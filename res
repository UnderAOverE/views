targets:

  - primary_key: AO_Channels_gtdc
    enabled: true
    datacenter: gtdc
    poll_interval_minutes: 5
    lookback_minutes: 8

    # Channel name rides in the metric_name ("MP09.GTPRDDIG01|Status"), so every
    # channel is its own series with NO per-channel config. Do not remove this -
    # without it all channels collapse into one "Status" series per node.
    metric_name_segments: 2

    # Empty = every channel the path returns is kept. New channels onboard
    # themselves; add "<channel>|Status" lines to metric_exclude to mute noisy ones.
    metric_include: []
    metric_exclude: []

    # NODES only - the segment after WebsphereMQ. Host-qualified <host>-<qmgr>
    # pairs; the bare aggregate nodes (GTPRDDIG01 etc.) match nothing here and
    # are dropped. Never list channels in this field.
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
      metric_path: "Application Infrastructure Performance|MCAG|Custom Metrics|WebsphereMQ|*|Channels|*|Status"
      controllers_database: PBWM
      controllers_collection: Controllers

    dimensions:
      environment: production
      csi: 162445
      application: AO
      component: Channel
