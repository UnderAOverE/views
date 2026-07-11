anomalies = st.Page(
    "pages/07_Anomalies.py",
    title="Anomalies",
    icon="🌪",
)

nav = st.navigation([
    home,
    targets,
    metrics_explorer,
    incidents,
    collections,
    config_inspector,
    thresholds_page,
    anomalies,          # <-- add here too, or it won't register
])


🚩


db.<platform>_metrics.aggregate([
  { $group: { _id: { i:"$metadata.instance", m:"$metadata.metric_name", t:"$ts" }, ids:{$push:"$_id"}, n:{$sum:1} } },
  { $match: { n: { $gt: 1 } } }
])
// delete all but one _id per group
