

import requests
import urllib3
from datetime import datetime

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_detailed_status(api_url, token, namespace, name, resource_type="deployments"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # 1. Get the Deployment/StatefulSet object
    res_url = f"{api_url}/apis/apps/v1/namespaces/{namespace}/{resource_type}/{name}"
    res_resp = requests.get(res_url, headers=headers, verify=False)
    if res_resp.status_code != 200:
        return {"error": f"Resource not found: {res_resp.text}"}
    
    res_data = res_resp.json()

    # 2. Get the Pods for this resource to check for crashes/actual start times
    # We use the label selector usually found in the spec
    match_labels = res_data['spec']['selector']['matchLabels']
    selector_query = ",".join([f"{k}={v}" for k, v in match_labels.items()])
    pods_url = f"{api_url}/api/v1/namespaces/{namespace}/pods?labelSelector={selector_query}"
    pods_resp = requests.get(pods_url, headers=headers, verify=False)
    pods_data = pods_resp.json() if pods_resp.status_code == 200 else {"items": []}

    # --- LOGIC TO FIND LAST RESTART ---
    timestamps = []

    # A. Manual restart timestamp (from oc rollout restart / console restart)
    manual_restart = res_data.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {}).get("kubectl.kubernetes.io/restartedAt")
    if manual_restart:
        timestamps.append(manual_restart)

    # B. Last Rollout/Update time
    for cond in res_data.get("status", {}).get("conditions", []):
        if cond.get("type") == "Progressing" and cond.get("lastUpdateTime"):
            timestamps.append(cond.get("lastUpdateTime"))

    # C. Individual Pod Starts and Crashes
    for pod in pods_data.get("items", []):
        # When the pod itself started
        if pod.get("status", {}).get("startTime"):
            timestamps.append(pod["status"]["startTime"])
        
        # If a container crashed and restarted, get the 'finishedAt' time of the previous run
        for container in pod.get("status", {}).get("containerStatuses", []):
            last_state = container.get("lastTerminationState", {}).get("terminated", {})
            if last_state.get("finishedAt"):
                timestamps.append(last_state["finishedAt"])

    # Calculate the most recent timestamp from all sources
    # (Handling ISO format strings by simple max if they are all formatted same)
    last_overall_restart = max(timestamps) if timestamps else "Unknown"

    # --- PREPARE JSON OUTPUT ---
    result = {
        "resource_metadata": {
            "name": name,
            "namespace": namespace,
            "kind": res_data.get("kind"),
            "creation_timestamp": res_data['metadata']['creationTimestamp'],
            "creation_explanation": "This is the date the Deployment object was first created in the cluster. It does not change during restarts or updates."
        },
        "release_details": {
            "image": res_data['spec']['template']['spec']['containers'][0]['image'],
            "version_label": res_data['metadata'].get('labels', {}).get('app.kubernetes.io/version', 'N/A'),
            "generation": res_data['metadata'].get('generation'),
            "observed_generation": res_data.get('status', {}).get('observedGeneration')
        },
        "restart_activity": {
            "last_detected_restart_or_crash": last_overall_restart,
            "manual_rollout_restart_at": manual_restart,
            "pod_count": len(pods_data.get("items", [])),
            "restart_types_monitored": ["crashes", "rollouts", "manual_restarts", "updates"]
        }
    }
    
    return result

# --- EXECUTION ---
URL = "https://api.your-cluster.com:6443"
TOKEN = "sha256~your_token"
NS = "my-namespace"
APP = "my-deployment-name"

final_json = get_detailed_status(URL, TOKEN, NS, APP, "deployments")
print(final_json)
