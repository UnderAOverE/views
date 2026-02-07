import asyncio
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from cryptography.fernet import Fernet
import aiosmtplib
from email.message import EmailMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- Settings ---
CONCURRENCY_LIMIT = 20
SAVE_BATCH_SIZE = 20
MAX_CLUSTERS_ALLOWED = 200
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "cluster_db"
OUTPUT_COLLECTION = "ActiveClusterTokens"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ClusterRefresh")

class ClusterProcessor:
    def __init__(self, sector: str, batch_env: str):
        self.sector = sector
        self.batch_env = batch_env
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.failures = []
        self.results_buffer = []
        self.buffer_lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def send_alert_email(self, subject: str, content: str, priority: str = "Normal"):
        msg = EmailMessage()
        msg["Subject"] = f"[{priority}] {subject}"
        msg["From"] = "automation@company.com"
        msg["To"] = "team-alerts@company.com"
        msg.set_content(content)
        try:
            await aiosmtplib.send(msg, hostname="smtp.company.com", port=25)
        except Exception as e:
            logger.error(f"Email failed: {e}")

    def decrypt_value(self, key: str, token: str) -> str:
        return Fernet(key.encode()).decrypt(token.encode()).decode()

    def encrypt_value(self, plain_text: str) -> (str, str):
        key = Fernet.generate_key()
        return key.decode(), Fernet(key).encrypt(plain_text.encode()).decode()

    async def flush_buffer(self, force: bool = False):
        """Saves results in batches of 20 to ensure tokens are available ASAP."""
        async with self.buffer_lock:
            if len(self.results_buffer) >= SAVE_BATCH_SIZE or (force and self.results_buffer):
                logger.info(f"Writing {len(self.results_buffer)} clusters to DB...")
                ops = [
                    UpdateOne({"cluster_name": r["cluster_name"]}, {"$set": r}, upsert=True)
                    for r in self.results_buffer
                ]
                await self.db[OUTPUT_COLLECTION].bulk_write(ops)
                self.results_buffer.clear()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        reraise=True
    )
    async def call_api(self, client: httpx.AsyncClient, url: str, **kwargs):
        resp = await client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    async def process_cluster(self, name: str, meta: Dict, mapping: Dict, fid_pass: str):
        async with self.semaphore:
            try:
                # 1. API Setup
                api_base = f"https://api.{name}.{meta['openshift']['domain']}:{meta['openshift']['api_port']}"
                user = meta['openshift']['fid_details']['name']
                
                async with httpx.AsyncClient(verify=False, timeout=300.0) as client:
                    # 2. Auth - Get Token
                    auth_url = f"{api_base}/oauth/authorize?response_type=token&client_id=openshift-challenging-client"
                    auth_resp = await self.call_api(client, auth_url, auth=(user, fid_pass))
                    
                    # Extract token from redirect fragment
                    token = auth_resp.url.fragment.split('access_token=')[1].split('&')[0] if '#' in str(auth_resp.url) else "err"
                    
                    # 3. Get Projects
                    proj_resp = await self.call_api(client, f"{api_base}/api/v1/namespaces", headers={"Authorization": f"Bearer {token}"})
                    all_ns = [n['metadata']['name'] for n in proj_resp.json().get('items', [])]
                    filtered = [p for p in all_ns if any(p.startswith(i) for i in meta['openshift']['project_name_identifiers'])]

                    # 4. Encrypt & Buffer
                    b_key, b_token = self.encrypt_value(token)
                    res = {
                        "cluster_name": name,
                        "datacenter": mapping.get("datacenter", "Unknown"),
                        "environment": mapping.get("environment", "Unknown"),
                        "bearer_key": b_key,
                        "bearer_token": b_token,
                        "bearer_token_expiration": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                        "bearer_token_user": user,
                        "api": api_base,
                        "projects": filtered,
                        "metadata": {"batch_sector": self.sector, "batch_env": self.batch_env, "total_projects": len(filtered)},
                        "logdate": datetime.now(timezone.utc).isoformat()
                    }

                    async with self.buffer_lock:
                        self.results_buffer.append(res)
                    await self.flush_buffer()

            except Exception as e:
                self.failures.append({"cluster": name, "error": str(e)})

    async def run(self):
        # 1. Load Metadata
        meta = await self.db.Metadata.find_one({"sector": self.sector, "environment": self.batch_env, "active": True})
        if not meta: return logger.error("Metadata not found.")

        cluster_list = meta["get_clusters"]["manual"]
        
        # 2. Guardrail
        if len(cluster_list) > MAX_CLUSTERS_ALLOWED:
            msg = f"Aborted: {len(cluster_list)} clusters exceeds limit of {MAX_CLUSTERS_ALLOWED}."
            await self.send_alert_email("CRITICAL: Cluster Limit", msg, priority="High")
            sys.exit(1)

        # 3. Mapping Lookup - Handle your specific schema where cluster name is a key
        logger.info("Building mapping dictionary...")
        mappings = {}
        async for doc in self.db.ClusterMappings.find():
            for c_name in cluster_list:
                if c_name in doc:
                    mappings[c_name] = doc[c_name]

        fid_pass = self.decrypt_value(meta['openshift']['fid_details']['decrypter_key'], meta['openshift']['fid_details']['decrypter_token'])

        # 4. TaskGroup Execution (Python 3.12)
        async with asyncio.TaskGroup() as tg:
            for name in cluster_list:
                tg.create_task(self.process_cluster(name, meta, mappings.get(name, {}), fid_pass))

        # 5. Finalize
        await self.flush_buffer(force=True)
        if self.failures:
            f_list = "\n".join([f"{f['cluster']}: {f['error']}" for f in self.failures])
            await self.send_alert_email(f"Failures: {self.sector}", f"Errors:\n{f_list}")

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit("Usage: python Clusters.py <env> <sector>")
    asyncio.run(ClusterProcessor(sys.argv[2], sys.argv[1]).run())




