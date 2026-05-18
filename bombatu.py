{
  "account_id": "034362034659",
  "account_name": "GCB-173812-PRD-RESPROD",
  "cluster_name": "gcb-resprod-us-east-1-prd-eks-kgls",
  "csi": "173812",
  "sector": "gcb",
  "environment": "prod",
  "namespace": "gcb-nam-prd-res-173812",
  "object_type": "deployment",
  "object_name": "rtl-ogn-c-rateentry-gt1prod",
  "operation": "restart pods",
  "region": "us-east-1",
  "incident_number": "INC0016455649",
  "reference_id": "069249d8-a187-7429-8000-d626078c5f08",
  "response_code": 200,
  "response": {
    "cluster_name": "gcb-resprod-us-east-1-prd-eks-kgls",
    "namespace": "gcb-nam-prd-res-173812",
    "object_name": "rtl-ogn-c-rateentry-gt1prod",
    "object_type": "deployment",
    "delete_pod_responses": [
      {
        "pod_name": "rtl-ogn-c-rateentry-gt1prod-5fdfb7c7f7-b6nbr",
        "response": "Pod 'gcb-resprod-us-east-1-prd-eks-kgls/gcb-nam-prd-res-173812/rtl-ogn-c-rateentry-gt1prod/rtl-ogn-c-rateentry-gt1prod-5fdfb7c7f7-b6nbr' deleted successfully with policy 'graceful' and grace period of 30 seconds.",
        "http_code": 200
      }
    ]
  },
  "status": "success",
  "user_id": "nd66466",
  "log_datetime": {
    "$date": "2025-11-24T18:02:06.090Z"
  },
  "restart_type": "graceful",
  "pod_names": [
    "rtl-ogn-c-rateentry-gt1prod-5fdfb7c7f7-b6nbr"
  ]
}

{
  "_id": "ObjectId('6a09c65cdd471867dc7d00d3')",
  "sector": "Not Available",
  "region": "APAC",
  "domain": "CITI GLOBAL WEALTH",
  "lob": "NA",
  "environment": "JPPROD2",
  "csi_application_id": "179054",
  "application": "Not Available",
  "cluster_name": "apcgcbljpd23p",
  "project": "gcb-pb-emeqd-p-179054",
  "object_type": "deployment",
  "object_name": "wmt-v-pricinginterface-eqd-wm-em",
  "pods": "All Pods",
  "replicas": 2,
  "status": "Started",
  "operation_type": "deployment start",
  "incident": "Not Available",
  "snow_primary_application": "Not Available",
  "snow_incident_group": "Not Available",
  "reference_id": "AMP4df6f3ac8e224b22902478465e7bf848",
  "user": "mg99750",
  "log_date": "2026-05-17T13:45:00.011+00:00"
}