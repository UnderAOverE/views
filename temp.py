# selfservice/src/common/constants.py
# -----------------------------------------------------------------------------
from enum import Enum

class AppEnvironment(str, Enum):
    """
    Defines the running environment of the application.
    """
    PROD = "prod"
    UAT = "uat"
    DEV = "dev"

class ResourceType(str, Enum):
    """
    Supported Kubernetes/OpenShift Resource types.
    """
    POD = "pod"
    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"

class OperationType(str, Enum):
    """
    Types of operations allowed in the self-service portal.
    """
    RESTART = "restart"
    STOP = "stop"
    START = "start"

class CollectionNames(str, Enum):
    """
    MongoDB Collection names.
    """
    AUDIT = "audit_logs"
    CONFIG = "app_configs"
    ALERTS = "alert_history"

# selfservice/src/common/config/basesettings/mongo.py
# -----------------------------------------------------------------------------
from pydantic_settings import BaseSettings, SettingsConfigDict

class MongoSettings(BaseSettings):
    """
    Configuration for MongoDB Connection.
    Reads from environment variables.
    """
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "selfservice_db"
    MONGO_MIN_POOL_SIZE: int = 10
    MONGO_MAX_POOL_SIZE: int = 50
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# selfservice/src/common/config/basesettings/http.py
# -----------------------------------------------------------------------------
from pydantic_settings import BaseSettings, SettingsConfigDict

class HttpSettings(BaseSettings):
    """
    Configuration for HTTP Clients and SSL Certificates.
    """
    CONNECT_TIMEOUT: int = 10
    READ_TIMEOUT: int = 30
    
    # Certificate Paths (Mounted ConfigMaps/Secrets in OSE)
    CACERT_PATH_PROD: str = "/app/common/certificates/cacerts_prod.pem"
    CACERT_PATH_UAT: str = "/app/common/certificates/cacerts_uat.pem"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# selfservice/src/common/db/exceptions.py
# -----------------------------------------------------------------------------
class DatabaseConnectionError(Exception):
    """Raised when DB connection fails during initialization."""
    pass

class ConfigurationError(Exception):
    """Raised when a required DB configuration document is missing."""
    pass

# selfservice/src/common/db/motor_repository.py
# -----------------------------------------------------------------------------
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from selfservice.src.common.config.basesettings.mongo import MongoSettings

class Database:
    """
    Singleton-style container for the Motor Client.
    Initialized in initializer.py.
    """
    client: Optional[AsyncIOMotorClient] = None
    db_name: str = MongoSettings().MONGO_DB_NAME

# Global instance
db_instance = Database()

async def get_database() -> AsyncIOMotorDatabase:
    """
    Dependency Injection provider for FastAPI routes.
    Returns the active database instance.
    """
    if db_instance.client is None:
        # This should theoretically not happen if lifespan works, but safety first
        raise ConnectionError("Database client is not initialized.")
    return db_instance.client[db_instance.db_name]

# selfservice/src/common/alerts.py
# -----------------------------------------------------------------------------
import logging
from datetime import datetime
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from selfservice.src.common.constants import CollectionNames

logger = logging.getLogger(__name__)

async def send_email_alert(
    subject: str, 
    body: str, 
    db: AsyncIOMotorDatabase
) -> None:
    """
    Fetches recipients from MongoDB and sends an alert email.
    
    Args:
        subject: Email subject line.
        body: Email body content.
        db: Database connection.
    """
    try:
        # 1. Dynamic Recipient Management via Mongo
        config_doc = await db[CollectionNames.CONFIG].find_one({"_id": "alert_recipients"})
        
        recipients: List[str]
        if config_doc and "emails" in config_doc:
            recipients = config_doc["emails"]
        else:
            # Fallback
            recipients = ["admin@example.com"]
            logger.warning("Alert recipient config not found in DB, using default.")

        # 2. Log the attempt (Mocking SMTP for this example)
        # In production: use aiosmtplib to send actual email
        logger.error(f"!!! ALERT !!! Sending email to {recipients} | Subject: {subject} | Body: {body[:100]}...")
        
        # 3. Record alert in DB for history
        await db[CollectionNames.ALERTS].insert_one({
            "timestamp": datetime.utcnow(),
            "recipients": recipients,
            "subject": subject,
            "body": body,
            "status": "SENT"
        })

    except Exception as e:
        logger.critical(f"Failed to send alert email mechanism: {str(e)}")

