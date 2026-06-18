from datetime import datetime, timezone
from core.services.thresholds import _fit_median_mad

vals = [5.0]*40 + [9.0]*7          # median=5, MAD=0, but min(5) != max(9)
band = _fit_median_mad(
    target_key="t", instance="i", metric_name="m", bucket="1_0",
    values=vals, k_lower=3.5, k_upper=3.5,
    fitted_at=datetime.now(timezone.utc), window_days=180, fit_run_id="x",
)
print("mad        :", band.parameters["mad"])         # 0.0
print("lower/upper:", band.lower_bound, band.upper_bound)  # equal
print("min != max :", min(vals) != max(vals))         # True -> old guard would NOT catch
print("now skipped:", band.lower_bound == band.upper_bound)  # True -> new guard catches
PY
(If the import fails, prefix PYTHONPATH=src.) This shows the smoking gun: a bucket where min != max (so the old min == max check passed it through and wrote a zero-width band) now satisfies lower == upper, which is exactly what the new guard skips on. That's proof the gap is closed.

3. Confirm end-to-end on a real fit run. After bin/compute_thresholds.sh --platforms apigee, grab the fit_run_id from the stats block, then:


// No zero-width band should exist from this run:
db.apigee_thresholds.find({ $expr: { $eq: ["$lower_bound", "$upper_bound"] } }).count()   // expect 0

// And the things it skipped are recorded - look for your near-constant metrics here:
db.apigee_fit_runs.find({ fit_run_id: "<id>" }, { buckets_skipped_flat: 1, flat_series_sample: 1 })
The flat_series_sample list in the fit-run summary names the (target, instance, metric, bucket) tuples it skipped as flat. If a mostly-flat metric (e.g. a PendingTasks that's 0 most of the time with a few non-zero blips) shows up there, that's direct operational proof the new guard fired — under the old code that same series would've been written as a zero-width band instead of appearing in this list.

So: grep+restart proves it's deployed, the snippet proves it behaves, and the fit_run query proves it fired on your real data. The snippet is the one I'd run first — it's instant and unambiguous.

