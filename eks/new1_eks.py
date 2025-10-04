import boto3
import base64
import json
import tempfile
import os
from kubernetes import client, config
from datetime import datetime, timedelta, timezone

# --- Configuration ---
REGION_NAME = "us-west-2"        # Replace with your AWS Region
CLUSTER_NAME = "my-eks-cluster"  # Replace with your EKS Cluster name
# ---------------------

def generate_eks_token(cluster_name: str, region_name: str, token_lifetime_minutes=15) -> str:
    """
    Generates a Kubernetes bearer token for EKS using pure Boto3 and STS.
    This replaces the need for the 'aws eks get-token' CLI command or the 'eks-token' package.
    """
    
    sts_client = boto3.client('sts', region_name=region_name)

    # Generate a standard presigned URL for the GetCallerIdentity action
    # This URL will contain all the necessary authentication parameters (signature, date, etc.)
    presigned_url_base = sts_client.generate_presigned_url(
        ClientMethod='GetCallerIdentity',
        Params={
            # EKS token requests a specific duration for the underlying GetCallerIdentity call.
            # While generate_presigned_url has an ExpiresIn param, some sources suggest
            # including DurationSeconds in Params for specific token types.
            # However, for EKS, ExpiresIn is typically sufficient for the presigned URL validity.
            # No specific Params are strictly required for GetCallerIdentity itself,
            # but ExpiresIn is crucial for the presigned URL's overall validity.
        },
        ExpiresIn=token_lifetime_minutes * 60, # The URL itself will be valid for this many seconds
        HttpMethod='GET',
    )
    
    # Now, modify this standard STS presigned URL to fit the EKS token specification.
    # The EKS authenticator expects:
    # 1. The hostname to be `eks.{region}.amazonaws.com` instead of `sts.{region}.amazonaws.com`.
    # 2. An additional query parameter `x-k8s-aws-id` set to the EKS cluster name.

    # 1. Replace 'sts.amazonaws.com' with 'eks.amazonaws.com' in the hostname
    modified_url = presigned_url_base.replace(f"sts.{region_name}.amazonaws.com", f"eks.{region_name}.amazonaws.com")
    
    # 2. Add the cluster name as 'x-k8s-aws-id' query parameter
    if '?' in modified_url:
        modified_url += f"&x-k8s-aws-id={cluster_name}"
    else:
        modified_url += f"?x-k8s-aws-id={cluster_name}"
        
    # 3. Base64 URL-safe encode the entire modified URL
    # The `rstrip('=')` removes padding characters, which is common for EKS token base64 strings.
    base64_url = base64.urlsafe_b64encode(modified_url.encode("utf-8")).decode("utf-8").rstrip('=')
    
    # 4. Prefix with the EKS version header
    eks_token = f"k8s-aws-v1.{base64_url}"
    
    return eks_token


def get_eks_cluster_info(cluster_name, region_name):
    """Retrieves cluster endpoint and CA data."""
    eks_client = boto3.client("eks", region_name=region_name)
    cluster_info = eks_client.describe_cluster(name=cluster_name)['cluster']
    
    endpoint = cluster_info["endpoint"]
    cert_authority_data = cluster_info["certificateAuthority"]["data"]
    
    return endpoint, cert_authority_data

def connect_and_list_pods(endpoint, cert_authority_data, token):
    """Sets up the Kubernetes client configuration and lists all pods."""
    
    # Use a temporary file to store the decoded CA certificate
    ca_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as ca_file:
            ca_file.write(base64.b64decode(cert_authority_data))
            ca_file_path = ca_file.name
            
        # 3. Create Kubernetes Client Configuration
        configuration = client.Configuration()
        configuration.host = endpoint
        configuration.verify_ssl = True
        configuration.ssl_ca_cert = ca_file_path
        
        # 4. Set the custom EKS token as the Authorization header
        configuration.api_key = {"authorization": f"Bearer {token}"}
        
        client.Configuration.set_default(configuration)
        
        # 5. Connect and make a Kubernetes API call
        v1 = client.CoreV1Api()
        print("✅ Successfully connected to EKS Kubernetes API (using pure Boto3 token).")
        
        print("\nListing all Pods:")
        ret = v1.list_pod_for_all_namespaces(watch=False)
        
        for i in ret.items:
            print(f"- {i.metadata.name}\t({i.status.phase})\tNamespace: {i.metadata.namespace}")

    except client.ApiException as e:
        print(f"❌ Kubernetes API Error: {e.status} - {e.reason}")
        
    except Exception as e:
        print(f"❌ An unexpected error occurred during connection: {e}")
        
    finally:
        # Clean up the temporary certificate file
        if ca_file_path and os.path.exists(ca_file_path):
            os.remove(ca_file_path)


if __name__ == "__main__":
    try:
        print(f"1. Retrieving EKS cluster information...")
        endpoint, ca_data = get_eks_cluster_info(CLUSTER_NAME, REGION_NAME)
        
        print(f"2. Generating EKS Bearer Token using pure Boto3...")
        token = generate_eks_token(CLUSTER_NAME, REGION_NAME)
        
        print("3. Connecting to Kubernetes API...")
        connect_and_list_pods(endpoint, ca_data, token)

    except Exception as e:
        print(f"\nFATAL ERROR: Ensure your local AWS credentials are configured and have 'eks:DescribeCluster' and 'sts:GetCallerIdentity' permissions. Error: {e}")
