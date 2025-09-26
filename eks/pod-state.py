# (Include get_kube_api_client, get_pod_details, delete_pod functions here as they are required)

def get_pods_for_statefulset(v1_client, apps_v1_client, namespace, statefulset_name):
    """Fetches pods associated with a specific StatefulSet."""
    try:
        # Get the StatefulSet to extract its selector labels
        statefulset = apps_v1_client.read_namespaced_stateful_set(name=statefulset_name, namespace=namespace)
        selector_labels = statefulset.spec.selector.match_labels

        # Convert selector_labels dict to a label_selector string
        label_selector = ",".join([f"{k}={v}" for k, v in selector_labels.items()])

        # List pods matching the selector
        pods = v1_client.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        return pods.items
    except ApiException as e:
        print(f"Error fetching pods for StatefulSet '{statefulset_name}': {e}")
        return []

# --- Example Usage for Pod Management (StatefulSet) ---
if __name__ == "__main__":
    v1, apps_v1 = get_kube_api_client(CLUSTER_NAME, REGION_NAME, EKS_ENDPOINT, CA_DATA)

    print("\n--- StatefulSet Pod Operations ---")

    # 1. Fetch pods inside a StatefulSet with detailed info
    print(f"Fetching detailed pods for StatefulSet '{STATEFULSET_NAME}'...")
    pods = get_pods_for_statefulset(v1, apps_v1, NAMESPACE_NAME, STATEFULSET_NAME)
    
    if pods:
        print(f"Found {len(pods)} pods for StatefulSet '{STATEFULSET_NAME}':")
        # Sort pods by name to respect ordinal order
        pods.sort(key=lambda p: p.metadata.name)
        for pod in pods:
            pod_details = get_pod_details(pod) # Re-using the get_pod_details function
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
        print(f"No pods found for StatefulSet '{STATEFULSET_NAME}'.")

    # 2. Restart (delete) pods inside a StatefulSet
    # Note: For StatefulSets, deleting pods will cause them to be recreated
    # in *ordinal order*, which might not be immediate for subsequent pods.
    if pods:
        print(f"\nAttempting to restart (delete) all pods in StatefulSet '{STATEFULSET_NAME}'...")
        # Deleting pods in reverse ordinal order might be safer for some stateful applications
        # but the StatefulSet controller handles recreation gracefully in any case.
        pods.sort(key=lambda p: p.metadata.name, reverse=True) 
        for pod in pods:
            delete_pod(v1, NAMESPACE_NAME, pod.metadata.name)
            time.sleep(2) # Add a small delay for StatefulSet controller to catch up
        print("Pods deletion initiated. StatefulSet controller will create new ones in ordinal order.")
    else:
        print(f"No pods to restart for StatefulSet '{STATEFULSET_NAME}'.")




"""
Important Considerations for StatefulSets:
Ordered Operations: When scaling down, StatefulSets terminate pods in reverse ordinal order (web-2, then web-1, then web-0). When scaling up, they create pods in ordinal order (web-0, then web-1, then web-2). This ordering is crucial for many stateful applications.
Restarting Strategy:
Patching Annotation (Recommended): This triggers a graceful rolling update. Pods are updated one by one, typically in reverse ordinal order, respecting readiness probes. This is the safest way to "restart" a StatefulSet.
Deleting Individual Pods: While technically possible, be cautious. Deleting a pod will immediately trigger the StatefulSet controller to recreate it. If you delete many pods simultaneously, it might lead to a temporary outage or data inconsistency if your application isn't designed for it. The controller will still recreate them in ordinal order.
Graceful Shutdown: Ensure your pods have proper terminationGracePeriodSeconds and handle SIGTERM signals so they can gracefully shut down before being forcefully terminated.
Readiness Probes: Well-configured readiness probes are essential for StatefulSets. Kubernetes uses them to determine when a new pod is ready before proceeding with the next ordered operation.


Key Differences for StatefulSets:
Stable Network Identifiers and Storage: StatefulSets give each Pod a stable hostname and automatically manage PersistentVolumeClaims (PVCs) for persistent storage.
Ordered Deployments/Scaling: Pods in a StatefulSet are created, scaled, and deleted in a strict ordinal order (e.g., web-0, web-1, web-2).
No Direct "Restart": Like Deployments, there's no direct "restart" API call for a StatefulSet. Restarting means forcing a new rollout of its pods."""
