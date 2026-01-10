
Waiting Threshold: This is your most important alert. If this is high, your "Concurrency Limit" is too low or your Database is too slow.
• Total Threshold: This protects your RAM. If this gets too high, the Python process might be killed by the OS (OOM Killer).



# infrastructure.py
# =========
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self):
        self._tasks = set()

    def run(self, func, *args, **kwargs):
        """Creates a tracked task and adds it to the set to prevent GC."""
        task = asyncio.create_task(func(*args, **kwargs))
        self._tasks.add(task)
        # Remove from set automatically when finished
        task.add_done_callback(self._tasks.discard)

    async def wait_for_completion(self, timeout: int = 10):
        """Gracefully awaits all running tasks during shutdown."""
        if not self._tasks:
            return
            
        logger.info(f"Draining {len(self._tasks)} background tasks...")
        done, pending = await asyncio.wait(self._tasks, timeout=timeout)
        
        for t in pending:
            logger.warning(f"Task {t.get_name()} timed out during shutdown. Cancelling.")
            t.cancel()

# Global instance to be imported by routes
task_manager = TaskManager()


# services/audit.py
# =========
import asyncio
import pymongo
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((pymongo.errors.AutoReconnect, pymongo.errors.ServerSelectionTimeoutError)),
    reraise=True
)
async def db_insert_logic(client, payload: dict):
    """Low-level DB insert with retries for 'blips'."""
    # Enforce a strict timeout for the DB operation itself
    async with asyncio.timeout(5):
        db = client["ops_db"]
        await db.audit_logs.insert_one(payload)

async def send_email_logic(email: str, content: str):
    """Mock for email sending logic."""
    async with asyncio.timeout(5):
        # Your email client (SendGrid, SES, etc) goes here
        await asyncio.sleep(1) 
        print(f"Email sent to {email}")

async def full_audit_workflow(client, payload: dict, email: str):
    """The high-level orchestrator for the background work."""
    try:
        # 1. Database Insert
        await db_insert_logic(client, payload)
        
        # 2. Email Notification
        await send_email_logic(email, f"Success for {payload['cluster']}")
        
    except asyncio.TimeoutError:
        logger.error("Operation timed out after retries.")
    except Exception as e:
        logger.error(f"Background workflow failed: {e}")


# routes/restart.py
# =========
from fastapi import APIRouter, BackgroundTasks, Request
# from ..infrastructure import task_manager  # Use relative or absolute import based on your setup
# from ..services.audit import full_audit_workflow

router = APIRouter()

@router.post("/restart")
async def restart_cluster(background_tasks: BackgroundTasks, request: Request):
    # This represents your operational data
    payload = {"cluster": "production-aws", "status": "restarting"}
    user_email = "admin@company.com"
    
    # We offload the work to the TaskManager
    # Note: request.app.state.mongo_client is shared from lifespan
    background_tasks.add_task(
        task_manager.run,
        full_audit_workflow,
        request.app.state.mongo_client,
        payload,
        user_email
    )
    
    return {"message": "Restart initiated. Audit and email queued."}


# main.py
# =========
from fastapi import FastAPI
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
# from .infrastructure import task_manager
# from .routes import restart

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    # Create the Motor client once and store it in app state
    app.state.mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
    print("Database connection established.")
    
    yield
    
    # SHUTDOWN
    print("Shutting down... waiting for background tasks.")
    # Give tasks 10 seconds to finish before we close the DB client
    await task_manager.wait_for_completion(timeout=10)
    app.state.mongo_client.close()
    print("Database connection closed.")

app = FastAPI(lifespan=lifespan)

# Include the modular route
app.include_router(router)


# services/audit.py
# =========
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = logging.getLogger(__name__)

# This helper function creates a log entry every time a retry is triggered
def log_retry_attempt(retry_state):
    logger.warning(
        f"Retrying {retry_state.fn.__name__}: "
        f"attempt #{retry_state.attempt_number} ended with exception: {retry_state.outcome.exception()}. "
        f"Waiting {retry_state.next_action.sleep}s before next attempt."
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((pymongo.errors.AutoReconnect, pymongo.errors.ServerSelectionTimeoutError)),
    before_sleep=log_retry_attempt, # <--- The hook
    reraise=True
)
async def db_insert_logic(client, payload: dict):
    async with asyncio.timeout(5):
        db = client["ops_db"]
        await db.audit_logs.insert_one(payload)


wait=wait_exponential(multiplier=1, min=2, max=10) + wait_random(0, 1)


# infrastructure.py
# =========
import asyncio

