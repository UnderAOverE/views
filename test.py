import asyncio
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient # Assuming MongoDB/DocumentDB

# --- Configuration ---
TOKEN_API_URL = "https://fapis-py:8443/aws/v1/token"
SERVICE_A_URL = "https://serviceA"
SERVICE_B_URL = "https://serviceB"

# AWS EKS Native API base URL (this will be dynamic per endpoint)
# For example, to get deployments in a specific namespace:
# https://<EKS_ENDPOINT>/apis/apps/v1/namespaces/<NAMESPACE>/deployments

# MongoDB/DocumentDB Configuration
MONGO_URI = "mongodb://localhost:27017/" # Replace with your AWS DocumentDB URI
DB_NAME = "your_database_name"
CLUSTERS_COLLECTION = "clusters"
WORKLOADS_COLLECTION = "workloads"

# --- Database Client (single instance) ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client[DB_NAME]
clusters_collection = db[CLUSTERS_COLLECTION]
workloads_collection = db[WORKLOADS_COLLECTION]

# --- Helper Functions ---

async def get_bearer_token(session: aiohttp.ClientSession) -> str:
    """Fetches the bearer token from the token API."""
    try:
        async with session.get(TOKEN_API_URL, ssl=False) as response: # ssl=False for self-signed certs, remove in prod if possible
            response.raise_for_status()
            data = await response.json()
            return data["access_token"]
    except aiohttp.ClientError as e:
        print(f"Error fetching token: {e}")
        raise

