# ==========================================================
# 🔥 LOGGING SETUP (add inside __init__)
# ==========================================================
def __init__(self, consolidated_data_repository, cm_settings):
    self.repo = consolidated_data_repository
    self.settings = cm_settings
    self.noise_words = tuple(cm_settings.noise_words)

    # Configure logger (production safe)
    self.logger = logging.getLogger("renewal_matchmaker")

    if not self.logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    self.logger.setLevel(logging.INFO)


# ==========================================================
# 🛡 MEMORY ESTIMATOR
# ==========================================================
def _estimate_cdist_memory_mb(self, alert_count: int, candidate_count: int) -> float:
    return (alert_count * candidate_count * 8) / (1024 ** 2)


# ==========================================================
# 🔪 SPLIT ALERTS INTO SAFE CHUNKS
# ==========================================================
def _split_alerts_into_chunks(self, alerts: List[dict], max_chunk_size: int):
    for i in range(0, len(alerts), max_chunk_size):
        yield alerts[i:i + max_chunk_size]


# ==========================================================
# 🚀 CDIST EXECUTION (WITH LOGGING)
# ==========================================================
def _run_cdist_chunk(
    self,
    alerts: List[dict],
    candidate_cleaned_list: List[str],
    candidate_rows: List[dict],
    threshold: float
):

    start = time.time()

    alert_cleaned_list = [a["cleaned_dn"] for a in alerts]

    score_matrix = process.cdist(
        alert_cleaned_list,
        candidate_cleaned_list,
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
    )

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

        alert["certificates_match"] = sorted(
            matches,
            key=lambda x: (x["similarity_score"], x["expiration_date"]),
            reverse=True
        )[:3]

    duration = round(time.time() - start, 3)

    self.logger.info(
        f"Processed chunk: alerts={len(alerts)} | "
        f"candidates={len(candidate_cleaned_list)} | "
        f"time={duration}s"
    )

    return alerts


# ==========================================================
# 🧠 UPDATED _process_group WITH FULL LOGGING
# ==========================================================
def _process_group(self, group_key: str, alerts: List[dict], candidates_df: pl.DataFrame):

    if not alerts:
        return []

    group_start = time.time()

    prefix = group_key

    # 🔥 Polars Prefilter
    pre_filtered = candidates_df.filter(
        pl.col("cleaned_dn").str.contains(prefix, literal=True)
    )

    candidate_count = pre_filtered.height

    self.logger.info(
        f"Group '{group_key}' | alerts={len(alerts)} | "
        f"candidates_after_filter={candidate_count}"
    )

    if candidate_count == 0:
        for alert in alerts:
            alert["certificates_match"] = []
        return alerts

    candidate_cleaned_list = pre_filtered["cleaned_dn"].to_list()
    candidate_rows = pre_filtered.to_dicts()

    threshold = self.settings.distinguished_name_similarity_ratio * 100

    # ==========================================================
    # 🛡 MEMORY GUARDRAIL CHECK
    # ==========================================================
    MAX_MEMORY_MB = 300

    estimated_mb = self._estimate_cdist_memory_mb(
        len(alerts),
        candidate_count
    )

    self.logger.info(
        f"Group '{group_key}' estimated memory: "
        f"{round(estimated_mb,2)} MB"
    )

    if estimated_mb > MAX_MEMORY_MB:

        self.logger.warning(
            f"Memory guardrail triggered for group '{group_key}' "
            f"(estimated {round(estimated_mb,2)} MB)"
        )

        safe_alert_count = int(
            (MAX_MEMORY_MB * (1024 ** 2)) /
            (candidate_count * 8)
        )

        safe_alert_count = max(1, safe_alert_count)

        self.logger.warning(
            f"Splitting group '{group_key}' into chunks of size "
            f"{safe_alert_count}"
        )

        final_results = []

        for chunk in self._split_alerts_into_chunks(alerts, safe_alert_count):
            final_results.extend(
                self._run_cdist_chunk(
                    chunk,
                    candidate_cleaned_list,
                    candidate_rows,
                    threshold
                )
            )

        total_duration = round(time.time() - group_start, 3)

        self.logger.info(
            f"Group '{group_key}' completed in {total_duration}s"
        )

        return final_results

    # ==========================================================
    # 🚀 NORMAL HYBRID EXECUTION
    # ==========================================================
    results = self._run_cdist_chunk(
        alerts,
        candidate_cleaned_list,
        candidate_rows,
        threshold
    )

    total_duration = round(time.time() - group_start, 3)

    self.logger.info(
        f"Group '{group_key}' completed in {total_duration}s"
    )

    return results












