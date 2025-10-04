import boto3
from botocore.signers import RequestSigner
import base64

def get_eks_token(session, cluster_name):
    client = session.client("sts")
    signer = client._request_signer  # already a RequestSigner
    params = {
        "method": "GET",
        "url": "https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
        "body": {},
        "headers": {},
        "context": {},
    }
    # NOTE: pass operation_name=None
    presigned_url = signer.generate_presigned_url(
        request_dict=params,
        expires_in=60,
        operation_name=None
    )
    return "k8s-aws-v1." + base64.urlsafe_b64encode(
        presigned_url.encode()
    ).decode().rstrip("=")

# if you already have temporary creds
session = boto3.Session(
    aws_access_key_id=ACCESS_KEY_ID,
    aws_secret_access_key=SECRET_ACCESS_KEY,
    aws_session_token=SESSION_TOKEN,
    region_name="us-east-1"
)

token = get_eks_token(session, "my-cluster")
print(token)
