
1. The "Flicker" (Flapping) Effect
If you manually scale a Deployment to 50 replicas:
Kubernetes will immediately start spinning up 50 pods.
A few seconds later, the HPA Controller wakes up (it checks every 15 seconds by default).
The HPA looks at the CPU/Memory metrics. If the metrics say you only need 2 pods, the HPA will overwrite your manual setting.
Kubernetes will immediately start killing 48 pods to get back down to 2.
Result: You wasted cluster resources, and your manual scale lasted less than 30 seconds.


If it exists, return 409 Conflict.
In the error message, tell the user: "Manual scaling is disabled because an HPA is managing this resource. Please update the HPA min/max instead."

While ResourceQuotas limit the total amount of resources for the whole namespace (the "Bucket"), LimitRanges control the minimum and maximum size of each individual pod (the "Measuring Cup").
When you scale to 50 replicas, LimitRanges impact your operation in three ways:
1. The "Defaulting" Trap (Most Important)
If a developer creates a Deployment and forgets to define how much CPU or Memory a pod needs, the LimitRange will automatically inject its default values into those 50 pods.
The Risk: If your LimitRange has a default of 500m CPU per pod, scaling to 50 pods will suddenly try to consume 25 CPUs from your namespace quota.
The Result: If your Namespace only has 20 CPUs available, 10 of your 50 pods will be stuck in Pending state forever because the LimitRange "stealthily" filled up your quota.
2. The "Maximum Size" Enforcement
If someone updates the Deployment template to have a very high limit (e.g., 4GB RAM) but the LimitRange for that namespace allows a maximum of 2GB per pod:
The Result: Kubernetes will reject the scaling operation. The Deployment will show a FailedCreate error in its events because the pod template violates the LimitRange.
3. Ratio Constraints (Less Common)
Some LimitRanges enforce a maxLimitRequestRatio. This means the "Limit" cannot be, for example, more than 2x the "Request." If your scaling operation involves a pod template that violates this ratio, the new pods will never be created.

How to handle LimitRanges in your API?
To make your scaling route truly resilient, your policy_service.py should check the LimitRange before applying the scale.
A. The "Predictive" Calculation
Before scaling to 50, your code should:
Look at the Pod Template in the Deployment.
If CPU/Memory is missing, fetch the LimitRange for that namespace.
Use the default values from the LimitRange to calculate the Total Potential Usage.
Compare that Total to the ResourceQuota.

If you ignore LimitRanges:
Quota calculation fails: You won't know the real cost of those 50 pods.
Pending Pods: Users will think the scale "worked" (API returned 200), but 15 minutes later they will complain that only half their pods are actually running.
Resilient Design: Always assume that if a pod doesn't have a resource request, the LimitRange will decide it for you. Calculate based on those defaults.



from fastapi import HTTPException, status

class PolicyService:
    def __init__(self, k8s_service, db):
        self.k8s = k8s_service
        self.db = db

    async def validate_request(self, obj_type, ns, name, requested_replicas):
        # 1. Get Settings from MongoDB
        settings_doc = await self.db.app_settings.find_one({"category": "scaling_rules"})
        settings = settings_doc["settings"]

        # 2. Prod Keyword Check
        if any(word in name.lower() for word in settings["forbidden_keywords"]):
            raise HTTPException(status_code=403, detail="Scaling production resources is forbidden.")

        # 3. Global Max Replicas Check
        if requested_replicas > settings["max_replicas_limit"]:
            raise HTTPException(status_code=400, detail=f"Request exceeds global limit of {settings['max_replicas_limit']}")

        # 4. HPA Check (Conflict Detection)
        hpa_resp = await self.k8s.get_hpas(ns)
        for hpa in hpa_resp.json().get("items", []):
            target = hpa["spec"]["scaleTargetRef"]
            if target["name"] == name and target["kind"].lower() == obj_type:
                raise HTTPException(status_code=409, detail=f"Managed by HPA {hpa['metadata']['name']}")

        # 5. Fetch current scale for math
        curr_scale_resp = await self.k8s.get_scale(obj_type, ns, name)
        current_replicas = curr_scale_resp.json()["spec"]["replicas"]

        # 6. PDB Check (Only if scaling down)
        if requested_replicas < current_replicas and settings["enforce_pdb_check"]:
            pdb_resp = await self.k8s.get_pdbs(ns)
            for pdb in pdb_resp.json().get("items", []):
                if pdb["status"]["disruptionsAllowed"] == 0:
                    raise HTTPException(status_code=422, detail="PDB blocks scale-down.")

        # 7. Resource Quota Check (If scaling up)
        if requested_replicas > current_replicas:
            quota_resp = await self.k8s.get_quotas(ns)
            for quota in quota_resp.json().get("items", []):
                hard = int(quota["status"]["hard"].get("pods", 999))
                used = int(quota["status"]["used"].get("pods", 0))
                # Available = HardLimit - (AlreadyUsed - CurrentObject)
                available = hard - (used - current_replicas)
                if requested_replicas > available:
                    raise HTTPException(status_code=422, detail=f"Namespace quota exceeded. Max available: {available}")

        return True


