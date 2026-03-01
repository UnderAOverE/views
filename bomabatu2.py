"""
RenewalMatchMaker — Fully Optimized Version
==========================================

STRATEGY OVERVIEW
-----------------
This version improves performance in 4 major ways:

1) MongoDB is streamed ONCE (seek pagination, no skip/offset).
2) Data is materialized into a Polars DataFrame (Rust engine, columnar).
3) Distinguished names are cleaned ONCE and stored in a new column.
4) RapidFuzz `process.cdist` performs bulk similarity scoring in C
   instead of Python row loops.

WHY THIS SCALES
---------------
• No parallel Mongo cursors
• No Python fuzzy loops
• Vectorized filtering in Polars
• Fuzzy matching executed in C
• Controlled asyncio concurrency

This design handles millions of records safely and efficiently.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, AsyncGenerator

import polars as pl
from pymongo import ASCENDING, DESCENDING
from pymongo.collation import Collation
from rapidfuzz import process, fuzz

from your_project.constants import Constants
from your_project.models import CMConsolidatedDataModel
from your_project.types import MongoDocument


# ─────────────────────────────────────────────────────────────
# REGEX: Extract CN from Distinguished Name
# Example:
#   CN=example.domain.com, OU=Test
# We only want: example.domain.com
# ─────────────────────────────────────────────────────────────
_CN_RE = re.compile(r"CN=([^,]+)", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# LRU-CACHED CLEANER
# Cleaning strings repeatedly is expensive.
# lru_cache avoids recomputation for identical strings.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=50_000)
def _clean_string(text: str, noise_words: tuple[str, ...]) -> str:
    """
    Normalize a distinguished name for fuzzy matching.

    Steps:
    1. Extract CN only
    2. Casefold (stronger than lower())
    3. Remove noise words
    4. Replace punctuation with spaces
    """

    match = _CN_RE.search(text)
    if match:
        text = match.group(1)

    text = text.casefold()

    for word in noise_words:
        text = text.replace(word, "")

    return (
        text.replace(".", " ")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


# ─────────────────────────────────────────────────────────────
# BASE REPOSITORY (UNCHANGED)
# Seek pagination for very large collections.
# ─────────────────────────────────────────────────────────────
class BaseReadMotorRepository[T](ABC):

    async def find_many_paginated_seek(
        self,
        base_filter_query: MongoDocument,
        sort_field: str,
        batch_size: int,
        last_seen_value: Any | None = None,
        sort_order: int = ASCENDING,
        projection: MongoDocument | None = None,
        collation: Collation | None = None,
    ) -> AsyncGenerator[list[T], None]:

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        current_filter = base_filter_query.copy()
        _last_seen_value = last_seen_value

        while True:
            iter_filter = current_filter.copy()

            if _last_seen_value is not None:
                comparison = "$gt" if sort_order == ASCENDING else "$lt"
                iter_filter[sort_field] = {comparison: _last_seen_value}

            docs_batch = await self._execute_find_many(
                filter_query=iter_filter,
                projection=projection,
                sort=[(sort_field, sort_order)],
                limit=batch_size,
                collation=collation,
            )

            if not docs_batch:
                break

            yield docs_batch
            _last_seen_value = docs_batch[-1].get(sort_field)


# ─────────────────────────────────────────────────────────────
# SERVICE
# ─────────────────────────────────────────────────────────────
class RenewalMatchMakerService:

    def __init__(self, consolidated_data_repository, cm_settings):
        self.consolidated_data_repository = consolidated_data_repository
        self.cm_settings = cm_settings
        self._noise_words_tuple = tuple(cm_settings.noise_words)

    # ==========================================================
    # MAIN ENTRY
    # ==========================================================
    async def run(self, actionable_certificates: list[dict[str, Any]]):

        # 1️⃣ Deduplicate alerts by serial number (O(n))
        unique_alerts = list(
            {a["serial_number"]: a for a in actionable_certificates}.values()
        )

        # 2️⃣ Load ALL candidates once into Polars
        candidates_df = await self._load_candidate_certificates()

        # 3️⃣ Concurrency guard to avoid memory spikes
        sem = asyncio.Semaphore(10)

        async def _guarded(alert):
            async with sem:
                return self._find_matches(alert, candidates_df)

        return list(await asyncio.gather(*[_guarded(a) for a in unique_alerts]))

    # ==========================================================
    # LOAD CANDIDATES INTO POLARS
    # ==========================================================
    async def _load_candidate_certificates(self) -> pl.DataFrame:

        rows = []

        async for batch in self.consolidated_data_repository\
                .find_valid_certificates_based_on_environments(
                    self.cm_settings.environments_to_monitor,
                    self.cm_settings.log_date_threshold,
                    self.cm_settings.expiry_threshold,
                    self.cm_settings.validity_threshold,
                ):
            for cert in batch:
                rows.append({
                    "distinguished_name": cert.distinguished_name,
                    "serial_number": cert.source_properties.serial_number,
                    "days_to_expiration": cert.days_to_expiration,
                    "expiration_date": cert.expiration_date,
                    "csi_application_id": cert.csi_application_id,
                    "ssl_cm_status": cert.source_properties.ssl_cm_status,
                })

        df = pl.DataFrame(rows)

        # 🔥 KEY OPTIMIZATION:
        # Precompute cleaned_dn ONCE.
        #
        # Polars Explanation:
        # with_columns() → adds/modifies columns
        # pl.col("distinguished_name") → selects column
        # map_elements() → applies Python function element-wise
        #
        # This runs once at load time instead of per alert.
        df = df.with_columns(
            pl.col("distinguished_name")
            .map_elements(
                lambda x: _clean_string(x, self._noise_words_tuple),
                return_dtype=pl.Utf8
            )
            .alias("cleaned_dn")
        )

        return df

    # ==========================================================
    # MATCH ONE ALERT
    # ==========================================================
    def _find_matches(self, alert, candidates_df: pl.DataFrame):

        alert_sn = alert["serial_number"]
        alert_dn = alert["distinguished_name"]
        alert_csi = alert["csi_id"]

        threshold = self.cm_settings.distinguished_name_similarity_ratio * 100

        # 1️⃣ POLARS FILTERING (VECTORISED IN RUST)
        #
        # filter() executes in Rust engine, not Python.
        # This is extremely fast even on millions of rows.
        pre_filtered = candidates_df.filter(
            pl.col("serial_number") != alert_sn
        )

        alert_cleaned = _clean_string(alert_dn, self._noise_words_tuple)

        # Prefix narrowing to reduce fuzzy workload
        if len(alert_cleaned) >= 4:
            prefix = alert_cleaned[:4]
            pre_filtered = pre_filtered.filter(
                pl.col("cleaned_dn").str.contains(prefix, literal=True)
            )

        if pre_filtered.height == 0:
            alert["certificates_match"] = []
            return alert

        # 2️⃣ BULK FUZZY MATCHING USING CDIST
        #
        # process.cdist runs entirely in C.
        # Much faster than Python loops.
        cleaned_candidates = pre_filtered["cleaned_dn"].to_list()
        candidate_rows = pre_filtered.to_dicts()

        scores = process.cdist(
            [alert_cleaned],
            cleaned_candidates,
            scorer=fuzz.token_set_ratio,
            score_cutoff=threshold,
        )[0]

        matches = []

        for idx, score in enumerate(scores):
            if score < threshold:
                continue

            row = candidate_rows[idx]

            note = (
                " (CSI Mismatch)"
                if row["csi_application_id"] != alert_csi
                else ""
            )

            matches.append({
                "distinguished_name": row["distinguished_name"] + note,
                "days_to_expiration": row["days_to_expiration"],
                "expiration_date": row["expiration_date"],
                "serial_number": row["serial_number"],
                "similarity_score": round(score, 2),
                "csi_application_id": row["csi_application_id"],
                "ssl_cm_status": row["ssl_cm_status"],
            })

        # 3️⃣ Ranking
        top_3_by_score = sorted(
            matches,
            key=lambda x: x["similarity_score"],
            reverse=True
        )[:3]

        alert["certificates_match"] = sorted(
            top_3_by_score,
            key=lambda x: x["expiration_date"],
            reverse=True
        )

        return alert