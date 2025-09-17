import httpx
import asyncio
import json
from typing import List, Dict, Any, Optional, Union, Tuple

# Define a type alias for clarity
EKSClusterInfo = Dict[str, str] # e.g., {"application_id": "app1", "environment": "dev", ...}
ServiceResponse = Union[Dict[str, Any], str] # A dict if JSON, else a string

# --- Configuration ---
BASE_SERVICE_URL = "https://service-uat.com"
# BASE_SERVICE_URL = "https://httpbin.org/anything" # Use httpbin for testing if service-uat.com isn't available
# PROXY_URL = "http://your.proxy.server:8080" # Uncomment and set if you need a proxy
PROXY_URL = None # Set to None if no proxy
SSL_VERIFY = False # Set to True in production if certificates are properly handled

# Define client configuration (e.g., timeouts, default headers)
# Assuming you're on a newer httpx version where 'proxies' is accepted by AsyncClient
CLIENT_DEFAULTS = {
    "verify": SSL_VERIFY,
    "timeout": httpx.Timeout(10.0, connect=5.0) # 10 seconds total, 5 seconds to connect
}
if PROXY_URL:
    CLIENT_DEFAULTS["proxies"] = PROXY_URL


async def fetch_cluster_data(
    client: httpx.AsyncClient,
    cluster_info: EKSClusterInfo
) -> Tuple[EKSClusterInfo, Optional[ServiceResponse], Optional[str]]:
    """
    Fetches data for a single EKS cluster from the service endpoint.

    Args:
        client: An initialized httpx.AsyncClient instance.
        cluster_info: A dictionary containing "application_id", "environment",
                      "region", and "cluster_id" for a single cluster.

    Returns:
        A tuple: (original_cluster_info, response_data, error_message).
        response_data will be None if an error occurred.
        error_message will be None if successful.
    """
    # Construct the URL from cluster_info
    # Using .format() or f-strings for URL construction
    # Make sure all keys are present in cluster_info to avoid KeyError
    try:
        url = (
            f"{BASE_SERVICE_URL}/"
            f"{cluster_info['environment']}/"
            f"{cluster_info['region']}/"
            f"{cluster_info['cluster_id']}/"
            f"{cluster_info['application_id']}"
        )
    except KeyError as e:
        error_msg = f"Missing key in cluster_info: {e}"
        print(f"Error for cluster {cluster_info}: {error_msg}")
        return cluster_info, None, error_msg

    headers = {
        "User-Agent": "EKSClusterServiceFetcher/1.0",
        "Accept": "application/json"
    }

    try:
        # Perform the GET request
        response = await client.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for 4xx/5xx responses

        # Try to parse response as JSON, otherwise return text
        if response.headers.get('content-type', '').startswith('application/json'):
            return cluster_info, response.json(), None
        else:
            # Handle non-JSON responses if necessary, e.g., plain text or HTML
            print(f"Warning: Non-JSON response for {url}. Status: {response.status_code}")
            return cluster_info, response.text, None

    except httpx.RequestError as exc:
        error_msg = f"Network error during request to {url!r}: {exc}"
        print(f"Error: {error_msg}")
        return cluster_info, None, error_msg
    except httpx.HTTPStatusError as exc:
        error_msg = (
            f"HTTP error {exc.response.status_code} "
            f"while requesting {exc.request.url!r}: {exc.response.text}"
        )
        print(f"Error: {error_msg}")
        return cluster_info, None, error_msg
    except json.JSONDecodeError:
        error_msg = f"Failed to decode JSON response from {url!r}. Response: {response.text[:100]}..."
        print(f"Error: {error_msg}")
        return cluster_info, None, error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred for {url!r}: {type(e).__name__}: {e}"
        print(f"Error: {error_msg}")
        return cluster_info, None, error_msg


async def get_all_eks_cluster_data(
    eks_clusters: List[EKSClusterInfo]
) -> List[Tuple[EKSClusterInfo, Optional[ServiceResponse], Optional[str]]]:
    """
    Fetches data for multiple EKS clusters concurrently.

    Args:
        eks_clusters: A list of dictionaries, each containing EKS cluster information.

    Returns:
        A list of tuples. Each tuple contains:
        (original_cluster_info, response_data_or_None, error_message_or_None).
    """
    if not eks_clusters:
        print("No EKS clusters provided to fetch data for.")
        return []

    async with httpx.AsyncClient(**CLIENT_DEFAULTS) as client:
        # Create a list of coroutine objects (tasks) to run concurrently
        tasks = [
            fetch_cluster_data(client, cluster_info)
            for cluster_info in eks_clusters
        ]

        # Run all tasks concurrently and gather their results
        # return_exceptions=True allows all tasks to complete, even if some raise exceptions.
        # Exceptions are then returned as results in the list, rather than stopping asyncio.gather.
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results: List[Tuple[EKSClusterInfo, Optional[ServiceResponse], Optional[str]]] = []

        # Process results, handling any exceptions returned by return_exceptions=True
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # If an exception was returned by asyncio.gather, it means something went very wrong
                # or a bug in fetch_cluster_data. fetch_cluster_data should handle its own exceptions.
                # This block serves as a final fallback.
                cluster_info = eks_clusters[i]
                error_msg = f"Unhandled exception for cluster {cluster_info}: {type(result).__name__}: {result}"
                print(f"Critical Error: {error_msg}")
                processed_results.append((cluster_info, None, error_msg))
            else:
                # Result is a (original_cluster_info, response_data, error_message) tuple
                processed_results.append(result)

        return processed_results


async def main():
    # --- Example Usage ---
    eks_clusters_data: List[EKSClusterInfo] = [
        {"application_id": "app1", "environment": "dev", "region": "us-east-1", "cluster_id": "eks-dev-1"},
        {"application_id": "app2", "environment": "prod", "region": "us-west-2", "cluster_id": "eks-prod-2"},
        {"application_id": "app3", "environment": "qa", "region": "eu-central-1", "cluster_id": "eks-qa-3"},
        # Example with a missing key to test error handling
        {"application_id": "app4", "environment": "staging", "region": "ap-south-1"},
        # Example that might fail (e.g., 404 on httpbin)
        {"application_id": "failapp", "environment": "nonexistent", "region": "nonexistent", "cluster_id": "fail-cluster"},
    ]

    print("Starting fetching EKS cluster data...")
    all_results = await get_all_eks_cluster_data(eks_clusters_data)
    print("\n--- All EKS Cluster Data Fetched ---")

    for original_info, response_data, error_msg in all_results:
        print(f"\nCluster: {original_info}")
        if error_msg:
            print(f"  Status: FAILED - {error_msg}")
        elif response_data:
            print("  Status: SUCCESS")
            if isinstance(response_data, dict):
                # print(f"  Data: {json.dumps(response_data, indent=2)}")
                print(f"  Data keys: {list(response_data.keys())}") # Print just keys for brevity
            else:
                print(f"  Data (Text): {response_data[:100]}...")
        else:
            print("  Status: FAILED - No data and no specific error message provided.")


if __name__ == "__main__":
    asyncio.run(main())

