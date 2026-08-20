  - primary_key: AO_Queues_gtdc
    enabled: true
    datacenter: gtdc
    poll_interval_minutes: 5
    lookback_minutes: 8

    # Queue name rides in the metric_name ("BCBSWI.CICSE.EAST.WWWQ.REPLY.Q|Current Queue Depth"),
    # one series per queue per node, no per-queue config. Do not remove.
    metric_name_segments: 2

    # Empty = every queue is kept; new queues onboard themselves.
    # Mute one with "<queue>|Current Queue Depth" in metric_exclude.
    metric_include: []
    metric_exclude: []

    # NODES only - same 12 host-qualified pairs as the Channels target.
    instance_include:
      - "gtcrd-mqdla01p-GTPRDDIG01"
      - "gtcrd-mqdla02p-GTPRDDIG01"
      - "gtcrd-mqdla01p-GTPRDDIG02"
      - "gtcrd-mqdla02p-GTPRDDIG02"
      - "gtcrd-mqdla01p-GTPRDDIG03"
      - "gtcrd-mqdla02p-GTPRDDIG03"
      - "gtcrd-mqdla01p-GTPRDDIG04"
      - "gtcrd-mqdla02p-GTPRDDIG04"
      - "gtcrd-mqdla01p-GTPRDDIG05"
      - "gtcrd-mqdla02p-GTPRDDIG05"
      - "gtcrd-mqdla01p-GTPRDDIG06"
      - "gtcrd-mqdla02p-GTPRDDIG06"

    instance_exclude: []

    source_config:
      type: appd
      controller_ref: GCG-NA-PRD4
      credential_key: ampchat_dna
      appd_application_path: "162445_MIDDLEWARE_CLIENT_ESB"
      # Slot 5 * = node (aggregate nodes dropped by instance_include);
      # slot 7 * = queue name; literal leaf keeps only depth rows.
      metric_path: "Application Infrastructure Performance|MCAG|Custom Metrics|WebsphereMQ|*|Queues|*|Current Queue Depth"
      controllers_database: PBWM
      controllers_collection: Controllers

    dimensions:
      environment: production
      csi: 162445
      csi: 162445
      application: AO
      component: Queue
