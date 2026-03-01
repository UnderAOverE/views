"""
HYBRID RAPIDFUZZY MATCHING ARCHITECTURE
----------------------------------------

Strategy:
1. Pre-clean strings once (vectorized Polars)
2. Group alerts using customizable grouping strategy
3. Pre-filter candidate space using Polars (vectorized + cheap)
4. Run medium-sized batched cdist per group
5. Extract best match per alert
6. Merge all results

Why Hybrid?
-----------
• Faster than per-alert matching
• Safer memory than full NxM batch
• Architecturally scalable
• Easy to extend grouping logic

Libraries Required:
- polars
- rapidfuzz
"""

import polars as pl
from rapidfuzz import process, fuzz
from collections import defaultdict
import re
import time


# ============================================================
# 1️⃣ STRING NORMALIZATION (Vectorized in Polars)
# ============================================================

def normalize_string_column(df: pl.DataFrame, column: str) -> pl.DataFrame:
    """
    Cleans and standardizes string column.

    Why?
    - Reduces fuzzy distance noise
    - Improves score stability
    - Makes threshold 90 more meaningful
    """

    return df.with_columns(
        pl.col(column)
        .str.to_lowercase()
        .str.replace_all(r"\s+", "")     # remove whitespace
        .str.replace_all(r"[-_.]", "")   # remove separators
        .alias(column)
    )


# ============================================================
# 2️⃣ CUSTOMIZABLE GROUPING STRATEGY
# ============================================================

def default_grouping_strategy(alert_value: str) -> str:
    """
    Default grouping:
    - Uses first 6 characters as prefix cluster

    You can enhance this to:
    - Group by environment
    - Group by domain
    - Group by CSI
    - Regex-based families
    """

    return alert_value[:6]


def regex_environment_grouping(alert_value: str) -> str:
    """
    Example advanced grouping:
    Groups by environment tag like prod/test/dev
    """

    match = re.search(r"(prod|test|dev|qa)", alert_value)
    if match:
        return match.group(1)
    return alert_value[:6]


def group_alerts(alert_list, grouping_function):
    """
    Groups alerts dynamically using injected strategy.
    This makes architecture future-proof.
    """

    groups = defaultdict(list)

    for alert in alert_list:
        key = grouping_function(alert)
        groups[key].append(alert)

    return groups


# ============================================================
# 3️⃣ CANDIDATE PREFILTER (POLARS VECTOR SPEED)
# ============================================================

def prefilter_candidates(candidate_df: pl.DataFrame, prefix: str, column: str):
    """
    Reduce search space BEFORE fuzzy matching.

    Why?
    - Dramatically reduces NxM matrix size
    - Vectorized and very fast in Polars
    """

    return candidate_df.filter(
        pl.col(column).str.starts_with(prefix[:3])
    )


# ============================================================
# 4️⃣ HYBRID MATCHING ENGINE
# ============================================================

def hybrid_fuzzy_match(
    alerts_df: pl.DataFrame,
    candidates_df: pl.DataFrame,
    alert_column: str,
    candidate_column: str,
    grouping_function=default_grouping_strategy,
    threshold: int = 90
):
    """
    Main Hybrid Matching Function

    Steps:
    1. Normalize strings
    2. Extract alert list
    3. Group alerts
    4. For each group:
        - Pre-filter candidates
        - Run batched cdist
    5. Collect best matches
    """

    start_time = time.time()

    # Normalize columns
    alerts_df = normalize_string_column(alerts_df, alert_column)
    candidates_df = normalize_string_column(candidates_df, candidate_column)

    alert_list = alerts_df[alert_column].to_list()
    candidate_list_full = candidates_df[candidate_column].to_list()

    # Group alerts using customizable strategy
    grouped_alerts = group_alerts(alert_list, grouping_function)

    results = []

    print(f"Total groups formed: {len(grouped_alerts)}")

    for group_key, group_alerts_list in grouped_alerts.items():

        print(f"\nProcessing Group: {group_key}")
        print(f"Alerts in group: {len(group_alerts_list)}")

        # Pre-filter candidate space
        candidate_subset_df = prefilter_candidates(
            candidates_df, group_key, candidate_column
        )

        candidate_subset = candidate_subset_df[candidate_column].to_list()

        if not candidate_subset:
            continue

        print(f"Candidates after prefilter: {len(candidate_subset)}")

        # Batched fuzzy matching
        score_matrix = process.cdist(
            group_alerts_list,
            candidate_subset,
            scorer=fuzz.ratio,
            score_cutoff=threshold
        )

        # Extract best match per alert
        for i, scores in enumerate(score_matrix):

            if not scores:
                continue

            best_index = max(range(len(scores)), key=lambda x: scores[x])
            best_score = scores[best_index]

            results.append({
                "alert": group_alerts_list[i],
                "matched_candidate": candidate_subset[best_index],
                "score": best_score,
                "group": group_key
            })

    end_time = time.time()

    print(f"\nHybrid matching completed in {round(end_time - start_time, 2)} seconds")

    return pl.DataFrame(results)


# ============================================================
# 5️⃣ EXAMPLE USAGE
# ============================================================