async def fetch_service_data(
    session: aiohttp.ClientSession, url: str, token: str
) -> list[dict]:
    """Fetches data from a given service API."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with session.get(url, headers=headers, ssl=False) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        print(f"Error fetching data from {url}: {e}")
        return [] # Return empty list on error for this step

async def fetch_eks_workloads(
    session: aiohttp.ClientSession, eks_endpoint: str, namespace: str, token: str
) -> list[dict]:
    """
    Fetches deployments and statefulsets for a given EKS cluster endpoint and namespace.
    Note: EKS API authentication might be more complex than a simple Bearer token.
    You might need AWS Signature V4 signing. This example assumes a Bearer token
    might work or needs to be adapted.
    """
    headers = {"Authorization": f"Bearer {token}"} # This might need to be replaced with AWS SigV4
    workloads = []

    # Fetch Deployments
    deployments_url = f"https://{eks_endpoint}/apis/apps/v1/namespaces/{namespace}/deployments"
    try:
        async with session.get(deployments_url, headers=headers, ssl=False) as response:
            if response.status == 200:
                data = await response.json()
                for item in data.get("items", []):
                    workloads.append({
                        "type": "deployment",
                        "name": item["metadata"]["name"],
                        "namespace": namespace,
                        "cluster_endpoint": eks_endpoint,
                        "status": item["status"] # Example field
                    })
            else:
                print(f"Warning: Could not fetch deployments for {namespace} on {eks_endpoint}. Status: {response.status}")
    except aiohttp.ClientError as e:
        print(f"Error fetching deployments from {deployments_url}: {e}")

    # Fetch StatefulSets
    statefulsets_url = f"https://{eks_endpoint}/apis/apps/v1/namespaces/{namespace}/statefulsets"
    try:
        async with session.get(statefulsets_url, headers=headers, ssl=False) as response:
            if response.status == 200:
                data = await response.json()
                for item in data.get("items", []):
                    workloads.append({
                        "type": "statefulset",
                        "name": item["metadata"]["name"],
                        "namespace": namespace,
                        "cluster_endpoint": eks_endpoint,
                        "status": item["status"] # Example field
                    })
            else:
                print(f"Warning: Could not fetch statefulsets for {namespace} on {eks_endpoint}. Status: {response.status}")
    except aiohttp.ClientError as e:
        print(f"Error fetching statefulsets from {statefulsets_url}: {e}")

    return workloads


# --- Main Logic ---

async def main():
    async with aiohttp.ClientSession() as session:
        try:
            bearer_token = await get_bearer_token(session)
            print("Token obtained successfully.")
        except Exception:
            print("Failed to obtain bearer token. Exiting.")
            return

        # 2. Call serviceA and serviceB concurrently
        print("Fetching data from Service A and Service B...")
        results_a, results_b = await asyncio.gather(
            fetch_service_data(session, SERVICE_A_URL, bearer_token),
            fetch_service_data(session, SERVICE_B_URL, bearer_token),
        )

        print(f"Service A raw response: {results_a}")
        print(f"Service B raw response: {results_b}")

        # Combine results into responseC
        response_c = []
        # Assuming a way to match accounts to clusters/namespaces.
        # This part requires understanding how accounts_id from serviceA maps to
        # name, namespace, endpoint from serviceB. For now, let's assume a direct mapping
        # or that serviceB entries implicitly belong to an account.
        # This example will just combine them based on available data for simplicity.
        # You'll likely need more complex logic here based on your actual data structure.

        # Let's create a mapping from serviceB for easier lookup, if needed
        service_b_map = {
            (item.get("name"), item.get("namespace")): item
            for item in results_b
            if item.get("name") and item.get("namespace")
        }

        # A more robust combination logic. This assumes 'accounts_id' from ServiceA
        # needs to be associated with an endpoint. Let's create a simplified combination.
        # If serviceA gives accounts and serviceB gives cluster info for those accounts,
        # you'd iterate serviceA results and then find matching serviceB results.
        # For this example, let's assume for each item in serviceB, we find an associated account.
        # This is a critical point where your data's relationship matters.
        
        # Simple combination: take all from serviceB, and try to associate an account_id
        # If serviceA has a list of accounts and serviceB has clusters,
        # you would typically iterate through serviceB's clusters and find their associated account_id
        # based on some common field.

        # Example: Let's just create entries in response_c for each item in serviceB,
        # and if we can, pull an account_id from serviceA.
        # This part is highly dependent on how serviceA and serviceB are structured
        # and how they relate.

        # Let's assume responseB entries are the clusters, and serviceA provides
        # account IDs that need to be linked.
        # For a basic example, let's just create records for each serviceB item,
        # potentially adding an `account_id` if available (e.g., if it's a field in serviceB
        # or can be derived/matched).

        for cluster_info in results_b:
            cluster_name = cluster_info.get("name")
            cluster_namespace = cluster_info.get("namespace")
            cluster_endpoint = cluster_info.get("endpoint")

            if cluster_name and cluster_namespace and cluster_endpoint:
                # Attempt to link an account_id. This is a very simplistic example.
                # You might need a more sophisticated matching logic.
                account_id = None
                if results_a: # Just pick the first account_id from ServiceA for demonstration
                    account_id = results_a[0].get("accounts_id")

                response_c.append({
                    "name": cluster_name,
                    "namespace": cluster_namespace,
                    "endpoint": cluster_endpoint,
                    "account_id": account_id # Can be None if no match
                })
        
        print(f"Combined Response C: {response_c}")

        # 3. Insert responseC into the clusters collection
        if response_c:
            print(f"Inserting {len(response_c)} clusters into '{CLUSTERS_COLLECTION}' collection...")
            try:
                # Use insert_many for efficiency
                insert_result = await clusters_collection.insert_many(response_c)
                print(f"Inserted cluster IDs: {insert_result.inserted_ids}")
            except Exception as e:
                print(f"Error inserting clusters: {e}")
        else:
            print("No clusters to insert.")

        # 4. Pull deployments/statefulsets information concurrently
        workload_tasks = []
        for cluster_data in response_c:
            eks_endpoint = cluster_data.get("endpoint")
            namespace = cluster_data.get("namespace") # Assuming namespace is the EKS namespace

            if eks_endpoint and namespace:
                # Here, bearer_token is used. For real EKS APIs, you'd likely need
                # to obtain temporary AWS credentials and sign the requests with SigV4.
                # This is a major difference.
                workload_tasks.append(
                    fetch_eks_workloads(session, eks_endpoint, namespace, bearer_token)
                )

        if workload_tasks:
            print("Fetching EKS workloads concurrently...")
            all_workloads = await asyncio.gather(*workload_tasks)
            # Flatten the list of lists into a single list of workload dicts
            flat_workloads = [item for sublist in all_workloads for item in sublist]

            if flat_workloads:
                print(f"Inserting {len(flat_workloads)} workloads into '{WORKLOADS_COLLECTION}' collection...")
                try:
                    insert_result = await workloads_collection.insert_many(flat_workloads)
                    print(f"Inserted workload IDs: {insert_result.inserted_ids}")
                except Exception as e:
                    print(f"Error inserting workloads: {e}")
            else:
                print("No workloads to insert.")
        else:
            print("No EKS endpoints to query for workloads.")

        # Close the DB connection
        db_client.close()
        print("Database connection closed.")

if __name__ == "__main__":
    asyncio.run(main())
