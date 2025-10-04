import boto3
from botocore.signers import RequestSigner
import datetime

def get_eks_token(cluster_name, role_arn):
    # 1. Assume the desired role
    sts = boto3.client("sts")
    assumed = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="eks-access",
    )
    creds = assumed["Credentials"]

    # 2. Build a session with those creds
    session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )

    # 3. Use RequestSigner directly
    client = session._session.create_client("sts")
    signer = RequestSigner(
        service_id="sts",
        region_name=session.region_name,
        signing_name="sts",
        signature_version="v4",
        credentials=client._request_signer._credentials,
        event_emitter=session._session.get_component("event_emitter"),
    )

    params = {
        "method": "GET",
        "url": "https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
        "body": {},
        "headers": {},
        "context": {},
    }

    signed_url = signer.generate_presigned_url(
        request_dict=params,
        expires_in=60,
        operation_name=""
    )

    import base64, json
    token = "k8s-aws-v1." + base64.urlsafe_b64encode(signed_url.encode()).decode().rstrip("=")
    return token

print(get_eks_token("mycluster", "arn:aws:iam::123456789012:role/MyEksRole"))