class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 10):
        self._tasks = set()
        # The semaphore acts as the concurrency limit
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)

    def run(self, func, *args, **kwargs):
        # We wrap the function in our semaphore-controlled runner
        task = asyncio.create_task(self._run_with_semaphore(func, *args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_with_semaphore(self, func, *args, **kwargs):
        """Internal wrapper that waits for a 'slot' to be available."""
        async with self._semaphore:
            try:
                await func(*args, **kwargs)
            except Exception as e:
                # Log it here or let the specific service handle it
                print(f"Task failed: {e}")

    async def wait_for_completion(self, timeout: int = 10):
        if not self._tasks:
            return
        done, pending = await asyncio.wait(self._tasks, timeout=timeout)
        for t in pending:
            t.cancel()

# Initialize with a limit (e.g., 10 concurrent database/email operations)
task_manager = TaskManager(max_concurrent_tasks=10)


# infrastructure.py
# =========
import asyncio
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_host="smtp.gmail.com", port=587, user=None, password=None):
        self.smtp_host = smtp_host
        self.port = port
        self.user = user
        self.password = password

    async def send_alert(self, subject, body, to_email):
        """Sends a synchronous email alert using asyncio.to_thread to avoid blocking."""
        def _send():
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = self.user
            msg['To'] = to_email
            try:
                with smtplib.SMTP(self.smtp_host, self.port) as server:
                    server.starttls()
                    server.login(self.user, self.password)
                    server.send_message(msg)
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")

        await asyncio.to_thread(_send)

class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 10, wait_timeout: int = 60):
        self._tasks = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._wait_timeout = wait_timeout # Max time a task can stay in 'Waiting' status
        self._waiting_count = 0

    def run(self, func, *args, **kwargs):
        task = asyncio.create_task(self._run_with_semaphore(func, *args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_with_semaphore(self, func, *args, **kwargs):
        self._waiting_count += 1
        try:
            # wait_for adds a timeout to the act of ACQUIRING the semaphore
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._wait_timeout)
            self._waiting_count -= 1
            
            try:
                await func(*args, **kwargs)
            finally:
                self._semaphore.release()
                
        except asyncio.TimeoutError:
            self._waiting_count -= 1
            logger.error(f"Task {func.__name__} timed out waiting for a semaphore slot.")
            # Trigger Email Alert
            alert_service = EmailService(user="alerts@yourcompany.com", password="app-password")
            await alert_service.send_alert(
                subject="CRITICAL: Background Task Queue Bottleneck",
                body=f"Task {func.__name__} was cancelled after waiting {self._wait_timeout}s for a slot.",
                to_email="admin@yourcompany.com"
            )
        except Exception as e:
            logger.error(f"Task execution error: {e}")

    async def wait_for_completion(self, timeout: int = 10):
        if not self._tasks: return
        done, pending = await asyncio.wait(self._tasks, timeout=timeout)
        for t in pending: t.cancel()

# Global instances
task_manager = TaskManager(max_concurrent_tasks=10, wait_timeout=30)

# services/audit.py
# =========
# (Same logic as before, including @retry for Mongo)
async def full_audit_workflow(client, payload):
    # Your Mongo + Success Email logic
    ...

# routes/restart.py
# =========
from fastapi import APIRouter, BackgroundTasks, Request
# Import task_manager and full_audit_workflow

router = APIRouter()

@router.post("/restart")
async def restart(background_tasks: BackgroundTasks, request: Request):
    background_tasks.add_task(
        task_manager.run,
        full_audit_workflow,
        request.app.state.mongo_client,
        {"cluster": "test-zone"}
    )
    return {"status": "accepted"}

# main.py
# =========
# (Same lifespan logic as before)



# infrastructure.py
# =========
import asyncio
import logging
from .services.email import email_service # Assuming your email logic is here

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 10, wait_timeout: int = 60):
        self._tasks = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._waiting_count = 0
        
        # ALERT THRESHOLDS
        self.WAITING_THRESHOLD = 50  # Alert if > 50 tasks are stuck in line
        self.TOTAL_THRESHOLD = 100   # Alert if > 100 total tasks are in memory
        self._alert_sent = False     # Prevent "Email Storms" (spamming alerts)

    # ... (Keep existing run and _run_with_semaphore methods) ...

    async def monitor_queue_health(self):
        """A background loop that runs for the life of the app."""
        while True:
            try:
                waiting = self.waiting_tasks
                total = len(self._tasks)

                if (waiting > self.WAITING_THRESHOLD or total > self.TOTAL_THRESHOLD) and not self._alert_sent:
                    await email_service.send_alert(
                        subject="⚠️ ALERT: Queue Congestion",
                        body=f"Queue is backing up!\nWaiting: {waiting}\nTotal: {total}",
                        to_email="admin@company.com"
                    )
                    self._alert_sent = True # Don't email again until it clears
                    logger.error("Queue threshold exceeded. Alert sent.")

                # Reset the alert flag if the queue clears
                elif waiting < (self.WAITING_THRESHOLD / 2) and total < (self.TOTAL_THRESHOLD / 2):
                    self._alert_sent = False

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(10) # Check every 10 seconds

