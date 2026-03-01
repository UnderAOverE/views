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