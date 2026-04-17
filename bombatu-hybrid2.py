{
    "timestamp": "2026-04-17T14:30:00Z",
    "meta": {
        "resource_id": "avi-vs-abc123",
        "resource_kind": "AviVirtualService",
        "resource_name": "prod_cluster1_apps_vs",
        "cluster": "cluster1"
    },
    "metrics": {
        "open_connections": 12847,
        "connections_per_sec": 847.3,
        "avg_bandwidth_kbps": 524800.0,
        "tx_packets_per_sec": 9523.1,
        "request_packets_per_sec": 9210.4
    }
}


{
    "timestamp": "2026-04-17T14:30:00Z",
    "meta": {
        "resource_id": "avi-se-def456",
        "resource_kind": "AviServiceEngine",
        "resource_name": "se-prod-01",
        "se_group": "prod-se-group"
    },
    "metrics": {
        "cpu_usage_pct": 42.7,
        "memory_usage_pct": 61.3,
        "buffer_usage_pct": 18.9,
        "throughput_kbps": 1048200.0,
        "connections": 34210,
        "rx_packets_per_sec": 28410.5,
        "tx_packets_per_sec": 27893.2,
        "rx_packets_drop_per_sec": 0.0
    }
}


{
    "timestamp": "2026-04-17T14:30:00Z",
    "meta": {
        "resource_id": "vm-se-prod-01-moid-1234",
        "resource_kind": "VirtualMachineMetrics",
        "resource_name": "se-prod-01-vm",
        "se_group": "prod-se-group",
        "linked_se_id": "avi-se-def456"    # ties this VM to the Avi SE
    },
    "metrics": {
        "cpu_usage_pct": 38.4,
        "cpu_ready_pct": 2.1,
        "memory_usage_pct": 64.2,
        "memory_balloon_mb": 0.0,
        "memory_swap_in_kbps": 0.0,
        "disk_read_kbps": 120.5,
        "disk_write_kbps": 45.3,
        "disk_latency_read_ms": 1.2,
        "disk_latency_write_ms": 0.8,
        "net_bytes_rx_kbps": 524800.0,
        "net_bytes_tx_kbps": 518200.0,
        "net_packets_dropped": 0.0
    }
}