task_manager = TaskManager()


# main.py
# =========
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
    
    # Start the monitoring loop in the background
    monitor_task = asyncio.create_task(task_manager.monitor_queue_health())
    
    yield
    
    # Shutdown
    monitor_task.cancel() # Stop the monitor
    await task_manager.wait_for_completion(timeout=10)
    app.state.mongo_client.close()


@router.get("/queue-status")
async def get_queue_status():
    waiting = task_manager.waiting_tasks
    is_healthy = waiting < task_manager.WAITING_THRESHOLD
    
    return {
        "status": "HEALTHY" if is_healthy else "CONGESTED",
        "running_total": len(task_manager._tasks),
        "active_slots_busy": task_manager.active_tasks,
        "tasks_waiting_in_line": waiting,
        "threshold_limit": task_manager.WAITING_THRESHOLD
    }


# infrastructure.py
# =========
class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 10, wait_timeout: int = 60):
        self._tasks = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._waiting_count = 0
        
        # Monitoring State
        self._monitoring_enabled = True  # The "Pause" flag
        self._alert_sent = False
        self.WAITING_THRESHOLD = 50

    def toggle_monitoring(self, status: bool):
        """Method to pause or resume alerts."""
        self._monitoring_enabled = status
        # If we pause, reset the alert flag so it can fire fresh when resumed
        if not status:
            self._alert_sent = False
        logger.info(f"Queue monitoring {'enabled' if status else 'paused'}")

    async def monitor_queue_health(self):
        while True:
            try:
                # Only run alert logic if monitoring is enabled
                if self._monitoring_enabled:
                    waiting = self.waiting_tasks
                    if waiting > self.WAITING_THRESHOLD and not self._alert_sent:
                        # ... (Existing email alert logic) ...
                        self._alert_sent = True
                    elif waiting < (self.WAITING_THRESHOLD / 2):
                        self._alert_sent = False
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            await asyncio.sleep(10)




# routes/metrics.py
# =========
from fastapi import APIRouter, HTTPException
from ..infrastructure import task_manager

router = APIRouter()

@router.post("/monitoring/pause")
async def pause_monitoring():
    """Stop the background monitor from sending email alerts."""
    task_manager.toggle_monitoring(False)
    return {"message": "Monitoring paused. No alerts will be sent."}

@router.post("/monitoring/resume")
async def resume_monitoring():
    """Resume the background monitor."""
    task_manager.toggle_monitoring(True)
    return {"message": "Monitoring resumed."}

@router.get("/queue-status")
async def get_queue_status():
    return {
        "monitoring_active": task_manager._monitoring_enabled,
        "running_total": len(task_manager._tasks),
        "tasks_waiting_in_line": task_manager.waiting_tasks,
        "alert_triggered": task_manager._alert_sent
    }


# auth.py
# =========
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import os

# In production, this should be in an environment variable
API_KEY = os.getenv("ADMIN_API_KEY", "super-secret-key-123")
API_KEY_NAME = "X-Admin-Token"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_admin_key(header_value: str = Security(api_key_header)):
    if header_value == API_KEY:
        return header_value
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate admin credentials",
    )


# routes/metrics.py
# =========
from fastapi import APIRouter, Depends
from ..infrastructure import task_manager
from ..auth import get_admin_key

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/monitoring/pause", dependencies=[Depends(get_admin_key)])
async def pause_monitoring():
    task_manager.toggle_monitoring(False)
    return {"message": "Monitoring paused."}

@router.post("/monitoring/resume", dependencies=[Depends(get_admin_key)])
async def resume_monitoring():
    task_manager.toggle_monitoring(True)
    return {"message": "Monitoring resumed."}

@router.get("/queue-status", dependencies=[Depends(get_admin_key)])
async def get_queue_status():
    return {
        "monitoring_active": task_manager._monitoring_enabled,
        "running_total": len(task_manager._tasks),
        "tasks_waiting_in_line": task_manager.waiting_tasks
    }



