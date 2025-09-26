def get_pods_for_deployment(v1_client, namespace, deployment_name):
    """Fetches pods associated with a specific deployment."""
    try:
        # Get the deployment to extract its selector labels
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        selector_labels = deployment.spec.selector.match_labels

        # Convert selector_labels dict to a label_selector string
        label_selector = ",".join([f"{k}={v}" for k, v in selector_labels.items()])

        # List pods matching the selector
        pods = v1_client.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        return pods.items
    except ApiException as e:
        print(f"Error fetching pods for deployment '{deployment_name}': {e}")
        return []

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

    # 1. Fetch pods inside a deployment
    print(f"Fetching pods for deployment '{DEPLOYMENT_NAME}'...")
    pods = get_pods_for_deployment(v1, NAMESPACE_NAME, DEPLOYMENT_NAME)
    if pods:
        print(f"Found {len(pods)} pods for deployment '{DEPLOYMENT_NAME}':")
        for pod in pods:
            print(f"  - {pod.metadata.name} (Status: {pod.status.phase})")
    else:
        print(f"No pods found for deployment '{DEPLOYMENT_NAME}'.")

    # 2. Restart (delete) pods inside a deployment
    if pods:
        print(f"\nAttempting to restart (delete) all pods in deployment '{DEPLOYMENT_NAME}'...")
        for pod in pods:
            delete_pod(v1, NAMESPACE_NAME, pod.metadata.name)
        print("Pods deletion initiated. Deployment controller will create new ones.")
    else:
        print(f"No pods to restart for deployment '{DEPLOYMENT_NAME}'.")