if __name__ == "__main__":

    alerts_df = pl.DataFrame({
        "cn": [
            "api-prod-abc.company.com",
            "api-prod-def.company.com",
            "db-test-123.company.com",
            "db-test-456.company.com"
        ]
    })

    candidates_df = pl.DataFrame({
        "cn": [
            "apiprodabccompanycom",
            "apiprodxyzcompanycom",
            "dbtest123companycom",
            "dbtest999companycom",
            "randomserver.company.com"
        ]
    })

    result_df = hybrid_fuzzy_match(
        alerts_df,
        candidates_df,
        alert_column="cn",
        candidate_column="cn",
        grouping_function=default_grouping_strategy,
        threshold=85
    )

    print(result_df)
    
    
    
Hybrid Batched Fuzzy Matching Version
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
    """
    WHY CACHE?
    ----------
    Many certificates repeat similar DNs.
    Caching avoids recomputing normalization repeatedly.
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

        """
        SEEK PAGINATION
        ---------------
        More efficient than skip/limit for large Mongo collections.
        Avoids O(n) skip scanning.
        """

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

        # STEP 1 — Deduplicate by serial_number
        # --------------------------------------
        # Prevent duplicate fuzzy work.
        unique_alerts = list(
            {a["serial_number"]: a for a in actionable_certificates}.values()
        )

        # STEP 2 — Load candidate certificates into Polars
        # -------------------------------------------------
        # We convert Mongo batches into a Polars DataFrame.
        # WHY POLARS?
        #   - Columnar memory layout (Apache Arrow)
        #   - SIMD optimizations
        #   - Rust execution backend
        #   - Much faster filtering than Python loops
        candidates_df = await self._load_candidates()

        # STEP 3 — Clean alert DNs once
        # --------------------------------
        for alert in unique_alerts:
            alert["cleaned_dn"] = _clean_string(
                alert["distinguished_name"], self.noise_words
            )

        # STEP 4 — Hybrid Grouping
        # --------------------------
        grouped_alerts = self._group_alerts(unique_alerts)

        # STEP 5 — Process each group independently
        # ------------------------------------------
        # This limits memory peak to largest group only.
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

        # Convert Python list of dicts → Polars DataFrame
        # ------------------------------------------------
        # Polars stores data column-wise (Arrow memory format).
        # This improves filtering speed dramatically.
        df = pl.DataFrame(rows)

        # PRECOMPUTE CLEANED_DN USING POLARS
        # -----------------------------------
        # Why inside Polars?
        # - Ensures cleaned_dn is stored as column
        # - Avoids repeated cleaning during matching
        # - Enables vectorized filtering before fuzzy
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
        CURRENT STRATEGY:
            First 6 chars of cleaned_dn.

        WHY?
            Likely to cluster same domain families together.
            Reduces candidate comparison size.

        FUTURE EXTENSIONS:
            - Regex domain suffix grouping
            - Environment bucket grouping
            - CSI-based grouping
            - Wildcard prefix grouping
        """

        cleaned = alert["cleaned_dn"]
        return cleaned[:6] if len(cleaned) >= 6 else cleaned

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

        prefix = group_key

        # POLARS FILTER (CRITICAL OPTIMIZATION)
        # --------------------------------------
        # This runs in Rust, not Python.
        # Extremely fast and memory efficient.
        #
        # It reduces the candidate space BEFORE fuzzy matching.
        # This is what prevents large NxM matrices.
        pre_filtered = candidates_df.filter(
            pl.col("cleaned_dn").str.contains(prefix, literal=True)
        )

        if pre_filtered.height == 0:
            for alert in alerts:
                alert["certificates_match"] = []
            return alerts

        # Convert column to Python list ONCE
        alert_cleaned_list = [a["cleaned_dn"] for a in alerts]
        candidate_cleaned_list = pre_filtered["cleaned_dn"].to_list()

        # Convert remaining candidate rows to dict only once
        candidate_rows = pre_filtered.to_dicts()

        threshold = self.settings.distinguished_name_similarity_ratio * 100

        # HYBRID BATCHED FUZZY MATCH
        # ---------------------------
        # Only ONE cdist per group.
        # Memory = len(alerts) × len(candidate_subset) × 8 bytes.
        score_matrix = process.cdist(
            alert_cleaned_list,
            candidate_cleaned_list,
            scorer=fuzz.token_set_ratio,
            score_cutoff=threshold,
        )

        # Post-processing
        for i, alert in enumerate(alerts):

            matches = []

            for j, score in enumerate(score_matrix[i]):
                if score < threshold:
                    continue

                row = candidate_rows[j]

                if row["serial_number"] == alert["serial_number"]:
                    continue

                matches.append({
                    "distinguished_name": row["distinguished_name"],
                    "days_to_expiration": row["days_to_expiration"],
                    "expiration_date": row["expiration_date"],
                    "serial_number": row["serial_number"],
                    "similarity_score": round(score, 2),
                    "csi_application_id": row["csi_application_id"],
                    "ssl_cm_status": row["ssl_cm_status"],
                })

            # Rank by similarity then expiration
            alert["certificates_match"] = sorted(
                matches,
                key=lambda x: (x["similarity_score"], x["expiration_date"]),
                reverse=True
            )[:3]

        return alerts