import base64
import boto3
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from botocore.signers import RequestSigner
import datetime
import os

# --- Configuration (replace with your actual values) ---
CLUSTER_NAME = "your-eks-cluster-name"
NAMESPACE_NAME = "default" # or your application's namespace
DEPLOYMENT_NAME = "your-deployment-name"
REGION_NAME = "your-aws-region"
EKS_ENDPOINT = "https://your-eks-cluster-endpoint" # e.g., from `aws eks describe-cluster`
# CA_DATA should be the base64 encoded certificate authority data from `aws eks describe-cluster`
CA_DATA = "your-base64-encoded-ca-data"
# --------------------------------------------------------

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

def get_pods_for_deployment(v1_client, apps_v1_client, namespace, deployment_name):
    """Fetches pods associated with a specific deployment."""
    try:
        # Get the deployment to extract its selector labels
        deployment = apps_v1_client.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        selector_labels = deployment.spec.selector.match_labels

        # Convert selector_labels dict to a label_selector string
        label_selector = ",".join([f"{k}={v}" for k, v in selector_labels.items()])

        # List pods matching the selector
        pods = v1_client.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        return pods.items
    except ApiException as e:
        print(f"Error fetching pods for deployment '{deployment_name}': {e}")
        return []


def get_pod_details(pod: client.V1Pod):
    """
    Extracts detailed information from a V1Pod object.
    """
    details = {
        "pod_name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "uid": pod.metadata.uid,
        "status": pod.status.phase,
        "node_name": pod.spec.node_name if pod.spec and pod.spec.node_name else "N/A",
        "start_time": pod.status.start_time.isoformat() if pod.status and pod.status.start_time else "N/A",
        "containers_count": len(pod.spec.containers) if pod.spec and pod.spec.containers else 0,
        "containers_info": [],
        "pod_ip": pod.status.pod_ip if pod.status and pod.status.pod_ip else "N/A",
        "host_ip": pod.status.host_ip if pod.status and pod.status.host_ip else "N/A",
        "reason": pod.status.reason if pod.status and pod.status.reason else "N/A",
        "message": pod.status.message if pod.status and pod.status.message else "N/A",
    }

    # Extract container-specific information
    if pod.status and pod.status.container_statuses:
        for container_status in pod.status.container_statuses:
            container_detail = {
                "name": container_status.name,
                "image": container_status.image,
                "ready": container_status.ready,
                "restart_count": container_status.restart_count,
                "state": "N/A",
                "last_state": "N/A"
            }
            
            # Determine current state
            if container_status.state:
                if container_status.state.running:
                    container_detail["state"] = f"Running (started: {container_status.state.running.started_at.isoformat()})"
                elif container_status.state.waiting:
                    container_detail["state"] = f"Waiting ({container_status.state.waiting.reason}: {container_status.state.waiting.message})"
                elif container_status.state.terminated:
                    container_detail["state"] = f"Terminated ({container_status.state.terminated.reason} code {container_status.state.terminated.exit_code})"
            
            # Determine last state if available
            if container_status.last_state:
                if container_status.last_state.running:
                    container_detail["last_state"] = f"Running (started: {container_status.last_state.running.started_at.isoformat()})"
                elif container_status.last_state.waiting:
                    container_detail["last_state"] = f"Waiting ({container_status.last_state.waiting.reason})"
                elif container_status.last_state.terminated:
                    container_detail["last_state"] = f"Terminated ({container_status.last_state.terminated.reason} code {container_status.last_state.terminated.exit_code} finished: {container_status.last_state.terminated.finished_at.isoformat()})"

            details["containers_info"].append(container_detail)
            
    # "Short name" is not a standard Kubernetes field. 
    # Often, people use the pod name or a truncated version.
    # If you mean something specific, you'd need a custom logic here.
    # For now, we'll just use the full pod name.
    details["short_name"] = pod.metadata.name # Or a derived short name if you have a pattern

    return details


def delete_pod(v1_client, namespace, pod_name):
    """Deletes a specific pod."""
    try:
        v1_client.delete_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',  # Ensure dependent objects are cleaned up
                grace_period_seconds=0 # Delete immediately
            )
        )
        print(f"Pod '{pod_name}' deleted successfully.")
    except ApiException as e:
        if e.status == 404:
            print(f"Pod '{pod_name}' not found.")
        else:
            print(f"Error deleting pod '{pod_name}': {e}")


# --- Example Usage for Pod Management ---
if __name__ == "__main__":
    v1, apps_v1 = get_kube_api_client(CLUSTER_NAME, REGION_NAME, EKS_ENDPOINT, CA_DATA)

    print("\n--- Pod Operations ---")

    # 1. Fetch pods inside a deployment with detailed info
    print(f"Fetching detailed pods for deployment '{DEPLOYMENT_NAME}'...")
    pods = get_pods_for_deployment(v1, apps_v1, NAMESPACE_NAME, DEPLOYMENT_NAME)
    
    if pods:
        print(f"Found {len(pods)} pods for deployment '{DEPLOYMENT_NAME}':")
        for pod in pods:
            pod_details = get_pod_details(pod)
            print("--------------------------------------------------")
            print(f"Pod Name: {pod_details['pod_name']}")
            print(f"Namespace: {pod_details['namespace']}")
            print(f"UID: {pod_details['uid']}")
            print(f"Status: {pod_details['status']}")
            print(f"Node Name: {pod_details['node_name']}")
            print(f"Start Time: {pod_details['start_time']}")
            print(f"Pod IP: {pod_details['pod_ip']}")
            print(f"Host IP: {pod_details['host_ip']}")
            print(f"Containers Count: {pod_details['containers_count']}")
            if pod_details['reason'] != 'N/A':
                print(f"Reason: {pod_details['reason']}")
            if pod_details['message'] != 'N/A':
                print(f"Message: {pod_details['message']}")

            print("  Containers Info:")
            for container in pod_details['containers_info']:
                print(f"    - Name: {container['name']}")
                print(f"      Image: {container['image']}")
                print(f"      Ready: {container['ready']}")
                print(f"      Restart Count: {container['restart_count']}")
                print(f"      State: {container['state']}")
                if container['last_state'] != 'N/A':
                    print(f"      Last State: {container['last_state']}")
            print("--------------------------------------------------")
    else:
        print(f"No pods found for deployment '{DEPLOYMENT_NAME}'.")

    # 2. Restart (delete) pods inside a deployment
    # This section remains the same, as deleting pods is the "restart" action
    # for individual pods within a deployment.
    if pods:
        print(f"\nAttempting to restart (delete) all pods in deployment '{DEPLOYMENT_NAME}'...")
        for pod in pods:
            delete_pod(v1, NAMESPACE_NAME, pod.metadata.name)
        print("Pods deletion initiated. Deployment controller will create new ones.")
    else:
        print(f"No pods to restart for deployment '{DEPLOYMENT_NAME}'.")
