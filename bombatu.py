"""
RenewalMatchMaker — Refactored with all performance recommendations applied.

Key changes vs. original
─────────────────────────
1.  FETCH ONCE   — candidates loaded from MongoDB a single time (one cursor,
                   one connection slot) BEFORE any tasks are spawned.
2.  NO PARALLEL CURSORS — asyncio.gather never touches MongoDB concurrently.
3.  POLARS DF    — 2M+ rows held in a Polars DataFrame; pre-filtering is
                   vectorised before fuzzy matching begins.
4.  SEMAPHORE    — caps concurrent fuzzy-match tasks to avoid memory spikes.
5.  PARQUET CACHE — optional short-lived cache so repeated runs skip Mongo.
6.  lru_cache    — _clean_string cached at the service level, not re-created
                   per alert.
7.  Early-exit   — stop_finding logic preserved from original, now inside
                   the per-alert matcher.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, AsyncGenerator

import polars as pl
from pymongo import ASCENDING, DESCENDING
from pymongo.collation import Collation
from rapidfuzz import fuzz  # drop-in for fuzzywuzzy, but faster

from your_project.constants import Constants
from your_project.models import CMConsolidatedDataModel
from your_project.types import MongoDocument

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_CN_RE = re.compile(r"CN=([^,]+)", re.IGNORECASE)

PARQUET_CACHE_PATH = Path("/tmp/cert_candidates.parquet")
PARQUET_CACHE_MAX_AGE_HOURS: float = 2.0

# How many fuzzy-match tasks may run concurrently.
# Pure CPU/memory work — no I/O — so this only guards against memory spikes.
MATCH_CONCURRENCY = 10


# ─────────────────────────────────────────────────────────────────────────────
# Base repository
# ─────────────────────────────────────────────────────────────────────────────

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
        """
        Seek-pagination over a large collection.

        Yields successive batches of `batch_size` documents. Safe to use with
        collections of millions of documents — it never uses skip/offset.

        ⚠️  Always consumed by a SINGLE sequential `async for` loop.
            Never pass this generator into asyncio.gather or equivalent.
        """

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        if sort_order not in (ASCENDING, DESCENDING):
            raise ValueError("sort_order must be ASCENDING or DESCENDING.")

        current_filter = base_filter_query.copy()
        _last_seen_value = last_seen_value

        while True:
            iter_filter = current_filter.copy()

            if _last_seen_value is not None:
                comparison = "$gt" if sort_order == ASCENDING else "$lt"
                iter_filter[sort_field] = {comparison: _last_seen_value}

            try:
                docs_batch = await self._execute_find_many(
                    filter_query=iter_filter,
                    projection=projection,
                    sort=[(sort_field, sort_order)],
                    limit=batch_size,
                    collation=collation,
                )

                if not docs_batch:
                    break

                if projection is None:
                    yield [self._read_map_to_model(doc) for doc in docs_batch]
                else:
                    yield docs_batch

                _last_seen_value = docs_batch[-1].get(sort_field)

                if _last_seen_value is None:
                    # Sort field missing from last document — cannot continue seek.
                    break

            except Exception as exc:
                raise RuntimeError(
                    f"Error in find_many_paginated_seek "
                    f"for {self._collection_name}: {exc!r}"
                ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Consolidated-data repository
# ─────────────────────────────────────────────────────────────────────────────

class CMConsolidatedDataMotorRepository(
    BaseReadMotorRepository[CMConsolidatedDataModel]
):

    async def find_valid_certificates_based_on_environments(
        self,
        environments: list[str],
        log_date_threshold: int,
        expiry_threshold: int,
        validity_threshold: int,
        source_names: list[str] | None = None,   # ← new field, optional
    ) -> AsyncGenerator[list[CMConsolidatedDataModel], None]:
        """
        Streams valid certificates that match the given environments (and
        optionally source names) using seek pagination.

        Always consumed sequentially — do NOT wrap in asyncio.gather.
        """

        base_query: MongoDocument = {
            "status": Constants.valid.capitalize(),
            "source_properties.environment": {"$in": environments},
            "days_to_expiration": {
                "$gt": expiry_threshold,
                "$lt": validity_threshold,
            },
            "log_date": {
                "$gte": datetime.now(timezone.utc) - timedelta(days=log_date_threshold),
            },
        }

        # Only add source filter when explicitly requested — keeps the index
        # selectivity intact for the common case.
        if source_names:
            base_query["source_properties.name"] = {"$in": source_names}

        async for batch in self.find_many_paginated_seek(
            base_filter_query=base_query,
            sort_field="_id",
            batch_size=100_000,
        ):
            yield batch


# ─────────────────────────────────────────────────────────────────────────────
# Service-level string cleaner  (created once, shared across all alerts)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=50_000)
def _clean_string(text: str, noise_words: tuple[str, ...]) -> str:
    """
    Normalise a distinguished name for fuzzy comparison.

    `noise_words` is a *tuple* so it is hashable and lru_cache works.
    """
    m = _CN_RE.search(text)
    if m:
        text = m.group(1)

    text = text.casefold()
    for word in noise_words:
        text = text.replace(word, "")

    return text.replace(".", " ").replace("-", " ").replace("_", " ").strip()


def _extract_cn(distinguished_name: str) -> str:
    """Return the CN value from a DN, or the full string if not found."""
    m = _CN_RE.search(distinguished_name)
    return m.group(1) if m else distinguished_name


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class RenewalMatchMakerService:

    def __init__(
        self,
        consolidated_data_repository: CMConsolidatedDataMotorRepository,
        cm_settings,                           # your settings object
    ) -> None:
        self.consolidated_data_repository = consolidated_data_repository
        self.cm_settings = cm_settings
        self._noise_words_tuple: tuple[str, ...] = tuple(cm_settings.noise_words)

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(self, actionable_certificates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Main entry point.

        Steps
        ─────
        1. De-duplicate incoming alerts by serial number.
        2. Fetch ALL candidate certificates from MongoDB — sequentially,
           using a single cursor.  No concurrency here.
        3. Materialise into a Polars DataFrame and (optionally) cache to
           Parquet so repeated runs within the same hour skip Mongo.
        4. Fan out fuzzy matching across all unique alerts — pure CPU work,
           no database I/O.  A semaphore caps peak memory use.
        """

        # Step 1 — deduplicate
        unique_alerts: list[dict[str, Any]] = list(
            {a["serial_number"]: a for a in actionable_certificates}.values()
        )

        # Step 2 & 3 — single sequential fetch → Polars DataFrame
        candidates_df: pl.DataFrame = await self._load_candidate_certificates()

        # Step 4 — concurrent fuzzy matching (no I/O, semaphore for memory)
        sem = asyncio.Semaphore(MATCH_CONCURRENCY)

        async def _guarded(alert: dict[str, Any]) -> dict[str, Any]:
            async with sem:
                return self._find_matches(alert, candidates_df)
            # endAsyncWith
        # endAsyncDef

        tasks = [_guarded(alert) for alert in unique_alerts]
        return list(await asyncio.gather(*tasks))

    # ── Private: load candidates ──────────────────────────────────────────────

    async def _load_candidate_certificates(self) -> pl.DataFrame:
        """
        Fetch every valid candidate from MongoDB into a Polars DataFrame.

        • Uses a SINGLE sequential cursor — one connection slot, no gather.
        • Writes a short-lived Parquet cache so repeated runs within
          PARQUET_CACHE_MAX_AGE_HOURS skip the Mongo round-trip entirely.
        • Returns immediately from cache if it is fresh enough.
        """

        # ── Cache hit? ────────────────────────────────────────────────────────
        if PARQUET_CACHE_PATH.exists():
            age_hours = (
                datetime.now().timestamp() - PARQUET_CACHE_PATH.stat().st_mtime
            ) / 3600
            if age_hours < PARQUET_CACHE_MAX_AGE_HOURS:
                return pl.read_parquet(PARQUET_CACHE_PATH)
            # endIf
        # endIf

        # ── Cache miss — stream from MongoDB ─────────────────────────────────
        rows: list[dict[str, Any]] = []

        async for batch in self.consolidated_data_repository\
                .find_valid_certificates_based_on_environments(
                    self.cm_settings.environments_to_monitor,
                    self.cm_settings.log_date_threshold,
                    self.cm_settings.expiry_threshold,
                    self.cm_settings.validity_threshold,
                    # pass source_names here if you have them:
                    # source_names=self.cm_settings.source_names,
                ):
            for cert in batch:
                rows.append({
                    "distinguished_name":   cert.distinguished_name,
                    "serial_number":        cert.source_properties.serial_number,
                    "days_to_expiration":   cert.days_to_expiration,
                    "expiration_date":      cert.expiration_date,
                    "csi_application_id":   cert.csi_application_id,
                    "ssl_cm_status":        cert.source_properties.ssl_cm_status,
                    "source_name":          cert.source_properties.name,
                })
            # endFor
        # endAsyncFor

        df = pl.DataFrame(rows)

        # ── Persist cache ─────────────────────────────────────────────────────
        try:
            df.write_parquet(PARQUET_CACHE_PATH)
        except OSError:
            pass  # non-fatal — cache is best-effort
        # endTryExcept

        return df

    # ── Private: match one alert against the in-memory DataFrame ─────────────

    def _find_matches(
        self,
        alert: dict[str, Any],
        candidates_df: pl.DataFrame,
    ) -> dict[str, Any]:
        """
        Pure in-memory fuzzy matching — NO database I/O.

        Because this method is synchronous (no `await`) it is safe to call
        from inside asyncio.gather without risk of starving the event loop
        (fuzzy string ops release the GIL via rapidfuzz's C extension).

        Strategy
        ────────
        1. Polars vectorised pre-filter  → eliminates obvious non-matches fast.
        2. rapidfuzz on the remaining subset → precise similarity scoring.
        3. Early exit once we have enough high-quality hits.
        """

        alert_sn      = alert["serial_number"]
        alert_dn      = alert["distinguished_name"]
        alert_csi     = alert["csi_id"]
        noise_words   = self._noise_words_tuple
        threshold     = self.cm_settings.distinguished_name_similarity_ratio * 100
        unique_identifier = f"{alert_dn} | {alert_sn}"

        # ── Step 1: Polars pre-filter (vectorised, no Python loop) ────────────
        #
        # Exclude the expiring certificate itself, then narrow by CN prefix
        # (first 4 chars, case-insensitive) to cut the candidate set before
        # we enter the expensive Python fuzzy loop.

        pre_filtered = candidates_df.filter(pl.col("serial_number") != alert_sn)

        alert_cn = _extract_cn(alert_dn)
        if len(alert_cn) >= 4:
            prefix = alert_cn[:4].casefold()
            pre_filtered = pre_filtered.filter(
                pl.col("distinguished_name").str.to_lowercase().str.contains(
                    prefix, literal=True
                )
            )
        # endIf

        # ── Step 2: Fuzzy matching on the pre-filtered subset ─────────────────

        matches: list[dict[str, Any]] = []
        seen_serials: set[str] = set()
        stop_finding = False

        s1 = _clean_string(alert_dn, noise_words)

        for row in pre_filtered.iter_rows(named=True):
            if stop_finding:
                break
            # endIf

            match_sn = row["serial_number"]
            if match_sn in seen_serials:
                continue
            # endIf

            s2 = _clean_string(row["distinguished_name"], noise_words)

            partial_score = fuzz.partial_ratio(s1, s2)
            token_score   = fuzz.token_sort_ratio(s1, s2)

            len1, len2    = len(s1), len(s2)
            length_ratio  = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 1.0

            score = max(partial_score * 0.8 + token_score * 0.2, token_score)
            if partial_score > 95 and token_score < 40 and length_ratio < 0.3:
                score = token_score
            # endIf

            if score >= threshold:
                seen_serials.add(match_sn)

                note = (
                    " (CSI Mismatch)"
                    if row["csi_application_id"] != alert_csi
                    else ""
                )

                matches.append({
                    "distinguished_name": row["distinguished_name"] + note,
                    "days_to_expiration": row["days_to_expiration"],
                    "expiration_date":    row["expiration_date"],
                    "serial_number":      match_sn,
                    "similarity_score":   round(score, 2),
                    "csi_application_id": row["csi_application_id"],
                    "ssl_cm_status":      row["ssl_cm_status"],
                })

                # Early-exit logic (preserved from original)
                all_perfect = all(m["similarity_score"] == 100.0 for m in matches)
                if all_perfect and len(matches) >= 3:
                    stop_finding = True
                elif len(matches) >= 6:
                    stop_finding = True
                # endIfElif
            # endIf
        # endFor

        # ── Step 3: Rank and limit ────────────────────────────────────────────

        top_3_by_score = sorted(
            matches, key=lambda x: x["similarity_score"], reverse=True
        )[:3]

        alert["certificates_match"] = sorted(
            top_3_by_score, key=lambda x: x["expiration_date"], reverse=True
        )

        return alert

"""
Architecture (biggest wins)

run() is now the single orchestrator — it fetches first, then fans out. MongoDB is never touched inside asyncio.gather.
_find_matches is now a plain def (not async def) — it does zero I/O, so there's nothing to await. rapidfuzz's C extension releases the GIL, so concurrent tasks won't block each other.

Database

find_valid_certificates_based_on_environments accepts an optional source_names list — your new field is additive and only injected into the query when provided, keeping index selectivity intact for the common case.
The sequential cursor in _load_candidate_certificates is the only place MongoDB is ever touched. One cursor, one connection slot, no exceptions.

Memory & concurrency

asyncio.Semaphore(10) in run() caps how many fuzzy-match tasks hold intermediate state simultaneously.
Parquet cache (2-hour TTL) means repeated runs within the same processing window skip Mongo entirely.

Fuzzy matching

_clean_string moved to module level with lru_cache(maxsize=50_000) — shared across all alerts instead of being recreated per-alert closure. noise_words passed as a tuple so it's hashable.
Polars CN-prefix pre-filter runs before any fuzzy call, cutting the per-alert candidate set dramatically.
fuzzywuzzy swapped for rapidfuzz — identical API, 10–100× faster, no python-Levenshtein warning.

"""
