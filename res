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


Executive Summary
AMP's anomaly framework now watches the infrastructure beneath business transactions, APIs, and microservices - the layer that was never monitored. We extended the platform KPI pipeline to collect critical metrics from our core platforms through AppDynamics at a one-minute interval, and built learn-and-detect models on top, so the system knows what "normal" looks like and flags genuine deviations.

Currently live across 37 platform instances.

Col 1 - How It Works
Platform KPI Pipeline Anomaly Detection extends AMP down to the platform infrastructure layer. It collects critical KPIs through AppDynamics at one-minute intervals, learns a dynamic baseline for every metric, and uses statistical modeling plus operator-set hard lines so only genuine anomalies are flagged.

Detection strategies:

Dynamic baselines - learned per metric, per hour of the week
Robust bands for steady metrics (median + typical wobble)
Percentile bands for bursty metrics (rates, latency)
Static hard lines where learning is the wrong tool (disk-fill)
Col 2 - What It Covers
CORE IDEA - Bring platform infrastructure into the AMP anomaly framework: the databases, caches, and gateways every business service depends on, previously unmonitored.

PLATFORMS LIVE (37 instances):

GemFire - 9 clusters (in-memory data grid)
Apigee - 3 planets (API gateway)
Oracle - 10 databases
Mongo - 15 databases
MQ - onboarding next.

Col 3 - Key Benefits
Catch the cause, not the symptom - detect platform degradation at its source, before it surfaces as failed transactions upstream.
No blind spot under AMP - full-stack coverage, from the infrastructure floor up to the business transaction.
Fewer false alarms - learned baselines beat fixed thresholds that fire at night and during peak hours.
Faster time-to-detect - issues surface in minutes at 1-minute collection, lowering business impact.
One consistent framework - same collect-learn-detect model on every platform, so onboarding the next one is repeatable, not a rebuild.
