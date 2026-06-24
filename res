db.gemfire_metrics.aggregate([
  { $group: { _id: { i: "$metadata.instance", m: "$metadata.metric_name", t: "$ts" }, n: { $sum: 1 } } },
  { $match: { n: { $gt: 1 } } },
  { $limit: 5 }
])