# selfservice/src/common/http/exceptions.py
# -----------------------------------------------------------------------------
class ExternalServiceError(Exception):
    """Base class for external API failures (OpenShift/AWS)."""
    def __init__(self, service_name: str, status_code: int, message: str):
        self.service_name = service_name
        self.status_code = status_code
        self.message = message
        super().__init__(f"{service_name} failed with {status_code}: {message}")

# selfservice/src/common/http/client_async.py
# -----------------------------------------------------------------------------
import httpx
import ssl
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from selfservice.src.common.config.basesettings.http import HttpSettings
from selfservice.src.common.http.exceptions import ExternalServiceError
from selfservice.src.common.alerts import send_email_alert

http_settings = HttpSettings()

class AsyncHttpClient:
    """
    A wrapper around httpx.AsyncClient that handles:
    1. SSL Context loading (Prod vs UAT).
    2. Automatic Error alerting via Email.
    """
    def __init__(self, env: str = "prod"):
        self.env = env
        self.ssl_context = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """
        Creates an SSL context with the specific CA certs required 
        for the OSE environment.
        """
        ctx = ssl.create_default_context()
        
        # In a real container, these files must exist. 
        # Check verify_mode carefully for Prod.
        cert_path = http_settings.CACERT_PATH_PROD if self.env == "prod" else http_settings.CACERT_PATH_UAT
        
        # ctx.load_verify_locations(cafile=cert_path) 
        # For this code block to run without actual files, we disable verification
        ctx.check_hostname = False 
        ctx.verify_mode = ssl.CERT_NONE 
        return ctx

    async def request(
        self, 
        method: str, 
        url: str, 
        db: AsyncIOMotorDatabase,
        headers: Dict[str, str] = {},
        json_body: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None
    ) -> httpx.Response:
        """
        Executes HTTP request. If status != 2xx, triggers alert and raises exception.
        """
        async with httpx.AsyncClient(verify=self.ssl_context, timeout=http_settings.READ_TIMEOUT) as client:
            try:
                response = await client.request(
                    method=method, 
                    url=url, 
                    headers=headers, 
                    json=json_body,
                    content=content
                )
                
                # Alert on Logic Errors (4xx, 5xx)
                if response.status_code >= 400:
                    error_msg = f"Method: {method} | URL: {url} | Response: {response.text}"
                    await send_email_alert(
                        subject=f"External Service Error: {response.status_code}",
                        body=error_msg,
                        db=db
                    )
                    raise ExternalServiceError("OpenShiftAPI", response.status_code, response.text)
                
                return response

            except httpx.RequestError as exc:
                # Alert on Connection Errors
                await send_email_alert(
                    subject=f"HTTP Connection Failed: {url}",
                    body=str(exc),
                    db=db
                )
                raise ExternalServiceError("OpenShiftAPI", 503, f"Connection Error: {str(exc)}")

# selfservice/src/apis/ose/config/basesettings/ose_config.py
# -----------------------------------------------------------------------------
from pydantic_settings import BaseSettings, SettingsConfigDict

class OseSettings(BaseSettings):
    """
    OpenShift specific configurations.
    """
    OSE_API_URL: str = "https://api.openshift.example.com:6443"
    OSE_TOKEN: str = "sha256~mock_token_usually_in_env_vars" 
    
    model_config = SettingsConfigDict(env_file=".env", prefix="OSE_")

# selfservice/src/apis/ose/models/payloads.py
# -----------------------------------------------------------------------------
from pydantic import BaseModel, Field
from typing import List, Optional
from selfservice.src.common.constants import ResourceType

class ResourceIdentifier(BaseModel):
    """
    Identifies a specific resource in OpenShift.
    """
    namespace: str = Field(..., example="my-app-prod")
    name: str = Field(..., example="backend-service")

class RestartRequest(BaseModel):
    """
    Payload for Restart API.
    """
    resource_type: ResourceType
    targets: List[ResourceIdentifier]
    reason: str = Field(..., min_length=5, description="Audit requires a reason")

class StopStartRequest(BaseModel):
    """
    Payload for Stop/Start API.
    """
    resource_type: ResourceType
    targets: List[ResourceIdentifier]
    replicas: Optional[int] = Field(1, ge=0, description="Target replicas for Start. Ignored for Stop.")

class PodInfo(BaseModel):
    """
    Response model for Pod Fetching.
    """
    name: str
    namespace: str
    status: str
    restart_count: int
    start_time: Optional[str]

