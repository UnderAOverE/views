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
AMP's anomaly framework has long watched the top of the stack - business transactions, APIs, microservices, and their exceptions - but the platform infrastructure underneath had no coverage. When a database, cache, or gateway degraded, we only learned about it from the failures it caused upstream, not from the cause itself. Over the past two months we closed that gap: we extended the platform KPI pipeline to collect critical metrics from our core platforms through AppDynamics at a one-minute interval, and built learn-and-detect models on top so the system knows what "normal" looks like and flags genuine deviations. AMP now monitors the full dependency chain, from the infrastructure floor up to the business transaction - with 37 platform instances live today.

Column 1 - "What We Delivered"
A. Anomaly detection extended to the platform floor - the layer every business service silently depends on
B. A collect -> learn -> detect pipeline - built directly on the existing AppDynamics feed, no new agents
C. One-minute collection cadence - fast enough to catch sudden disruptions, not just slow drift
D. "Normal" learned per metric, per hour of the week - 168 baselines per metric, so 2am is judged against 2am
E. Robust baselines for steady metrics - median plus typical wobble, so one freak spike never poisons the norm
F. Percentile bands for bursty metrics - rates and latency, where the business-hours peak is normal, not an outlier
G. Operator-set hard lines where learning is wrong - a fixed ceiling for disk-fill and similar one-way creep
H. Every reading judged in context - not against one static line copied across every platform
I. Low-noise, trustworthy alerting - tuned so an alert means something and gets acted on
Column 2 - "Coverage Today"
A. 4 platform types live in production - one consistent model across all of them
B. GemFire - 9 clusters - in-memory data grid
C. Apigee - 3 planets - API gateway layer
D. Oracle - 10 databases - core relational data
E. Mongo - 15 databases - document data stores
F. MQ - onboarding in progress - messaging layer, next to join
G. 37 platform instances monitored today - and growing with each onboarding
H. Standardized critical KPIs per platform - the metrics that actually signal health
I. Same pipeline and models everywhere - adding a platform is a repeatable step, not a rebuild
Column 3 - "Business Value"
A. Catch the cause, not just the symptom - detect platform degradation at its source, before it surfaces upstream
B. No silent blind spot under AMP - full-stack coverage from infrastructure to business transaction
C. Faster time-to-detect, lower business impact - problems surface in minutes, not after customer-facing failures
D. Fewer false alarms - learned baselines beat fixed thresholds that fire at night and during peaks
E. Adapts to real patterns - daily and weekly rhythms are expected, so only genuine deviation alerts
F. One framework across all AMP layers - a single operating model to run, extend, and reason about
G. Repeatable, low-cost onboarding - each new platform reuses the same pipeline and tooling
H. A foundation for proactive health - the base for trend-based early warning as coverage grows





Col 1 - How It Works

Collect -> learn -> detect on the AppD feed
Critical KPIs at 1-minute intervals
Normal learned per metric, per hour of week (168 baselines)
Robust bands for steady metrics, percentile bands for bursty
Hard lines where learning is wrong (disk-fill)
Every reading judged in context, not one fixed line
Low-noise, trustworthy alerting
Col 2 - What It Covers

4 platform types in production
GemFire - 9 clusters
Apigee - 3 planets
Oracle - 10 databases
Mongo - 15 databases
MQ - onboarding next
37 instances live today
Col 3 - Key Benefits

Catch the cause, not the symptom
No blind spot under AMP - full-stack coverage
Faster time-to-detect, lower business impact
Fewer false alarms than fixed thresholds
Adapts to daily and weekly patterns
One framework across all AMP layers
Repeatable, low-cost onboarding
"Key Benefits" fits the exec framing well - it's outcome language, not delivery language. Want the columns balanced to equal row counts, or leave them as-is?

