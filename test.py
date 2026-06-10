db.gemfire_metrics.aggregate([
  { $match: { "metadata.metric_name": "ClientConnectionCount" } },
  { $group: { _id: { instance: "$metadata.instance", ts: "$ts" }, copies: { $sum: 1 } } },
  { $match: { copies: { $gt: 1 } } },
  { $limit: 5 }
])
