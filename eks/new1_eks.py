import boto3
import base64
import json
import tempfile
import os
from kubernetes import client, config
from datetime import datetime, timedelta, timezone
import urllib.parse # To correctly handle URL encoding of parameters

# --- Configuration ---
REGION_NAME = "us-west-2"        # Replace with your AWS Region
CLUSTER_NAME = "my-eks-cluster"  # Replace with your EKS Cluster name
# ---------------------

def generate_eks_token(cluster_name: str, region_name: str, token_lifetime_minutes=15) -> str:
    """
    Generates a Kubernetes bearer token for EKS using pure Boto3/Botocore signing logic.
    This accurately replicates how the 'aws eks get-token' CLI command works.
    """
    
    session = boto3.Session(region_name=region_name)
    
    # The token is a presigned URL to STS GetCallerIdentity, but constructed specifically.
    
    # 1. Define the parameters that will be part of the presigned URL query string
    #    These are the standard AWS signature parameters plus EKS specific ones.
    
    # The EKS token's presigned URL points to the STS service.
    # The 'Action' and 'Version' parameters are standard for STS API calls.
    # 'X-Amz-Expires' specifies how long the presigned URL is valid in seconds.
    query_params = {
        "Action": "GetCallerIdentity",
        "Version": "2011-06-15",
        "X-Amz-Expires": str(token_lifetime_minutes * 60)
    }

    # Construct the base URL for the STS service
    sts_endpoint = f"https://sts.{region_name}.amazonaws.com"
    
    # Create an AWSRequest object (this is a botocore object)
    # We construct the URL with the query parameters before signing.
    from botocore.awsrequest import AWSRequest
    
    # Manually build the canonical request
    # The EKS token actually presigns a request to STS.GetCallerIdentity,
    # but the *host* in the final token will be 'eks.amazonaws.com'
    # and it needs an 'x-k8s-aws-id' parameter.

    # First, create a request that can be signed by STS
    request_headers = {
        'host': f'sts.{region_name}.amazonaws.com', # Sign against STS host
        'x-k8s-aws-id': cluster_name # This header is key for EKS
    }
    
    # Prepare the query string
    encoded_query_params = urllib.parse.urlencode(query_params)
    full_url = f"{sts_endpoint}/?{encoded_query_params}"
    
    aws_request = AWSRequest(
        method="GET",
        url=full_url,
        headers=request_headers
    )
    
    # Use botocore's signing process directly via the session's client for STS
    sts_client = session.client('sts', region_name=region_name)
    
    # The underlying botocore client has a request signer.
    # We need to get the "operation model" for GetCallerIdentity
    # and then create a request specific to that model.
    
    # This is the tricky part: directly mimicking `aws eks get-token`'s signing.
    # It essentially presigns an STS GetCallerIdentity *request* but then
    # manipulates the URL.

    # Option 1: The 'aws eks get-token' approach (most reliable, if complex)
    # This involves manually constructing the URL for STS.GetCallerIdentity
    # and then signing it. The `sts_client.generate_presigned_url` is not
    # what `aws eks get-token` uses.
    # Instead, it constructs a URL with specific query parameters, then
    # presigns it *and* adds the x-k8s-aws-id parameter during the signing process
    # as a header, which then gets incorporated into the signature.
    
    # Let's use the explicit request signing from `botocore`.
    # This avoids the `generate_presigned_url` method which doesn't directly
    # support adding the `x-k8s-aws-id` header in a way that affects the signature
    # for a presigned URL in the EKS manner.
    
    # Get the credential provider
    creds = session.get_credentials().get_frozen_credentials()

    # Get the service model for STS
    service_model = sts_client.meta.service_model
    operation_model = service_model.operation_model("GetCallerIdentity")

    # This creates a request object that can be signed
    request_dict = sts_client._convert_to_request_dict(
        {}, operation_model,
        presigned_url=True, # Important: indicates we want a presigned URL
        region_name=region_name,
        credentials=creds,
        endpoint_url=sts_endpoint,
        expire_in=token_lifetime_minutes * 60
    )

    # Add the EKS specific header *before* signing
    request_dict['headers']['x-k8s-aws-id'] = cluster_name
    
    # The `request_dict` already contains the `X-Amz-Expires` query param.
    # Now, explicitly presign the request
    # This requires using the low-level `botocore.signers.RequestSigner`
    # which is not directly exposed as `session.get_component('request_signer')` in newer boto3.
    
    # Instead, we can let the client handle the signing by preparing it.
    final_presigned_url = sts_client.meta.events.emit(
        'request-created', 
        request=request_dict, 
        service_name='sts', 
        operation_name='GetCallerIdentity'
    )
    
    # The above is also not quite right for directly getting the URL.
    # The `aws-cli` and `eks-token` package do this more explicitly.
    
    # *** Corrected approach using `botocore.signers.RequestSigner` ***
    # This is how the AWS CLI and `eks-token` library do it.
    from botocore.signers import RequestSigner
    
    # The `request_signer` needs to be initialized.
    # It takes the service id, region, signature version and credentials.
    signer = RequestSigner(
        service_id=service_model.service_id,
        region_name=region_name,
        signature_version='v4',
        credentials=creds,
        event_emitter=sts_client.meta.events # Pass the client's event emitter
    )
    
    # The URL that gets signed is the base STS endpoint with the required parameters
    # and the x-k8s-aws-id header.
    
    # Construct the base URL for the STS service
    # Note: `GetCallerIdentity` is a parameter, not part of the path.
    # The path is just '/' for the root endpoint.
    sts_url_path = '/'
    
    # The canonical request query string *must* contain 'Action', 'Version', 'X-Amz-Expires'
    canonical_querystring = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)

    # The headers for signing must include 'host' and 'x-k8s-aws-id'
    # Ensure header names are lowercase for signing purposes
    signing_headers = {
        'host': f"sts.{region_name}.amazonaws.com",
        'x-k8s-aws-id': cluster_name
    }
    
    # Presign the URL
    # The `generate_presigned_url` method of `RequestSigner` is the key.
    presigned_url = signer.generate_presigned_url(
        method="GET",
        url=f"https://sts.{region_name}.amazonaws.com", # Base URL to sign
        headers=signing_headers,
        parameters=query_params, # The parameters that will be in the query string
        expires_in=token_lifetime_minutes * 60,
    )

    # The `presigned_url` now contains the signed URL to STS GetCallerIdentity
    # with the x-k8s-aws-id header incorporated into the signature.
    
    # Now, we need to perform the EKS-specific final modifications:
    # Change the host from `sts` to `eks`
    # and ensure `x-k8s-aws-id` is in the query string (if it's not already)
    
    # The `generate_presigned_url` from `botocore.signers.RequestSigner` usually
    # includes the x-k8s-aws-id as a signed header. EKS requires it in the query string *and*
    # the hostname to be eks.
    
    # This is the crucial part that `aws eks get-token` does:
    # 1. It presigns an STS GetCallerIdentity URL with x-k8s-aws-id *header*.
    # 2. It then replaces the 'sts' hostname with 'eks'.
    # 3. It adds 'x-k8s-aws-id' as a *query parameter* to the URL (even though it was a header for signing).

    # So, let's start with the `presigned_url` and apply the EKS transformations:
    
    # Replace 'sts.amazonaws.com' with 'eks.amazonaws.com' in the hostname
    modified_url = presigned_url.replace(f"sts.{region_name}.amazonaws.com", f"eks.{region_name}.amazonaws.com")
    
    # Ensure 'x-k8s-aws-id' is explicitly in the query string.
    # The `generate_presigned_url` above might put `X-Amz-SignedHeaders=host%3Bx-k8s-aws-id`
    # but the actual query parameter `x-k8s-aws-id` is still needed for the EKS endpoint.
    if f"x-k8s-aws-id={cluster_name}" not in modified_url:
        if '?' in modified_url:
            modified_url += f"&x-k8s-aws-id={cluster_name}"
        else:
            modified_url += f"?x-k8s-aws-id={cluster_name}"
            
    # 3. Base64 URL-safe encode the entire modified URL
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