# ==========================================================
# 🛡 MEMORY GUARDRAIL ADDITIONS
# Add ALL of this inside RenewalMatchMakerService
# ==========================================================


# ─────────────────────────────────────────────────────────────
# 1️⃣ MEMORY ESTIMATOR
# ─────────────────────────────────────────────────────────────
def _estimate_cdist_memory_mb(self, alert_count: int, candidate_count: int) -> float:
    """
    Estimates memory usage of RapidFuzzy process.cdist.

    Why needed?
    -----------
    cdist builds a full similarity matrix in memory:
        alerts × candidates × 8 bytes

    Each score ≈ float64 (8 bytes).

    This helps prevent OOM crashes in Kubernetes/OpenShift.

    Returns:
        Estimated memory usage in MB.
    """

    return (alert_count * candidate_count * 8) / (1024 ** 2)


# ─────────────────────────────────────────────────────────────
# 2️⃣ SPLIT ALERTS INTO SAFE CHUNKS
# ─────────────────────────────────────────────────────────────
def _split_alerts_into_chunks(self, alerts: List[dict], max_chunk_size: int):
    """
    Splits alerts into smaller batches when memory guardrail triggers.

    Why?
    ----
    If group is too large, we break it into smaller chunks
    so each cdist call stays under memory threshold.
    """

    for i in range(0, len(alerts), max_chunk_size):
        yield alerts[i:i + max_chunk_size]


# ─────────────────────────────────────────────────────────────
# 3️⃣ SHARED CDIST EXECUTION LOGIC
# ─────────────────────────────────────────────────────────────
def _run_cdist_chunk(
    self,
    alerts: List[dict],
    candidate_cleaned_list: List[str],
    candidate_rows: List[dict],
    threshold: float
):

    alert_cleaned_list = [a["cleaned_dn"] for a in alerts]

    score_matrix = process.cdist(
        alert_cleaned_list,
        candidate_cleaned_list,
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
    )

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

        alert["certificates_match"] = sorted(
            matches,
            key=lambda x: (x["similarity_score"], x["expiration_date"]),
            reverse=True
        )[:3]

    return alerts


# ─────────────────────────────────────────────────────────────
# 4️⃣ REPLACE YOUR EXISTING _process_group WITH THIS VERSION
# ─────────────────────────────────────────────────────────────
def _process_group(self, group_key: str, alerts: List[dict], candidates_df: pl.DataFrame):

    if not alerts:
        return []

    prefix = group_key

    # 🔥 POLARS PREFILTER (Vectorized in Rust)
    pre_filtered = candidates_df.filter(
        pl.col("cleaned_dn").str.contains(prefix, literal=True)
    )

    if pre_filtered.height == 0:
        for alert in alerts:
            alert["certificates_match"] = []
        return alerts

    candidate_cleaned_list = pre_filtered["cleaned_dn"].to_list()
    candidate_rows = pre_filtered.to_dicts()

    threshold = self.settings.distinguished_name_similarity_ratio * 100

    # ==========================================================
    # 🛡 MEMORY GUARDRAIL CHECK
    # ==========================================================
    MAX_MEMORY_MB = 300  # 🔧 Adjust based on pod/machine RAM

    estimated_mb = self._estimate_cdist_memory_mb(
        len(alerts),
        len(candidate_cleaned_list)
    )

    if estimated_mb > MAX_MEMORY_MB:

        print(f"⚠ Memory guardrail triggered for group: {group_key}")
        print(f"Estimated usage: {round(estimated_mb, 2)} MB")

        # Calculate safe number of alerts per chunk
        safe_alert_count = int(
            (MAX_MEMORY_MB * (1024 ** 2)) /
            (len(candidate_cleaned_list) * 8)
        )

        safe_alert_count = max(1, safe_alert_count)

        print(f"Splitting into chunks of size: {safe_alert_count}")

        final_results = []

        for chunk in self._split_alerts_into_chunks(alerts, safe_alert_count):
            final_results.extend(
                self._run_cdist_chunk(
                    chunk,
                    candidate_cleaned_list,
                    candidate_rows,
                    threshold
                )
            )

        return final_results

    # ==========================================================
    # 🚀 NORMAL HYBRID EXECUTION (IF SAFE)
    # ==========================================================
    return self._run_cdist_chunk(
        alerts,
        candidate_cleaned_list,
        candidate_rows,
        threshold
    )