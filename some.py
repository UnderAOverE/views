import asyncio
import logging
from dataclasses import dataclass
from typing import Self, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

# Assuming these are imported from your existing structure
# from src.common.settings import environment_settings
# from src.common.http_client import HTTPXClient
# from src.apis.service.ose.models import ScaleSettingsModel

logger = logging.getLogger(__name__)

# --- Models ---

@dataclass
class GuardRailCheckResult:
    check_name: str
    message: str
    passed: bool

class NamespaceConstraintsResponse(BaseModel):
    cluster_name: str
    namespace: str
    hpa: List[dict[str, Any]] = Field(default_factory=list)
    pdb: List[dict[str, Any]] = Field(default_factory=list)
    resource_quotas: List[dict[str, Any]] = Field(default_factory=list)
    limit_ranges: List[dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

# --- Utilities ---

class K8sResourceParser:
    @staticmethod
    def parse_cpu(cpu_str: str) -> int:
        if not cpu_str: return 0
        if str(cpu_str).endswith("m"):
            return int(cpu_str[:-1])
        return int(float(cpu_str) * 1000)

    @staticmethod
    def parse_memory(mem_str: str) -> int:
        if not mem_str: return 0
        units = {
            "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
            "K": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4
        }
        for unit, multiplier in units.items():
            if str(mem_str).endswith(unit):
                return int(mem_str[:-len(unit)]) * multiplier
        return int(mem_str)

# --- Service ---

class OSEGuardRailService:
    RESOURCE_POD_READINESS: str = "Resource Pod Readiness"
    CURRENT_REPLICAS: str = "Current Replicas Check"
    PDB_CONSTRAINTS: str = "PDB Constraints Check"
    HPA_CONSTRAINTS: str = "HPA Constraints Check"
    RESOURCE_QUOTA: str = "Resource Quota Check"
    LIMIT_RANGE: str = "Limit Range Check"
    REPLICA_LIMIT: str = "Replica Limit Check"
    OBJECT_STATE: str = "Object Current State Check"

    def __init__(self) -> None:
        self.ose_settings = environment_settings.ose
        # Assuming HTTPXClient is pre-configured
        self.httpx_client = HTTPXClient(
            ca_certificate_path=self.ose_settings.ca_certificate_path,
            verify_ssl=self.ose_settings.ssl_verify,
        )

    @classmethod
    async def get_service(cls) -> Self:
        return cls()

    async def _make_k8s_request(self, uri: str, token: str, cluster_url: str) -> dict:
        url = f"{cluster_url.rstrip('/')}/{uri.lstrip('/')}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.httpx_client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def get_scale_settings(self) -> Any: # Replace Any with ScaleSettingsModel
        try:
            # Using your logic from the prompt
            db_settings = await self.settings_service.get_db_settings(environment="PROD")
            if not db_settings or isinstance(db_settings, str):
                return ScaleSettingsModel()
            return db_settings
        except Exception as e:
            logger.warning(f"Error fetching scale settings: {e}, using defaults")
            return ScaleSettingsModel()

    async def perform_checks(
        self, cluster_name: str, cluster_api_url: str, bearer_token: str, 
        namespace: str, object_name: str, object_type: str, 
        target_replicas: int, operation_type: str
    ) -> Tuple[bool, List[str], List[GuardRailCheckResult]]:
        
        results = []
        success_messages = []
        all_passed = True

        scale_settings = await self.get_scale_settings()
        resource_data = await self._get_resource(cluster_api_url, bearer_token, namespace, object_name, object_type)
        current_replicas = resource_data.get("spec", {}).get("replicas", 0)

        # Logic Mapping
        if operation_type in ["restart", "stop"]:
            passed, msg = await self._check_pod_readiness(cluster_api_url, bearer_token, namespace, object_name)
            results.append(GuardRailCheckResult(self.RESOURCE_POD_READINESS, msg, passed))

        elif operation_type == "start":
            passed = (current_replicas == 0)
            msg = "Object is stopped" if passed else f"Object has {current_replicas} active replicas"
            results.append(GuardRailCheckResult(self.OBJECT_STATE, msg, passed))

        elif operation_type == "scale":
            if current_replicas == target_replicas:
                results.append(GuardRailCheckResult(self.CURRENT_REPLICAS, "Target matches current replicas", False))
            
            hpa_passed, hpa_msg = await self._check_hpa_constraints(cluster_api_url, bearer_token, namespace, object_name, target_replicas)
            results.append(GuardRailCheckResult(self.HPA_CONSTRAINTS, hpa_msg, hpa_passed))

            # Scaling Down
            if target_replicas < current_replicas and scale_settings.scale.enforce_pdb_check:
                pdb_p, pdb_m = await self._check_pdb_constraints(cluster_api_url, bearer_token, namespace)
                results.append(GuardRailCheckResult(self.PDB_CONSTRAINTS, pdb_m, pdb_p))

            # Scaling Up
            if target_replicas > current_replicas:
                if target_replicas > scale_settings.scale.up_replicas_hard_limit:
                    results.append(GuardRailCheckResult(self.REPLICA_LIMIT, f"Exceeds hard limit: {scale_settings.scale.up_replicas_hard_limit}", False))
                
                if scale_settings.scale.enforce_resource_quota_check:
                    q_p, q_m = await self._check_resource_quotas(cluster_api_url, bearer_token, namespace, resource_data, target_replicas, current_replicas)
                    results.append(GuardRailCheckResult(self.RESOURCE_QUOTA, q_m, q_p))

                if scale_settings.scale.enforce_limit_ranges_check:
                    lr_p, lr_m = await self._check_limit_ranges(cluster_api_url, bearer_token, namespace, resource_data)
                    results.append(GuardRailCheckResult(self.LIMIT_RANGE, lr_m, lr_p))

        # Compile totals
        all_passed = all(r.passed for r in results)
        success_messages = [f"{r.check_name}: {r.message}" for r in results if r.passed]

        return all_passed, success_messages, results

    async def get_namespace_constraints(
        self, cluster_name: str, cluster_api_url: str, bearer_token: str, namespace: str
    ) -> NamespaceConstraintsResponse:
        uris = {
            "hpa": self.ose_settings.hpa_uri.replace("REPLACE_WITH_NAMESPACE", namespace),
            "pdb": self.ose_settings.pdb_uri.replace("REPLACE_WITH_NAMESPACE", namespace),
            "resource_quotas": self.ose_settings.resourcequotas_uri.replace("REPLACE_WITH_NAMESPACE", namespace),
            "limit_ranges": self.ose_settings.limit_ranges_uri.replace("REPLACE_WITH_NAMESPACE", namespace),
        }

        keys = list(uris.keys())
        tasks = [self._make_k8s_request(uris[k], bearer_token, cluster_api_url) for k in keys]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        resp_model = NamespaceConstraintsResponse(cluster_name=cluster_name, namespace=namespace)

        for i, key in enumerate(keys):
            res = responses[i]
            if isinstance(res, Exception):
                resp_model.errors.append(f"{key}: {str(res)}")
                continue
            
            items = res.get("items", [])
            setattr(resp_model, key, items)

        return resp_model

    # --- Private Helpers ---

    async def _get_resource(self, url, token, ns, name, rtype) -> dict:
        # Resolve correct URI based on type
        is_dep = rtype.lower() == "deployment"
        uri_template = self.ose_settings.deployment_uri if is_dep else self.ose_settings.statefulset_uri
        
        # Mapping Deployment -> DEPLOYMENT_NAME or StatefulSet -> STATEFULSET_NAME
        placeholder = f"REPLACE_WITH_{rtype.upper()}_NAME"
        uri = uri_template.replace("REPLACE_WITH_NAMESPACE", ns).replace(placeholder, name)
        return await self._make_k8s_request(uri, token, url)

    async def _check_pod_readiness(self, url, token, ns, name) -> Tuple[bool, str]:
        uri = self.ose_settings.pods_uri.replace("REPLACE_WITH_NAMESPACE", ns)
        pods = await self._make_k8s_request(uri, token, url)
        
        # Check for pods where name is in metadata and status is Ready
        ready_count = 0
        for pod in pods.get("items", []):
            if name in pod["metadata"]["name"]:
                conditions = pod.get("status", {}).get("conditions", [])
                if any(c["type"] == "Ready" and c["status"] == "True" for c in conditions):
                    ready_count += 1
        
        return (ready_count > 0, f"Found {ready_count} ready pods" if ready_count > 0 else "No pods are currently ready")

    async def _check_hpa_constraints(self, url, token, ns, name, target) -> Tuple[bool, str]:
        uri = self.ose_settings.hpa_uri.replace("REPLACE_WITH_NAMESPACE", ns)
        hpas = await self._make_k8s_request(uri, token, url)
        for hpa in hpas.get("items", []):
            ref = hpa["spec"]["scaleTargetRef"]
            if ref["name"] == name:
                min_r = hpa["spec"].get("minReplicas", 1)
                max_r = hpa["spec"].get("maxReplicas", 1)
                if not (min_r <= target <= max_r):
                    return False, f"Target {target} is outside HPA range {min_r}-{max_r}"
        return True, "HPA constraints validated"

    async def _check_pdb_constraints(self, url, token, ns) -> Tuple[bool, str]:
        uri = self.ose_settings.pdb_uri.replace("REPLACE_WITH_NAMESPACE", ns)
        pdbs = await self._make_k8s_request(uri, token, url)
        for pdb in pdbs.get("items", []):
            if pdb.get("status", {}).get("disruptionsAllowed", 0) == 0:
                return False, f"PDB {pdb['metadata']['name']} allows no further disruptions"
        return True, "PDB check passed"

    async def _check_resource_quotas(self, url, token, ns, resource, target, current) -> Tuple[bool, str]:
        uri = self.ose_settings.resourcequotas_uri.replace("REPLACE_WITH_NAMESPACE", ns)
        quotas = await self._make_k8s_request(uri, token, url)
        if not quotas.get("items"): return True, "No quotas found"

        containers = resource["spec"]["template"]["spec"]["containers"]
        pod_cpu = sum(K8sResourceParser.parse_cpu(c.get("resources", {}).get("requests", {}).get("cpu", 0)) for c in containers)
        pod_mem = sum(K8sResourceParser.parse_memory(c.get("resources", {}).get("requests", {}).get("memory", 0)) for c in containers)
        
        needed_cpu = pod_cpu * (target - current)
        needed_mem = pod_mem * (target - current)

        for q in quotas["items"]:
            hard = q["status"].get("hard", {})
            used = q["status"].get("used", {})
            
            if "requests.cpu" in hard:
                avail = K8sResourceParser.parse_cpu(hard["requests.cpu"]) - K8sResourceParser.parse_cpu(used.get("requests.cpu", 0))
                if needed_cpu > avail: return False, "Quota: Insufficient CPU"
            
            if "requests.memory" in hard:
                avail = K8sResourceParser.parse_memory(hard["requests.memory"]) - K8sResourceParser.parse_memory(used.get("requests.memory", 0))
                if needed_mem > avail: return False, "Quota: Insufficient Memory"

        return True, "Quota checks passed"

    async def _check_limit_ranges(self, url, token, ns, resource) -> Tuple[bool, str]:
        uri = self.ose_settings.limit_ranges_uri.replace("REPLACE_WITH_NAMESPACE", ns)
        lrs = await self._make_k8s_request(uri, token, url)
        containers = resource["spec"]["template"]["spec"]["containers"]

        for lr in lrs.get("items", []):
            for limit in lr["spec"]["limits"]:
                if limit["type"] == "Container":
                    max_cpu = K8sResourceParser.parse_cpu(limit.get("max", {}).get("cpu", "999999"))
                    for c in containers:
                        if K8sResourceParser.parse_cpu(c.get("resources", {}).get("requests", {}).get("cpu", 0)) > max_cpu:
                            return False, f"Container {c['name']} exceeds LimitRange max CPU"
        return True, "LimitRange checks passed"
