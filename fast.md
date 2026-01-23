class OSESettings(BaseSettings):  # 5 usages

    bearer_token_url: str = (
        "https://oauth-openshift.apps.REPLACE_WITH_CLUSTER_NAME."
        "REPLACE_WITH_DOMAIN/oauth/authorize?client_id=openshift"
        "&challenging-client&response_type=token"
    )

    ca_certificate_path: str = (
        f"{HOME_DIRECTORY}/src/common/config/certificates/ca-prod.pem"
    )

    cluster_api_url: str = (
        "https://api.REPLACE_WITH_CLUSTER_NAME."
        "REPLACE_WITH_DOMAIN:REPLACE_WITH_API_PORT"
    )

    content_type: str = CONTENT_TYPE

    deployment_url: str = (
        "https://console-openshift-console.apps.REPLACE_WITH_CLUSTER_NAME."
        "REPLACE_WITH_DOMAIN/k8s/ns/REPLACE_WITH_NAMESPACE/"
        "deployments/REPLACE_WITH_DEPLOYMENT_NAME"
    )

    deployment_uri: str = (
        "apis/apps/v1/namespaces/REPLACE_WITH_NAMESPACE/"
        "deployments/REPLACE_WITH_DEPLOYMENT_NAME"
    )

    deployments_list_uri: str = (
        "apis/apps/v1/namespaces/REPLACE_WITH_NAMESPACE/deployments"
    )

    hpa_uri: str = (
        "apis/autoscaling/v1/namespaces/REPLACE_WITH_NAMESPACE/"
        "horizontalpodautoscalers"
    )

    limit_ranges_uri: str = (
        "api/v1/namespaces/REPLACE_WITH_NAMESPACE/limitranges"
    )

    pdb_uri: str = (
        "apis/policy/v1/namespaces/REPLACE_WITH_NAMESPACE/"
        "poddisruptionbudgets"
    )

    pods_labels_uri: str = (
        "api/v1/namespaces/REPLACE_WITH_NAMESPACE/pods"
        "?labelSelector=REPLACE_WITH_LABEL_SELECTOR"
    )

    pods_uri: str = (
        "api/v1/namespaces/REPLACE_WITH_NAMESPACE/pods"
    )

    pod_delete_uri: str = (
        "api/v1/namespaces/REPLACE_WITH_NAMESPACE/pods/"
        "REPLACE_WITH_POD_NAME"
    )

    projects_uri: str = "apis/project.openshift.io/v1/projects"

    resourcequotas_uri: str = (
        "api/v1/namespaces/REPLACE_WITH_NAMESPACE/resourcequotas"
    )

    ssl_verify: bool = True