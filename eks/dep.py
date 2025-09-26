# --- Configuration (replace with your actual values) ---
CLUSTER_NAME = "your-eks-cluster-name"
NAMESPACE_NAME = "default" # or your application's namespace
DEPLOYMENT_NAME = "your-deployment-name"
REGION_NAME = "your-aws-region"
EKS_ENDPOINT = "https://your-eks-cluster-endpoint" # e.g., from `aws eks describe-cluster`
# CA_DATA should be the base64 encoded certificate authority data from `aws eks describe-cluster`
# Example: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCg..."
CA_DATA = "your-base64-encoded-ca-data"
# --------------------------------------------------------

def scale_deployment(apps_v1_client, namespace, deployment_name, replicas):
    """Scales a Kubernetes deployment to the specified number of replicas."""
    try:
        patch_body = {"spec": {"replicas": replicas}}
        api_response = apps_v1_client.patch_namespaced_deployment_scale(
            name=deployment_name, namespace=namespace, body=patch_body
        )
        print(f"Deployment '{deployment_name}' in namespace '{namespace}' scaled to {replicas} replicas.")
        # print(api_response) # Uncomment for detailed API response
    except ApiException as e:
        print(f"Error scaling deployment '{deployment_name}': {e}")
        if e.status == 404:
            print(f"Deployment '{deployment_name}' not found in namespace '{namespace}'.")
        elif e.status == 403:
            print(f"Access denied for scaling deployment. Check IAM/RBAC permissions.")

def restart_deployment(apps_v1_client, namespace, deployment_name):
    """
    Restarts a Kubernetes deployment by patching its spec with a new annotation,
    forcing a rollout.
    """
    try:
        # Get the current deployment to avoid overwriting other spec details
        deployment = apps_v1_client.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        
        # Patch the deployment with a new annotation in the pod template spec
        # This will trigger a new rollout because the template has changed
        if not deployment.spec.template.metadata.annotations:
            deployment.spec.template.metadata.annotations = {}
        
        # Add or update a unique annotation to force a rollout
        deployment.spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"] = \
            datetime.datetime.utcnow().isoformat() + "Z"

        api_response = apps_v1_client.patch_namespaced_deployment(
            name=deployment_name, namespace=namespace, body=deployment
        )
        print(f"Deployment '{deployment_name}' in namespace '{namespace}' restarted successfully.")
        # print(api_response)
    except ApiException as e:
        print(f"Error restarting deployment '{deployment_name}': {e}")
        if e.status == 404:
            print(f"Deployment '{deployment_name}' not found in namespace '{namespace}'.")
        elif e.status == 403:
            print(f"Access denied for restarting deployment. Check IAM/RBAC permissions.")


# --- Example Usage for Deployment Management ---
if __name__ == "__main__":
    v1, apps_v1 = get_kube_api_client(CLUSTER_NAME, REGION_NAME, EKS_ENDPOINT, CA_DATA)

    print("\n--- Deployment Operations ---")

    # 1. Stop a deployment (scale to 0 replicas)
    print(f"Attempting to stop deployment '{DEPLOYMENT_NAME}'...")
    scale_deployment(apps_v1, NAMESPACE_NAME, DEPLOYMENT_NAME, 0)
    # Give Kubernetes some time to process
    import time
    time.sleep(5) 

    # 2. Start a deployment (scale to desired replicas, e.g., 2)
    print(f"\nAttempting to start deployment '{DEPLOYMENT_NAME}' (scale to 2 replicas)...")
    scale_deployment(apps_v1, NAMESPACE_NAME, DEPLOYMENT_NAME, 2)
    time.sleep(5)

    # 3. Restart a deployment
    print(f"\nAttempting to restart deployment '{DEPLOYMENT_NAME}'...")
    restart_deployment(apps_v1, NAMESPACE_NAME, DEPLOYMENT_NAME)
    time.sleep(5)
