 - name: "Used%"
    unit: percent
    metric_type: gauge
    description: Filesystem used percent for /opt/apigee on the polled node. Point-in-time sample.
    precision: 2
    alert_direction: upper_only

  - name: "Current Usage (MB)"
    unit: MB
    metric_type: gauge
    description: JVM heap current usage in megabytes for the polled node. Point-in-time sample.
    precision: 2
	alert_direction: upper_only

  - name: "Process CPU Usage %"
    unit: percent
    metric_type: gauge
    description: JVM process CPU usage percent for the polled node. Point-in-time sample.
    precision: 2
	alert_direction: upper_only

  # ---- Apigee node throughput / latency (bursty - percentile) ----

  - name: "Calls per Minute"
    unit: calls/min
    metric_type: rate
    description: Requests served per minute by the node over the sample minute. Bursty with load.
    precision: 0

  - name: "Average Response Time (ms)"
    unit: ms
    metric_type: rate
    description: Mean request response time over the sample minute, in milliseconds. Bursty with load.
    precision: 2
	alert_direction: upper_only
