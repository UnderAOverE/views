{
  "client": "EAMP-Selfservice",
  "cluster_name": "namgcbswd40p",
  "csi_information": {
    "application_name": "IPA Application Suite - GCB NA",
    "application_manager": "P Jayasri",
    "application_manager_soeid": "JP54880",
    "business": "USPB",
    "csi": "170514",
    "domain": "NAM_Core",
    "lob": "CITI CARDS",
    "region": "NAM",
    "sector": "PBWM",
    "sub_domain": "ATMPegaConAI",
    "sub_sector": "PB",
    "technology_managed_segment_L6": "Consumer Operations Tech [L6]",
    "technology_managed_segment_L7": "AI & Automation [L7]"
  },
  "datacenter": "SWDC",
  "details": {
    "grace_period_seconds": 30,
    "operation_type": "restart",
    "platform": "ose",
    "pods_restart": true,
    "restart_type": "graceful"
  },
  "environment": "SW1PROD",
  "log_datetime": {
    "$date": "2026-05-16T15:31:03.215Z"
  },
  "namespace": "gcb-nam-rsk-ipa-170514",
  "object_name": "swlecsprod-elm-o-fraudevaluation-info",
  "object_type": "deployment",
  "operation_duration_seconds": 0.16,
  "pods": [
    "swlecsprod-elm-o-fraudevaluation-info-6fdd9b486b-5874f",
    "swlecsprod-elm-o-fraudevaluation-info-6fdd9b486b-rz5k7"
  ],
  "reason": "service to service token failure",
  "reference_id": "06a088db-70e0-7f3b-8000-7eb49e67267b",
  "saas_ticket_number": "INC0022545945",
  "status": "success",
  "summary": [
    "Successfully authenticated with cluster namgcbswd40p",
    "Pods operation (restart) successful.",
    "Successfully initiated restart for pod swlecsprod-elm-o-fraudevaluation-info-6fdd9b486b-5874f;",
    "Successfully initiated restart for pod swlecsprod-elm-o-fraudevaluation-info-6fdd9b486b-rz5k7",
    "Notification email sent to Sivakumar, Parithy regarding pod restart operation."
  ],
  "user_id": "PS02336"
}