"""
RenewalMatchMaker — Hybrid Batched Fuzzy Matching Version
==========================================================

WHAT THIS VERSION DOES
----------------------
Instead of:
    • Matching per alert (many small cdist calls)
OR
    • Matching all alerts in one giant matrix (large memory spike)

We:
    • Group alerts by a configurable strategy
    • Run process.cdist per group
    • Merge results

WHY HYBRID IS IDEAL
-------------------
✔ Faster than per-alert version
✔ Lower memory than full-batch version
✔ Easy to extend grouping logic later
✔ Cleaner architecture for large-scale systems

GROUPING IS CUSTOMIZABLE.
You can modify `_group_key_strategy()` anytime without changing the engine.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List

import polars as pl
from pymongo import ASCENDING
from rapidfuzz import process, fuzz

from your_project.constants import Constants
from your_project.models import CMConsolidatedDataModel
from your_project.types import MongoDocument


# ─────────────────────────────────────────────────────────────
# REGEX TO EXTRACT CN
# ─────────────────────────────────────────────────────────────
_CN_RE = re.compile(r"CN=([^,]+)", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# CLEANER (CACHED)
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=50_000)
def _clean_string(text: str, noise_words: tuple[str, ...]) -> str:
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
# ─────────────────────────────────────────────────────────────
class BaseReadMotorRepository[T](ABC):

    async def find_many_paginated_seek(
        self,
        base_filter_query: MongoDocument,
        sort_field: str,
        batch_size: int,
        last_seen_value: Any | None = None,
        sort_order: int = ASCENDING,
    ) -> AsyncGenerator[list[T], None]:

        current_filter = base_filter_query.copy()
        _last_seen_value = last_seen_value

        while True:
            iter_filter = current_filter.copy()

            if _last_seen_value is not None:
                iter_filter[sort_field] = {"$gt": _last_seen_value}

            docs_batch = await self._execute_find_many(
                filter_query=iter_filter,
                sort=[(sort_field, sort_order)],
                limit=batch_size,
            )

            if not docs_batch:
                break

            yield docs_batch
            _last_seen_value = docs_batch[-1].get(sort_field)


# ─────────────────────────────────────────────────────────────
# HYBRID MATCH SERVICE
# ─────────────────────────────────────────────────────────────
class RenewalMatchMakerService:

    def __init__(self, consolidated_data_repository, cm_settings):
        self.repo = consolidated_data_repository
        self.settings = cm_settings
        self.noise_words = tuple(cm_settings.noise_words)

    # ==========================================================
    # ENTRY POINT
    # ==========================================================
    async def run(self, actionable_certificates: list[dict[str, Any]]):

        # 1️⃣ Deduplicate alerts
        unique_alerts = list(
            {a["serial_number"]: a for a in actionable_certificates}.values()
        )

        # 2️⃣ Load candidate certificates once
        candidates_df = await self._load_candidates()

        # 3️⃣ Pre-clean alerts once
        for alert in unique_alerts:
            alert["cleaned_dn"] = _clean_string(
                alert["distinguished_name"], self.noise_words
            )

        # 4️⃣ Group alerts (HYBRID STRATEGY)
        grouped_alerts = self._group_alerts(unique_alerts)

        # 5️⃣ Process each group
        results = []
        for group_key, alerts in grouped_alerts.items():
            results.extend(
                self._process_group(group_key, alerts, candidates_df)
            )

        return results

    # ==========================================================
    # LOAD CANDIDATES INTO POLARS
    # ==========================================================
    async def _load_candidates(self) -> pl.DataFrame:

        rows = []

        async for batch in self.repo\
                .find_valid_certificates_based_on_environments(
                    self.settings.environments_to_monitor,
                    self.settings.log_date_threshold,
                    self.settings.expiry_threshold,
                    self.settings.validity_threshold,
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

        # 🔥 Precompute cleaned_dn once
        df = df.with_columns(
            pl.col("distinguished_name")
            .map_elements(
                lambda x: _clean_string(x, self.noise_words),
                return_dtype=pl.Utf8
            )
            .alias("cleaned_dn")
        )

        return df

    # ==========================================================
    # GROUPING STRATEGY (CUSTOMIZABLE)
    # ==========================================================
    def _group_key_strategy(self, alert: dict) -> str:
        """
        Customize grouping logic here.

        Current Strategy:
        Group by first 6 characters of cleaned_dn.

        You can later extend this to:
            - environment
            - CSI ID
            - domain suffix
            - wildcard grouping
            - custom regex buckets
        """

        cleaned = alert["cleaned_dn"]

        if len(cleaned) >= 6:
            return cleaned[:6]

        return cleaned

    def _group_alerts(self, alerts: List[dict]) -> Dict[str, List[dict]]:

        groups = {}

        for alert in alerts:
            key = self._group_key_strategy(alert)
            groups.setdefault(key, []).append(alert)

        return groups

    # ==========================================================
    # PROCESS ONE GROUP (HYBRID CORE)
    # ==========================================================
    def _process_group(self, group_key: str, alerts: List[dict], candidates_df: pl.DataFrame):

        if not alerts:
            return []

        # Use first alert prefix for candidate narrowing
        prefix = group_key

        # Polars filter (vectorized in Rust)
        pre_filtered = candidates_df.filter(
            pl.col("cleaned_dn").str.contains(prefix, literal=True)
        )

        if pre_filtered.height == 0:
            for alert in alerts:
                alert["certificates_match"] = []
            return alerts

        # Prepare batch fuzzy input
        alert_cleaned_list = [a["cleaned_dn"] for a in alerts]
        candidate_cleaned_list = pre_filtered["cleaned_dn"].to_list()
        candidate_rows = pre_filtered.to_dicts()

        threshold = self.settings.distinguished_name_similarity_ratio * 100

        # 🚀 Single batched cdist per group
        score_matrix = process.cdist(
            alert_cleaned_list,
            candidate_cleaned_list,
            scorer=fuzz.token_set_ratio,
            score_cutoff=threshold,
        )

        # Post-process per alert
        for i, alert in enumerate(alerts):

            matches = []

            for j, score in enumerate(score_matrix[i]):
                if score < threshold:
                    continue

                row = candidate_rows[j]

                if row["serial_number"] == alert["serial_number"]:
                    continue

                note = (
                    " (CSI Mismatch)"
                    if row["csi_application_id"] != alert["csi_id"]
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

            # Rank results
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

        return alerts