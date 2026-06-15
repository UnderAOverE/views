python -c "import sys, inspect; import sources.appd.controllers as m; print(sys.executable); print(m.__file__); print('NY' if 'replace(tzinfo=None)' in inspect.getsource(m.AppDCredential._normalize_to_utc) else 'OLD')"


# 1. Stop everything (so nothing holds the old code in memory)
bin/stop.sh ; bin/stop_dashboards.sh ; bin/stop_api.sh

# 2. Activate the venv
source .venv/bin/activate

# 3. Uninstall the package — run twice (pip sometimes leaves a duplicate)
pip uninstall -y platform-kpi
pip uninstall -y platform-kpi        # 2nd time should say "not installed"

# 4. PROVE it's gone — this should now ERROR (ModuleNotFoundError)
python -c "import sources.appd.controllers" 2>&1 | tail -1
#   - if it errors  -> good, clean. continue.
#   - if it STILL imports -> there's a stray hand-copied package shadowing it:
python -c "import sources, os; print(os.path.dirname(os.path.dirname(sources.__file__)))"
#     ^ that prints the dir to delete; rm -rf the leftover package dirs it shows under site-packages

# 5. Purge caches + stale build artifacts + bytecode
pip cache purge
rm -rf build/ dist/ .eggs/ *.egg-info src/*.egg-info
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
# clear any leftover editable pointer files from a previous attempt:
find .venv -name "__editable__*platform*" -delete 2>/dev/null
find .venv -name "*platform*kpi*.pth" -delete 2>/dev/null

# 6. Fresh editable install, no cache
pip install -e . --no-cache-dir

# 7. VERIFY it loads from src (this is the gate — must show a .../src/... path, NOT site-packages)
python -c "import sources.appd.controllers as m; print(m.__file__)"

# 8. Start everything back up
bin/start.sh ; bin/start_dashboards.sh ; bin/start_api.sh

# 9. Confirm the daemon now loads the fix
grep appd.tz_normalization.status var/logs/daemon/daemon.log | tail -1
#   -> expect: active: true, applied_offset_hours: 5.0, controllers_module: .../src/...
The two checkpoints that matter
Step 4 must error. If import sources still works right after uninstalling, a stray copied package is shadowing everything — that's almost certainly your whole problem. The command there prints exactly which directory to delete.
Step 7 must print a .../src/... path. If it shows site-packages, the editable install didn't take — stop and tell me, don't start the services yet.
Notes
Adjust .venv if your prod venv lives elsewhere.
pip pull/git pull first if your prod src isn't already at commit 4aeaa83 — the editable install links to whatever's in src, so it must have the fix.
If pip install -e . errors on package discovery, that's the pyproject.toml packages=[...] issue — tell me and I'll switch it to [tool.setuptools.packages.find] where=["src"].
Run it and paste step 4's output and step 7's path — those two lines tell us if the wipe finally cleared the stale copy.

/opt/appdata/app/platform_kpi/.venv/bin/python -c "from datetime import datetime, timezone; from pydantic import SecretStr; import sources.appd.controllers as m; p=datetime(2026,1,1,tzinfo=timezone.utc); print('offset', (m.AppDCredential(bearer_token=SecretStr('x'), bearer_token_expiration=p).bearer_token_expiration - p).total_seconds()/3600); print('from', m.__file__)"



Core concepts
Bucket — one hour-of-the-week slot. The week is sliced into 168 (7 days × 24 hours); "Tuesday 2pm" is its own bucket. Each gets its own "normal."
Sample — one collected data point (one metric reading at one timestamp). ~1 per minute from AppD.
Band — the "normal range" [lower, upper] fitted for one bucket. One band per (target × instance × metric × bucket).
Fit — the daily job that reads samples and computes the bands.
Training window — how far back the fit looks (90 days). The pool of history each band is built from.
Why a bucket gets skipped (no band)
Low-sample skip — bucket had fewer than 30 samples (min_samples_per_bucket) → not enough data to trust → skipped.
Flat skip — every sample in the bucket was the same value (max == min) → can't draw a meaningful range → skipped. Usually a stuck/constant metric.
min_samples_per_bucket — the floor (30). Below it, no band.
Per-platform fit-health columns
status — freshness of the platform's last fit run: 🟢 fresh (<24h) / 🟡 stale (24-36h) / 🔴 overdue (>36h or never).
platform — gemfire / apigee.
collection — the Mongo collection holding the bands (gemfire_thresholds).
total bands — count of all band documents.
stale bands — count of individual bands not refreshed in >36h (they fit once, then stopped qualifying). Different from the status column.
low-sample skips — how many buckets were dropped for <30 samples this run.
flat skips — how many buckets were dropped for being flat this run.
last fit — when the most recent fit ran.
age — how long ago that was.
fit_run_id — the UUID of that fit run; use it to grep the daemon log.
Flat-series table columns
target_key — which monitored target (e.g. apigee-cassandra-planet7-swdc-clientrequest).
instance — which node/server (e.g. sd-bcdb-5e9c_cassandra).
metric_name — which metric (ClientRequest (Read)|Latency|95thPercentile).
bucket — the flat hour-of-week slot (6_19 = Saturday 19:00 UTC).
Statuses (quick)
🟢 fresh — fit ran within cadence (24h). Good.
🟡 stale — fit is 24-36h old. Watch.
🔴 overdue — fit >36h old or never. Investigate.
Band strategy (bonus — you'll see this elsewhere)
median_mad — band = typical value ± wobble. For steady metrics (heap, CPU).
percentile — band = middle 98% of values (p1-p99). For bursty metrics (rates, latency).
Want me to add the alerting/consumer terms too (lower_bound, upper_bound, fitted_at, sample_count, "no opinion"), or is the fit side enough?

yes add those too
Band fields (what's stored in each band document)
lower_bound — the bottom edge of normal. sample.value < lower_bound ⇒ anomalous low.
upper_bound — the top edge of normal. sample.value > upper_bound ⇒ anomalous high.
sample_count — how many samples were used to fit this band. The confidence/weight — higher = more trustworthy. Below ~30 it wouldn't exist.
fitted_at — when this band was computed (UTC). Used to tell if a band is stale.
window_days — how much history it was fit over (90). Informational, for alert messages.
strategy — which recipe produced it: median_mad or percentile.
parameters — the raw math inputs (see below). Optional; used for nice alert wording.
fit_run_id — the run that produced it; ties all bands from one fit together.
How the detector (other team) uses them
anomalous low — incoming value fell below lower_bound. For rates/latency, often "service quietly died."
anomalous high — incoming value rose above upper_bound. Leak, spike, runaway.
"no opinion" — no band for this bucket (or band too thin/stale) → detector stays silent, never alerts. The safe default during cold-start/gaps.
staleness window — the consumer's own "ignore bands older than X" cutoff (~14 days suggested). A band past it = no opinion.
min-confidence floor — the consumer's "ignore bands with sample_count below N" cutoff. Thin bands = no opinion.
Inside the math (parameters)
median — the typical (middle) value of the bucket. Center of a median_mad band.
MAD — Median Absolute Deviation = the typical wobble around the median (robust to outliers).
k / k_lower / k_upper — how many MADs out the band edges sit. lower = median - k_lower×MAD, upper = median + k_upper×MAD. Bigger k = wider/looser.
p_lower / p_upper — the percentile edges for a percentile band (e.g. p1 and p99 = middle 98%).
winsorize — before fitting, clip the most extreme 1% of samples so recurring spikes don't widen the band. Invisible in the output.
One-line mental model
Each bucket gets a band [lower, upper], fit from samples over the training window using a strategy. A live sample outside the band = anomaly; no band / thin / stale = no opinion (silence).

That covers the full lifecycle — fit side (buckets, samples, skips), the band schema, and how the consumer turns a band into an alert-or-silence decision.

and also thre shoul dbe ideally 60 samples in a bukcet correct?
Almost — 60 is right for one occurrence of the bucket, but the bucket total over the full window is much higher. Let me untangle it.

Per single occurrence of that hour (one week's worth):

1 sample/minute × 60 minutes = ~60 samples. ✅ That's your 60.
Per bucket over the whole 90-day training window:

A bucket (e.g. "Tuesday 2pm") happens once a week, and the window holds ~13 weeks (90 ÷ 7).
So a mature bucket pools ~60 × 13 ≈ 780 samples, not 60.

1 occurrence  (1 hour)        ~60   samples
1 week                        ~60   (one Tuesday-2pm)
full 90-day window (~13 wks)  ~780  (~13 Tuesday-2pms)
So the numbers to keep straight:

~60 = a single hour, polled every minute.
~780 = a fully warmed-up bucket at 90 days.
30 = the floor; even one ~60-sample occurrence clears it.
Why this matters: if you see a bucket stuck around ~60 after several weeks, that series is only reporting ~1 hour per week (sparse) — a candidate for low-sample skips and stale bands. And that sample_count: 47 you saw earlier is just shy of one full hour — about 47 of the 60 minutes collected (partial first occurrence, or a few missing minutes), exactly what you'd expect a few days into warmup.

So: 60 per hour-occurrence, yes — but a healthy mature bucket should climb to several hundred as the weeks stack up.




/opt/appdata/amp/platform_kpi/.venv/bin/python -c "from dashboards.data.collections import per_platform_collection_stats as f; [print(r['collection'], '->', r['latest_ts']) for r in f() if 'threshold' in r['suffix'] or r['suffix']=='fit_runs']"


/opt/appdata/amp/platform_kpi/.venv/bin/python -c "import inspect, dashboards.data.collections as c; s=inspect.getsource(c); print('FILE:', c.__file__); print('FIX PRESENT:', '_LATEST_TS_FIELD' in s and 'fitted_at' in s)"

