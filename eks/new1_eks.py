import boto3
import base64
import json
import tempfile
import os
from kubernetes import client, config
from datetime import datetime, timedelta, timezone
import urllib.parse

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

    # 1. Generate a standard presigned URL for the STS GetCallerIdentity API call.
    #    'ClientMethod' specifies the AWS API action to presign.
    #    'ExpiresIn' defines the validity duration of the presigned URL.
    #    No special 'Params' are strictly needed for GetCallerIdentity itself,
    #    as the EKS-specific 'x-k8s-aws-id' and host manipulation come later.
    try:
        presigned_url_base = sts_client.generate_presigned_url(
            ClientMethod='GetCallerIdentity',
            Params={}, # GetCallerIdentity usually doesn't need specific request parameters
            ExpiresIn=token_lifetime_minutes * 60, 
            HttpMethod='GET',
        )
    except Exception as e:
        print(f"Error generating presigned URL for GetCallerIdentity: {e}")
        print("This often indicates an issue with the boto3/botocore version or environment setup.")
        print("Attempting an alternative low-level signing method...")
        
        # Fallback to the botocore.signers.RequestSigner approach if generate_presigned_url fails.
        # This is more complex but is what 'aws eks get-token' uses internally.
        session = boto3.Session(region_name=region_name)
        creds = session.get_credentials().get_frozen_credentials()
        
        from botocore.signers import RequestSigner
        from botocore.session import get_session
        
        # Ensure we have a botocore session and event emitter
        botocore_session = get_session()
        event_emitter = botocore_session.get_component('event_emitter')
        
        # Manually create service model for STS
        service_model = botocore_session.get_service_model('sts')

        signer = RequestSigner(
            service_id=service_model.service_id,
            region_name=region_name,
            signature_version='v4',
            credentials=creds,
            event_emitter=event_emitter
        )
        
        query_params_for_signing = {
            "Action": "GetCallerIdentity",
            "Version": "2011-06-15",
            "X-Amz-Expires": str(token_lifetime_minutes * 60)
        }
        
        signing_headers = {
            'host': f"sts.{region_name}.amazonaws.com",
            'x-k8s-aws-id': cluster_name # This is crucial for EKS token signature
        }

        presigned_url_base = signer.generate_presigned_url(
            method="GET",
            url=f"https://sts.{region_name}.amazonaws.com", # Base URL to sign
            headers=signing_headers,
            parameters=query_params_for_for_signing, # Parameters for the query string
            expires_in=token_lifetime_minutes * 60,
        )
        print("Successfully generated token using low-level signing fallback.")
    
    # --- EKS-specific modifications (same for both generation methods) ---
    
    # 2. Modify the standard STS presigned URL to fit the EKS token specification.
    #    The EKS authenticator expects:
    #    a) The hostname to be `eks.{region}.amazonaws.com`.
    #    b) An additional query parameter `x-k8s-aws-id` set to the EKS cluster name.

    # Replace 'sts.amazonaws.com' with 'eks.amazonaws.com' in the hostname
    modified_url = presigned_url_base.replace(f"sts.{region_name}.amazonaws.com", f"eks.{region_name}.amazonaws.com")
    
    # Ensure 'x-k8s-aws-id' is explicitly in the query string.
    # It might have been a header during signing, but EKS needs it in the URL.
    # Use urllib.parse to safely manipulate query parameters.
    url_parts = urllib.parse.urlparse(modified_url)
    query_dict = urllib.parse.parse_qs(url_parts.query)
    
    # Add/overwrite x-k8s-aws-id in the query parameters
    query_dict['x-k8s-aws-id'] = [cluster_name] # parse_qs returns lists, so set as list
    
    # Reconstruct the query string
    reconstructed_query = urllib.parse.urlencode(query_dict, doseq=True)
    
    # Reconstruct the URL with the modified query string
    final_eks_presigned_url = urllib.parse.urlunparse(
        url_parts._replace(query=reconstructed_query)
    )
        
    # 3. Base64 URL-safe encode the entire modified URL
    base64_url = base64.urlsafe_b64encode(final_eks_presigned_url.encode("utf-8")).decode("utf-8").rstrip('=')
    
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
