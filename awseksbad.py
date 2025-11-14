class EKSService:
    # ...

    def _get_eks_token(account_id: str, session: boto3.Session, cluster_name: str, region: str,) -> str | None:
        """
        :param cluster_name: The name of the EKS cluster.
        :type cluster_name: str
        :param region: The AWS region where the EKS cluster is located.
        :type region: str
        :return: A base64-encoded EKS authentication token.
        :rtype: str | None
        """

        logger.debug(
            f" EKSService._get_eks_token generating token for account_id={account_id}, "
            f"cluster={cluster_name}, region={region}",
            extra={"version": module_version,}
        )

        client = session.client(ApplicationConstants.AWSServiceName)
        signer = client._request_signer  # already a RequestSigner

        params = {
            "method": "GET",
            "url": (
                f"https://{ApplicationConstants.AWSServiceName}.{region}.amazonaws.com/"
                "?Action=GetCallerIdentity&Version=2011-06-15"
            ),
            "body": {},
            "headers": {
                "x-k8s-aws-id": cluster_name,
            },
            "context": {},
        }

        # NOTE: pass operation_name=None
        presigned_url = signer.generate_presigned_url(
            request_dict=params,
            expires_in=60,
            operation_name=None,
        )

        return (
            ApplicationConstants.KubernetesTokenIdentifier
            + base64.urlsafe_b64encode(presigned_url.encode()).decode().rstrip("=")
        )