# --- Additional Settings ---
MAX_CLUSTERS_ALLOWED = 200
ALERT_THRESHOLDS = {
    "job_duration_total_sec": 300,  # Alert if job takes > 5 mins
    "cluster_duration_sec": 15,     # Alert if any single cluster takes > 15s
    "failure_percent_limit": 10      # Alert if > 10% of clusters fail
}

class ClusterProcessor:
    def __init__(self, sector: str, batch_env: str):
        # ... existing init ...
        self.cluster_timings = []
        self.failures = [] # List of dicts: {"cluster": name, "error": str, "duration": float}
        self.start_time = None

    async def process_cluster(self, name: str, meta: Dict, mapping: Dict, fid_pass: str):
        async with self.semaphore:
            c_start = time.perf_counter()
            try:
                # ... API Logic ...
                duration = round(time.perf_counter() - c_start, 3)
                
                res = {
                    "cluster_name": name,
                    "processing_duration_sec": duration,
                    "logdate": datetime.now(timezone.utc).isoformat()
                }
                self.cluster_timings.append({"name": name, "duration": duration})

                async with self.buffer_lock:
                    self.results_buffer.append(res)
                await self.flush_buffer()

            except Exception as e:
                duration = round(time.perf_counter() - c_start, 3)
                self.failures.append({"cluster": name, "error": str(e), "duration": duration})
                logger.error(f"❌ {name} failed after {duration}s")

    async def run(self):
        self.start_time = time.perf_counter()
        
        # 1. Load Metadata & Guardrail
        meta = await self.db.Metadata.find_one({"sector": self.sector, "active": True})
        cluster_list = meta.get("get_clusters", {}).get("manual", [])

        if len(cluster_list) > MAX_CLUSTERS_ALLOWED:
            await self.send_alert_email(
                "CRITICAL: Capacity Exceeded", 
                f"Sector {self.sector} has {len(cluster_list)} clusters. Limit is {MAX_CLUSTERS_ALLOWED}."
            )
            return

        # 2. Execution
        async with asyncio.TaskGroup() as tg:
            for name in cluster_list:
                tg.create_task(self.process_cluster(name, meta, {}, "fid_pass_here"))

        await self.flush_buffer(force=True)
        
        # 3. Final Evaluation & Single Alert
        total_time = time.perf_counter() - self.start_time
        await self.evaluate_and_alert(total_time, len(cluster_list))

    async def evaluate_and_alert(self, total_time, total_count):
        alerts = []
        
        # Condition: Overall Time
        if total_time > ALERT_THRESHOLDS["job_duration_total_sec"]:
            alerts.append(f"⚠️ Job exceeded time limit: {total_time:.2f}s (Limit: {ALERT_THRESHOLDS['job_duration_total_sec']}s)")

        # Condition: Failures
        fail_rate = (len(self.failures) / total_count) * 100 if total_count > 0 else 0
        if self.failures:
            alerts.append(f"❌ Failures detected: {len(self.failures)}/{total_count} ({fail_rate:.1f}%)")
        
        # Condition: Individual Slow Clusters
        slow_clusters = [c for c in self.cluster_timings if c['duration'] > ALERT_THRESHOLDS["cluster_duration_sec"]]
        if slow_clusters:
            alerts.append(f"🐢 {len(slow_clusters)} clusters were slower than {ALERT_THRESHOLDS['cluster_duration_sec']}s")

        # If any issues found, send ONE email
        if alerts:
            subject = f"Alert Summary: {self.sector} ({'CRITICAL' if fail_rate > 20 else 'Warning'})"
            content = "The following issues were detected during the cluster refresh:\n\n"
            content += "\n".join(f"- {a}" for a in alerts)
            
            if self.failures:
                content += "\n\nFailure Details:\n" + "\n".join([f"{f['cluster']}: {f['error']}" for f in self.failures])
            
            content += f"\n\nTotal Processing Time: {total_time:.2f}s"
            await self.send_alert_email(subject, content)
            logger.info("📧 Consolidated alert email sent.")
