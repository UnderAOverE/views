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