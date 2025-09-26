import base64
import boto3
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from botocore.signers import RequestSigner
import datetime
import os
import time # For sleep

# --- Configuration (replace with your actual values) ---
CLUSTER_NAME = "your-eks-cluster-name"
NAMESPACE_NAME = "default" # or your application's namespace
STATEFULSET_NAME = "your-statefulset-name" # e.g., "my-database"
REGION_NAME = "your-aws-region"
EKS_ENDPOINT = "https://your-eks-cluster-endpoint" # e.g., from `aws eks describe-cluster`
# CA_DATA should be the base64 encoded certificate authority data from `aws eks describe-cluster`
CA_DATA = "your-base64-encoded-ca-data"
# --------------------------------------------------------

# (Include the get_kube_api_client function here as it's required)
def get_kube_api_client(cluster_name, region_name, endpoint, ca_data):
    """
    Configures and returns a Kubernetes API client for an EKS cluster.
    """
    
    STS_TOKEN_EXPIRES_IN = 60 # Seconds
    session = boto3.session.Session(region_name=region_name)
    client_id = cluster_name
    
    service_id = session.get_service_data('sts')['signingName']
    signer = RequestSigner(
        service_id,
        region_name,
        'get-caller-identity',
        session.get_credentials(),
        session.events
    )

    token_parameters = {
        'method': 'GET',
        'url': f'https://sts.{region_name}.amazonaws.com/?Action=GetCallerIdentity&Version=2010-09-09',
        'headers': {
            'x-k8s-aws-id': client_id
        },
        'body': {},
        'query_string': {}
    }

    signed_url = signer.generate_presigned_url(
        token_parameters,
        expiration_in_seconds=STS_TOKEN_EXPIRES_IN
    )

    token = 'k8s-aws-v1.' + base64.urlsafe_b64encode(
        signed_url.encode('utf-8')
    ).decode('utf-8').rstrip('=')

    configuration = client.Configuration()
    configuration.host = endpoint
    configuration.api_key = {"authorization": f"Bearer {token}"}
    
    # Handle CA_DATA decoding and temporary file writing
    try:
        configuration.ssl_ca_cert = base64.b64decode(ca_data).decode('utf-8')
    except (base64.binascii.Error, UnicodeDecodeError):
        configuration.ssl_ca_cert = ca_data
        
    if isinstance(configuration.ssl_ca_cert, str) and '\n' in configuration.ssl_ca_cert:
        temp_ca_path = os.path.join(os.getcwd(), f"{cluster_name}_ca.crt")
        with open(temp_ca_path, "w") as f:
            f.write(configuration.ssl_ca_cert)
        configuration.ssl_ca_cert = temp_ca_path


    client.Configuration.set_default(configuration)
    
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    
    return v1, apps_v1


def scale_statefulset(apps_v1_client, namespace, statefulset_name, replicas):
    """Scales a Kubernetes StatefulSet to the specified number of replicas."""
    try:
        # Patching only the replicas field of the scale subresource
        patch_body = {"spec": {"replicas": replicas}}
        api_response = apps_v1_client.patch_namespaced_stateful_set_scale(
            name=statefulset_name, namespace=namespace, body=patch_body
        )
        print(f"StatefulSet '{statefulset_name}' in namespace '{namespace}' scaled to {replicas} replicas.")
    except ApiException as e:
        print(f"Error scaling StatefulSet '{statefulset_name}': {e}")
        if e.status == 404:
            print(f"StatefulSet '{statefulset_name}' not found in namespace '{namespace}'.")
        elif e.status == 403:
            print(f"Access denied for scaling StatefulSet. Check IAM/RBAC permissions.")

def restart_statefulset(apps_v1_client, namespace, statefulset_name):
    """
    Restarts a Kubernetes StatefulSet by patching its spec with a new annotation,
    forcing a rollout.
    
    Note: StatefulSet rollouts are ordered. Pods are updated one-by-one in
    reverse ordinal order for rolling updates (e.g., web-2, web-1, web-0).
    """
    try:
        statefulset = apps_v1_client.read_namespaced_stateful_set(name=statefulset_name, namespace=namespace)
        
        if not statefulset.spec.template.metadata.annotations:
            statefulset.spec.template.metadata.annotations = {}
        
        # Add or update a unique annotation to force a rollout
        statefulset.spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"] = \
            datetime.datetime.utcnow().isoformat() + "Z"

        api_response = apps_v1_client.patch_namespaced_stateful_set(
            name=statefulset_name, namespace=namespace, body=statefulset
        )
        print(f"StatefulSet '{statefulset_name}' in namespace '{namespace}' restarted successfully.")
    except ApiException as e:
        print(f"Error restarting StatefulSet '{statefulset_name}': {e}")
        if e.status == 404:
            print(f"StatefulSet '{statefulset_name}' not found in namespace '{namespace}'.")
        elif e.status == 403:
            print(f"Access denied for restarting StatefulSet. Check IAM/RBAC permissions.")


# --- Example Usage for StatefulSet Management ---
if __name__ == "__main__":
    v1, apps_v1 = get_kube_api_client(CLUSTER_NAME, REGION_NAME, EKS_ENDPOINT, CA_DATA)

    print("\n--- StatefulSet Operations ---")

    # 1. Stop a StatefulSet (scale to 0 replicas)
    print(f"Attempting to stop StatefulSet '{STATEFULSET_NAME}'...")
    scale_statefulset(apps_v1, NAMESPACE_NAME, STATEFULSET_NAME, 0)
    time.sleep(10) # Give Kubernetes some time to process ordered termination

    # 2. Start a StatefulSet (scale to desired replicas, e.g., 3)
    print(f"\nAttempting to start StatefulSet '{STATEFULSET_NAME}' (scale to 3 replicas)...")
    scale_statefulset(apps_v1, NAMESPACE_NAME, STATEFULSET_NAME, 3)
    time.sleep(10) # Give Kubernetes some time to process ordered creation

    # 3. Restart a StatefulSet
    print(f"\nAttempting to restart StatefulSet '{STATEFULSET_NAME}'...")
    restart_statefulset(apps_v1, NAMESPACE_NAME, STATEFULSET_NAME)
    time.sleep(10) # Give Kubernetes some time for the ordered rollout
