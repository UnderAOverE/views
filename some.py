import boto3
import base64
import datetime
import tempfile
import requests
from botocore.signers import RequestSigner

# --- AWS creds ---
AWS_ACCESS_KEY_ID = "your_access_key_id"
AWS_SECRET_ACCESS_KEY = "your_secret_access_key"
AWS_SESSION_TOKEN = "your_session_token"
REGION = "your_region"
CLUSTER_NAME = "your_cluster_name"
NAMESPACE = "aws"   # the namespace you care about

# --- Step 1: Connect to AWS EKS and get cluster info ---
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=REGION,
)
eks = session.client("eks")
cluster_info = eks.describe_cluster(name=CLUSTER_NAME)["cluster"]
endpoint = cluster_info["endpoint"]
ca_data = cluster_info["certificateAuthority"]["data"]

# --- Step 2: Get Bearer token ---
def get_bearer_token(cluster_name: str, region: str, session: boto3.Session) -> str:
    service_id = "sts"
    signer = RequestSigner(
        service_id, region, service_id, "v4",
        session.get_credentials(), session.events,
    )
    params = {
        "method": "GET",
        "url": f"https://sts.{region}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
        "body": {},
        "headers": {"x-k8s-aws-id": cluster_name},
        "context": {},
    }
    signed_url = signer.generate_presigned_url(
        params, region_name=region, expires_in=60, operation_name=""
    )
    token = "k8s-aws-v1." + base64.urlsafe_b64encode(signed_url.encode()).decode().rstrip("=")
    return token

token = get_bearer_token(CLUSTER_NAME, REGION, session)

with tempfile.NamedTemporaryFile(delete=False) as ca_file:
    ca_file.write(base64.b64decode(ca_data))
    ca_cert_path = ca_file.name

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# --- Step 3: Get Deployments & StatefulSets ---
def get_deployments():
    url = f"{endpoint}/apis/apps/v1/namespaces/{NAMESPACE}/deployments"
    resp = requests.get(url, headers=headers, verify=ca_cert_path)
    resp.raise_for_status()
    return resp.json()["items"]

def get_statefulsets():
    url = f"{endpoint}/apis/apps/v1/namespaces/{NAMESPACE}/statefulsets"
    resp = requests.get(url, headers=headers, verify=ca_cert_path)
    resp.raise_for_status()
    return resp.json()["items"]

deployments = get_deployments()
statefulsets = get_statefulsets()

print(f"📦 Deployments in {NAMESPACE}: {[d['metadata']['name'] for d in deployments]}")
print(f"📦 StatefulSets in {NAMESPACE}: {[s['metadata']['name'] for s in statefulsets]}")

# --- Step 4: Get pods for a given controller (Deployment/StatefulSet) ---
def get_pods_for_controller(controller_name):
    url = f"{endpoint}/api/v1/namespaces/{NAMESPACE}/pods"
    resp = requests.get(url, headers=headers, verify=ca_cert_path)
    resp.raise_for_status()
    pods = resp.json()["items"]

    controller_pods = []
    for p in pods:
        owner_refs = p["metadata"].get("ownerReferences", [])
        if any(controller_name in o["name"] for o in owner_refs):
            controller_pods.append(p["metadata"]["name"])
    return controller_pods

# --- Step 5: Actions ---
def restart_controller(controller_type, name):
    url = f"{endpoint}/apis/apps/v1/namespaces/{NAMESPACE}/{controller_type}/{name}"
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": datetime.datetime.utcnow().isoformat()
                    }
                }
            }
        }
    }
    resp = requests.patch(url, headers=headers, json=patch, verify=ca_cert_path)
    resp.raise_for_status()
    print(f"✅ Restarted {controller_type} {name}")

def scale_controller(controller_type, name, replicas):
    url = f"{endpoint}/apis/apps/v1/namespaces/{NAMESPACE}/{controller_type}/{name}/scale"
    patch = {"spec": {"replicas": replicas}}
    resp = requests.patch(url, headers=headers, json=patch, verify=ca_cert_path)
    resp.raise_for_status()
    print(f"✅ Scaled {controller_type} {name} to {replicas} replicas")

def delete_pod(pod_name):
    url = f"{endpoint}/api/v1/namespaces/{NAMESPACE}/pods/{pod_name}"
    resp = requests.delete(url, headers=headers, verify=ca_cert_path)
    resp.raise_for_status()
    print(f"🗑️ Deleted pod {pod_name} (will restart if controlled by a deployment/SS)")

# --- Example usage ---
for d in deployments:
    name = d["metadata"]["name"]
    pods = get_pods_for_controller(name)
    print(f"\nDeployment {name} has pods: {pods}")
    restart_controller("deployments", name)

for s in statefulsets:
    name = s["metadata"]["name"]
    pods = get_pods_for_controller(name)
    print(f"\nStatefulSet {name} has pods: {pods}")
    scale_controller("statefulsets", name, 0)   # stop
    scale_controller("statefulsets", name, 1)   # start back
    




from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class Pod:
    name: str
    owner_kind: str
    owner_name: str

@dataclass
class Controller:
    kind: str            # "Deployment" or "StatefulSet"
    name: str
    replicas: int
    pods: List[Pod]

# --- casting helpers ---
def cast_pod(p: Dict[str, Any]) -> Pod:
    owners = p["metadata"].get("ownerReferences", [])
    if owners:
        owner = owners[0]
        return Pod(
            name=p["metadata"]["name"],
            owner_kind=owner["kind"],
            owner_name=owner["name"],
        )
    else:
        return Pod(name=p["metadata"]["name"], owner_kind="Unknown", owner_name="Unknown")

def cast_controller(obj: Dict[str, Any], kind: str, pods: List[Pod]) -> Controller:
    return Controller(
        kind=kind.capitalize(),  # Deployment or StatefulSet
        name=obj["metadata"]["name"],
        replicas=obj["spec"].get("replicas", 1),
        pods=pods,
    )
    
raw_deployments = list_controllers("deployments")
controllers: List[Controller] = []

for d in raw_deployments:
    pods_raw = get_pods_for_controller(d["metadata"]["name"])
    pods = [cast_pod(p) for p in pods_raw]
    controllers.append(cast_controller(d, "deployment", pods))

# Now you have typed Python objects
for c in controllers:
    print(f"{c.kind} {c.name} → replicas={c.replicas}, pods={[p.name for p in c.pods]}")
    
    

