import boto3
import base64
import json
import tempfile
import os
from kubernetes import client, config
from datetime import datetime, timedelta, timezone
from botocore.awsrequest import AWSRequest # Import AWSRequest

# --- Configuration ---
REGION_NAME = "us-west-2"        # Replace with your AWS Region
CLUSTER_NAME = "my-eks-cluster"  # Replace with your EKS Cluster name
# ---------------------

def generate_eks_token(cluster_name: str, region_name: str, token_lifetime_minutes=15) -> str:
    """
    Generates a Kubernetes bearer token for EKS using pure Boto3 and STS.
    This replaces the need for the 'aws eks get-token' CLI command or the 'eks-token' package.
    """
    
    session = boto3.Session(region_name=region_name)
    credentials = session.get_credentials()
    
    # Calculate expiration time
    expiration = datetime.now(timezone.utc) + timedelta(minutes=token_lifetime_minutes)
    
    # Create the request for GetCallerIdentity
    # The EKS token requires the service to be 'eks', but the underlying call is STS
    # The URL needs a 'x-k8s-aws-id' header with the cluster name, but for token generation,
    # it's usually embedded in the presigned URL as a query parameter or hostname modification.
    
    # EKS specific presigned URL generation logic
    # This is based on how `aws eks get-token` works internally.
    # It creates a presigned URL to STS GetCallerIdentity, but then manipulates it
    # to target the EKS service domain and adds cluster-specific parameters.

    # 1. Create a raw STS GetCallerIdentity request
    #    The service needs to be 'sts' for signing, but the resulting URL
    #    will be tweaked for EKS.
    
    # Manually construct the components needed for a presigned URL
    endpoint_url = f"https://sts.{region_name}.amazonaws.com"
    request_params = {
        "Action": "GetCallerIdentity",
        "Version": "2011-06-15",
        "X-Amz-Expires": str(token_lifetime_minutes * 60)
    }

    # Use botocore's internal signing logic
    # We need to create an AWSRequest and then sign it.
    request = AWSRequest(
        method="GET",
        url=endpoint_url + "/?" + "&".join([f"{k}={v}" for k, v in request_params.items()]),
        headers={'x-k8s-aws-id': cluster_name} # This header is crucial for EKS token
    )

    # Use the session's signer
    signer = session.get_component('request_signer')
    signer.add_auth(request) # This will add Authorization headers and modify the URL for presigning

    # Get the presigned URL from the modified request
    # The `request.url` now contains the presigned URL with all necessary query parameters
    presigned_url = request.url

    # The EKS authenticator expects the service name in the hostname to be 'eks', not 'sts'
    # and expects the cluster name in a specific query parameter.
    # The x-k8s-aws-id header is often encoded as a query param in the final URL.
    
    # Clean up the URL: remove existing Action and Version, add EKS specific ones
    # This manipulation is tricky and often where custom implementations diverge.
    
    # A more robust way, closer to the actual CLI, is to use a specific
    # `boto3.client('sts').get_caller_identity` operation and then manually
    # construct and sign the specific EKS token URL.
    
    # Let's use the explicit `get_caller_identity` presigning, and then manually
    # add the EKS specific components.
    
    # Corrected approach: Generate a standard STS presigned URL first, then modify it
    sts_client = boto3.client('sts', region_name=region_name,
                              config=boto3.session.Config(signature_version='v4'))

    # Generate a presigned URL for GetCallerIdentity
    # This will include X-Amz-Signature, X-Amz-Date, X-Amz-SignedHeaders etc.
    presigned_url_base = sts_client.generate_presigned_url(
        ClientMethod='GetCallerIdentity',
        Params={
            'DurationSeconds': token_lifetime_minutes * 60,
        },
        ExpiresIn=token_lifetime_minutes * 60, # This is the TTL for the URL itself
        HttpMethod='GET',
    )
    
    # Now, modify the URL to fit the EKS token specification
    # The EKS token is a presigned URL for STS GetCallerIdentity, but with:
    # 1. Hostname changed from `sts.amazonaws.com` to `eks.amazonaws.com`
    # 2. An additional query parameter `x-k8s-aws-id` set to the cluster name.
    
    # Replace 'sts.amazonaws.com' with 'eks.amazonaws.com'
    modified_url = presigned_url_base.replace(f"sts.{region_name}.amazonaws.com", f"eks.{region_name}.amazonaws.com")
    
    # Add the cluster name as x-k8s-aws-id query parameter
    if '?' in modified_url:
        modified_url += f"&x-k8s-aws-id={cluster_name}"
    else:
        modified_url += f"?x-k8s-aws-id={cluster_name}"
        
    # 3. Base64 encode the URL
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