class PaginatedResponse(BaseModel):
    """
    Standardized Pagination Wrapper.
    """
    total_available: int
    returned_count: int
    data: List[PodInfo]

# selfservice/src/apis/ose/services/ose_service.py
# -----------------------------------------------------------------------------
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from fastapi import HTTPException

from selfservice.src.common.http.client_async import AsyncHttpClient
from selfservice.src.apis.ose.config.basesettings.ose_config import OseSettings
from selfservice.src.common.constants import ResourceType, CollectionNames
from selfservice.src.apis.ose.models.payloads import ResourceIdentifier, PodInfo
from motor.motor_asyncio import AsyncIOMotorDatabase

class OseService:
    """
    Business Logic layer for OpenShift interactions.
    Directly uses Native HTTP APIs.
    """
    def __init__(self, http_client: AsyncHttpClient, db: AsyncIOMotorDatabase):
        self.client = http_client
        self.settings = OseSettings()
        self.db = db
        self.headers = {
            "Authorization": f"Bearer {self.settings.OSE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _get_limit_config(self, config_key: str, default: int) -> int:
        """Helper to get limits from Mongo Config Collection."""
        doc = await self.db[CollectionNames.CONFIG].find_one({"_id": config_key})
        return doc["value"] if doc else default

    async def fetch_pods(self, namespace: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetches pods for a namespace.
        Note: Native K8s pagination uses 'continue' tokens. For this framework,
        we are limiting simple fetch to strict numbers.
        """
        url = f"{self.settings.OSE_API_URL}/api/v1/namespaces/{namespace}/pods"
        
        # Using query params for limit
        url += f"?limit={limit}"
        
        response = await self.client.request("GET", url, self.db, headers=self.headers)
        data = response.json()
        
        items = data.get("items", [])
        
        # Map raw K8s JSON to Pydantic Model
        parsed_pods: List[PodInfo] = []
        for pod in items:
            # Safe navigation of dict
            status_phase = pod.get("status", {}).get("phase", "Unknown")
            container_statuses = pod.get("status", {}).get("containerStatuses", [])
            restart_count = container_statuses[0].get("restartCount", 0) if container_statuses else 0
            start_time = pod.get("status", {}).get("startTime")

            parsed_pods.append(PodInfo(
                name=pod["metadata"]["name"],
                namespace=pod["metadata"]["namespace"],
                status=status_phase,
                restart_count=restart_count,
                start_time=start_time
            ))
            
        return {"items": parsed_pods, "total": len(parsed_pods)} # K8s doesn't give total count easily without list

    async def _restart_pod(self, target: ResourceIdentifier) -> None:
        """Delete a POD to force restart."""
        url = f"{self.settings.OSE_API_URL}/api/v1/namespaces/{target.namespace}/pods/{target.name}"
        await self.client.request("DELETE", url, self.db, headers=self.headers)

    async def _rollout_workload(self, target: ResourceIdentifier, r_type: ResourceType) -> None:
        """
        Restarts Deployment/StatefulSet via Annotation Patch (kubectl rollout restart).
        """
        # Determine API endpoint
        api_group = "apis/apps/v1"
        endpoint = f"{r_type.value}s" # deployments or statefulsets
        
        url = f"{self.settings.OSE_API_URL}/{api_group}/namespaces/{target.namespace}/{endpoint}/{target.name}"
        
        # Strategic Merge Patch Payload
        patch_data = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "selfservice.framework/restartedAt": datetime.utcnow().isoformat()
                        }
                    }
                }
            }
        }
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/strategic-merge-patch+json"
        
        await self.client.request("PATCH", url, self.db, headers=headers, content=json.dumps(patch_data))

    async def _scale_workload(self, target: ResourceIdentifier, r_type: ResourceType, replicas: int) -> None:
        """
        Scales a workload to specific replicas (0 for Stop, N for Start).
        """
        api_group = "apis/apps/v1"
        endpoint = f"{r_type.value}s"
        
        url = f"{self.settings.OSE_API_URL}/{api_group}/namespaces/{target.namespace}/{endpoint}/{target.name}/scale"
        
        # Merge Patch for Scale Subresource
        patch_data = {"spec": {"replicas": replicas}}
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/merge-patch+json"
        
        await self.client.request("PATCH", url, self.db, headers=headers, content=json.dumps(patch_data))

    async def bulk_restart(self, targets: List[ResourceIdentifier], r_type: ResourceType) -> None:
        """
        Orchestrates bulk restart operations. Checks Mongo limits first.
        """
        max_ops = await self._get_limit_config("max_bulk_ops", 5)
        if len(targets) > max_ops:
            raise HTTPException(400, f"Too many targets. Max allowed is {max_ops}")

        # Create tasks list
        tasks = []
        for target in targets:
            if r_type == ResourceType.POD:
                tasks.append(self._restart_pod(target))
            else:
                tasks.append(self._rollout_workload(target, r_type))
        
        # Execute concurrently
        await asyncio.gather(*tasks)

    async def bulk_scale(self, targets: List[ResourceIdentifier], r_type: ResourceType, replicas: int) -> None:
        """
        Orchestrates bulk stop/start.
        """
        max_ops = await self._get_limit_config("max_bulk_ops", 5)
        if len(targets) > max_ops:
            raise HTTPException(400, f"Too many targets. Max allowed is {max_ops}")

        tasks = [self._scale_workload(t, r_type, replicas) for t in targets]
        await asyncio.gather(*tasks)

# selfservice/src/apis/ose/utils/audit.py
# -----------------------------------------------------------------------------
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from selfservice.src.common.constants import CollectionNames, OperationType

async def audit_log(
    db: AsyncIOMotorDatabase,
    operation: OperationType,
    details: dict,
    user: str = "system",
    status: str = "SUCCESS"
) -> None:
    """
    Writes operation details to the MongoDB Audit Collection.
    """
    doc = {
        "timestamp": datetime.utcnow(),
        "operation": operation.value,
        "user": user,
        "status": status,
        "details": details
    }
    await db[CollectionNames.AUDIT].insert_one(doc)

# selfservice/src/apis/ose/routes/pods.py
# -----------------------------------------------------------------------------
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from selfservice.src.common.db.motor_repository import get_database
from selfservice.src.common.http.client_async import AsyncHttpClient
from selfservice.src.apis.ose.services.ose_service import OseService
from selfservice.src.apis.ose.models.payloads import PaginatedResponse

router = APIRouter()

def get_ose_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> OseService:
    return OseService(AsyncHttpClient(), db)

@router.get("/{namespace}", response_model=PaginatedResponse, summary="Fetch Pods")
async def fetch_pods(
    namespace: str,
    limit: int = Query(20, description="Max number of pods to fetch"),
    service: OseService = Depends(get_ose_service)
) -> PaginatedResponse:
    """
    Fetches a list of pods from the specified OpenShift Namespace.
    """
    result = await service.fetch_pods(namespace, limit)
    return PaginatedResponse(
        total_available=result["total"],
        returned_count=len(result["items"]),
        data=result["items"]
    )

# selfservice/src/apis/ose/routes/restart.py
# -----------------------------------------------------------------------------
from fastapi import APIRouter, Depends, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from selfservice.src.common.db.motor_repository import get_database
from selfservice.src.apis.ose.services.ose_service import OseService, get_ose_service
from selfservice.src.apis.ose.models.payloads import RestartRequest
from selfservice.src.apis.ose.utils.audit import audit_log
from selfservice.src.common.constants import OperationType

router = APIRouter()

@router.post("/", summary="Restart Resources")
async def restart_resources(
    payload: RestartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    service: OseService = Depends(get_ose_service)
) -> dict:
    """
    Restarts Pods (Delete), Deployments (Rollout), or StatefulSets (Rollout).
    Logs the action to Audit Collection.
    """
    # Execute Operation
    await service.bulk_restart(payload.targets, payload.resource_type)
    
    # Audit (Background Task to ensure response speed)
    audit_payload = {
        "targets": [t.dict() for t in payload.targets],
        "resource_type": payload.resource_type,
        "reason": payload.reason
    }
    background_tasks.add_task(
        audit_log, db, OperationType.RESTART, audit_payload
    )

    return {"status": "success", "message": f"Restart initiated for {len(payload.targets)} resources"}

# selfservice/src/apis/ose/routes/stop.py
# -----------------------------------------------------------------------------
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from selfservice.src.common.db.motor_repository import get_database
from selfservice.src.apis.ose.services.ose_service import OseService, get_ose_service
from selfservice.src.apis.ose.models.payloads import StopStartRequest
from selfservice.src.apis.ose.utils.audit import audit_log
from selfservice.src.common.constants import OperationType, ResourceType

router = APIRouter()

@router.post("/", summary="Stop Resources")
async def stop_resources(
    payload: StopStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    service: OseService = Depends(get_ose_service)
) -> dict:
    """
    Scales Deployments or StatefulSets to 0.
    """
    if payload.resource_type == ResourceType.POD:
        raise HTTPException(400, "Cannot 'Stop' individual pods. Use Restart/Delete.")

    await service.bulk_scale(payload.targets, payload.resource_type, 0)
    
    audit_payload = {"targets": [t.dict() for t in payload.targets], "type": payload.resource_type}
    background_tasks.add_task(audit_log, db, OperationType.STOP, audit_payload)

    return {"status": "success", "message": f"Stop initiated for {len(payload.targets)} resources"}

# selfservice/src/apis/ose/routes/start.py
# -----------------------------------------------------------------------------
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from selfservice.src.common.db.motor_repository import get_database
from selfservice.src.apis.ose.services.ose_service import OseService, get_ose_service
from selfservice.src.apis.ose.models.payloads import StopStartRequest
from selfservice.src.apis.ose.utils.audit import audit_log
from selfservice.src.common.constants import OperationType, ResourceType

router = APIRouter()

@router.post("/", summary="Start Resources")
async def start_resources(
    payload: StopStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    service: OseService = Depends(get_ose_service)
) -> dict:
    """
    Scales Deployments or StatefulSets to N replicas (default 1).
    """
    if payload.resource_type == ResourceType.POD:
        raise HTTPException(400, "Cannot 'Start' individual pods.")

    replicas = payload.replicas if payload.replicas is not None else 1
    
    await service.bulk_scale(payload.targets, payload.resource_type, replicas)
    
    audit_payload = {
        "targets": [t.dict() for t in payload.targets], 
        "type": payload.resource_type,
        "replicas": replicas
    }
    background_tasks.add_task(audit_log, db, OperationType.START, audit_payload)

    return {"status": "success", "message": f"Start initiated for {len(payload.targets)} resources"}

# selfservice/src/initializer.py
# -----------------------------------------------------------------------------
from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from selfservice.src.common.config.basesettings.mongo import MongoSettings
from selfservice.src.common.db.motor_repository import db_instance

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler.
    Opens the DB connection on Startup and closes it on Shutdown.
    This ensures the connection pool persists for the POD's lifetime.
    """
    settings = MongoSettings()
    print(f"Initializing MongoDB Connection at {settings.MONGO_URL}...")
    
    # Create Client with pooling options
    db_instance.client = AsyncIOMotorClient(
        settings.MONGO_URL,
        minPoolSize=settings.MONGO_MIN_POOL_SIZE,
        maxPoolSize=settings.MONGO_MAX_POOL_SIZE
    )
    
    # Test Connection
    try:
        await db_instance.client.admin.command('ping')
        print("MongoDB Connection Established.")
    except Exception as e:
        print(f"CRITICAL: MongoDB Connection Failed: {e}")
        raise e

    yield # Application traffic handled here

    print("Closing MongoDB Connection...")
    db_instance.client.close()

# selfservice/src/main.py
# -----------------------------------------------------------------------------
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from selfservice.src.initializer import lifespan
from selfservice.src.apis.ose.routes import pods, restart, stop, start

# Metadata for Swagger UI
tags_metadata = [
    {"name": "OSE Fetch", "description": "Read-only operations for OpenShift"},
    {"name": "OSE Operations", "description": "State-changing operations (Restart/Stop/Start)"},
]

app = FastAPI(
    title="Self Service Framework",
    description="Unified API for AWS and OpenShift Resource Management",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(pods.router, prefix="/api/v1/ose/pods", tags=["OSE Fetch"])
app.include_router(restart.router, prefix="/api/v1/ose/restart", tags=["OSE Operations"])
app.include_router(stop.router, prefix="/api/v1/ose/stop", tags=["OSE Operations"])
app.include_router(start.router, prefix="/api/v1/ose/start", tags=["OSE Operations"])

@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """K8s Liveness Probe Endpoint"""
    return {"status": "alive"}

# main.sh
# -----------------------------------------------------------------------------
#!/bin/bash
# Set Python Path to allow absolute imports from project root
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run Uvicorn
# Workers should generally be 1 inside a container, OSE manages scaling replicas
exec python3 -m uvicorn selfservice.src.main:app --host 0.0.0.0 --port 8000 --log-level info
