import boto3
import base64
import datetime
from botocore.signers import RequestSigner
from kubernetes import client, config

# --- AWS credentials & settings ---
AWS_ACCESS_KEY_ID = "your_access_key_id"
AWS_SECRET_ACCESS_KEY = "your_secret_access_key"
AWS_SESSION_TOKEN = "your_session_token"
REGION = "your_region"
CLUSTER_NAME = "your_cluster_name"
NAMESPACE = "your_namespace"

# --- Step 1: Get EKS cluster info ---
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=REGION,
)
eks = session.client("eks")
cluster_info = eks.describe_cluster(name=CLUSTER_NAME)["cluster"]

endpoint = cluster_info["endpoint"]
cert = cluster_info["certificateAuthority"]["data"]

# --- Step 2: Generate token for authentication ---
def get_bearer_token(cluster_name: str, region: str, session: boto3.Session) -> str:
    service_id = "sts"
    signer = RequestSigner(
        service_id,
        region,
        service_id,
        "v4",
        session.get_credentials(),
        session.events,
    )

    params = {
        "method": "GET",
        "url": f"https://sts.{region}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
        "body": {},
        "headers": {"x-k8s-aws-id": cluster_name},
        "context": {},
    }

    signed_url = signer.generate_presigned_url(
        params,
        region_name=region,
        expires_in=60,
        operation_name="",
    )

    # EKS expects base64 encoded URL token
    token = "k8s-aws-v1." + base64.urlsafe_b64encode(signed_url.encode()).decode().rstrip("=")
    return token

token = get_bearer_token(CLUSTER_NAME, REGION, session)

# --- Step 3: Configure Kubernetes client ---
kube_config = client.Configuration()
kube_config.host = endpoint
kube_config.verify_ssl = True
kube_config.ssl_ca_cert = None

# Write cert to temp file
import tempfile
with tempfile.NamedTemporaryFile(delete=False) as ca_file:
    ca_file.write(base64.b64decode(cert))
    kube_config.ssl_ca_cert = ca_file.name

kube_config.api_key = {"authorization": "Bearer " + token}
client.Configuration.set_default(kube_config)

apps_v1 = client.AppsV1Api()
core_v1 = client.CoreV1Api()

# --- Step 4: List deployments ---
print(f"📦 Deployments in namespace '{NAMESPACE}':")
deployments = apps_v1.list_namespaced_deployment(namespace=NAMESPACE)
for d in deployments.items:
    print(f" - {d.metadata.name}")

# --- Step 5: Restart the first deployment (as example) ---
if deployments.items:
    deployment_name = deployments.items[0].metadata.name
    print(f"\n🔄 Restarting deployment: {deployment_name}")
    body = {
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
    apps_v1.patch_namespaced_deployment(
        name=deployment_name,
        namespace=NAMESPACE,
        body=body
    )
    print("✅ Deployment restarted.")

    # --- Step 6: Restart a pod by deleting it ---
    pods = core_v1.list_namespaced_pod(
        namespace=NAMESPACE,
        label_selector=f"app={deployment_name}"
    )
    if pods.items:
        pod_name = pods.items[0].metadata.name
        print(f"🗑️ Deleting pod: {pod_name}")
        core_v1.delete_namespaced_pod(name=pod_name, namespace=NAMESPACE)
        print("✅ Pod deleted (will restart automatically).")
    else:
        print("⚠️ No pods found for that deployment.")
else:
    print("⚠️ No deployments found in this namespace.")