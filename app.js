import boto3
import base64
import tempfile
from kubernetes import client
from botocore.signers import RequestSigner
import os

# ----------- Your AWS EKS details -----------
AWS_ACCESS_KEY_ID = "YOUR_KEY_ID"
AWS_SECRET_ACCESS_KEY = "YOUR_SECRET_KEY"
AWS_SESSION_TOKEN = "YOUR_SESSION_TOKEN"

CLUSTER_NAME = "your-cluster"
REGION = "us-east-1"

# ----------- Proxy settings -----------
USE_PROXY = True   # <--- flip this to False if running outside corporate network

HTTP_PROXY = "http://your.proxy.corp:8080"
HTTPS_PROXY = "http://your.proxy.corp:8080"
NO_PROXY = "localhost,127.0.0.1,169.254.169.254,.cluster.local"

# ----------- Step 1: Configure boto3 session -----------
boto_config = None

if USE_PROXY:
    os.environ["HTTP_PROXY"] = HTTP_PROXY
    os.environ["HTTPS_PROXY"] = HTTPS_PROXY
    os.environ["NO_PROXY"] = NO_PROXY

    boto_config = boto3.session.Config(
        proxies={
            "http": HTTP_PROXY,
            "https": HTTPS_PROXY
        }
    )
else:
    # clear any inherited proxy env vars
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]:
        os.environ.pop(var, None)

session = boto3.session.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=REGION
)

eks = session.client("eks", config=boto_config) if boto_config else session.client("eks")

# ----------- Step 2: Get cluster info -----------
cluster_info = eks.describe_cluster(name=CLUSTER_NAME)["cluster"]
endpoint = cluster_info["endpoint"]
ca_data = cluster_info["certificateAuthority"]["data"]

# ----------- Step 3: Generate auth token (IAM signed) -----------
service_id = eks.meta.service_model.service_id
signer = RequestSigner(
    service_id,
    REGION,
    "sts",
    "v4",
    session.get_credentials(),
    session.events,
)

signed_url = signer.generate_presigned_url(
    request_dict={
        "method": "GET",
        "url": f"https://sts.{REGION}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
        "headers": {"x-k8s-aws-id": CLUSTER_NAME},
        "body": b"",
        "query_string": {},
    },
    operation_name="",
    expires_in=60,
)

token = "k8s-aws-v1." + base64.urlsafe_b64encode(
    signed_url.encode("utf-8")
).decode("utf-8").rstrip("=")

# ----------- Step 4: Configure Kubernetes client -----------
configuration = client.Configuration()
configuration.host = endpoint
configuration.verify_ssl = True
configuration.api_key = {"authorization": "Bearer " + token}

# write CA cert to temp file
ca_cert_bytes = base64.b64decode(ca_data)
with tempfile.NamedTemporaryFile(delete=False) as ca_file:
    ca_file.write(ca_cert_bytes)
    configuration.ssl_ca_cert = ca_file.name

# If using proxy, let urllib3 use env vars. If not, bypass explicitly.
if USE_PROXY:
    configuration.proxy = None  # cluster API bypasses proxy thanks to NO_PROXY
else:
    configuration.proxy = None  # no proxy at all

client.Configuration.set_default(configuration)

# ----------- Step 5: Query Deployments & StatefulSets -----------
v1_core = client.CoreV1Api()
v1_apps = client.AppsV1Api()

namespaces = [ns.metadata.name for ns in v1_core.list_namespace().items]

for ns in namespaces:
    print(f"\nNamespace: {ns}")
    deployments = v1_apps.list_namespaced_deployment(ns)
    statefulsets = v1_apps.list_namespaced_stateful_set(ns)

    for d in deployments.items:
        print(f"  Deployment: {d.metadata.name}")
    for s in statefulsets.items:
        print(f"  StatefulSet: {s.metadata.name}")
