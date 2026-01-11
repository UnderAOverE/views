import asyncio
import logging
import time
import os
import smtplib
from email.message import EmailMessage
from typing import Annotated, Set, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, status, Security
from fastapi.security.api_key import APIKeyHeader

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Security Config
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "test-secret-123")
API_KEY_NAME = "X-Admin-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# --- INFRASTRUCTURE: EMAIL SERVICE ---
class EmailService:
    def __init__(self):
        self.user = os.getenv("EMAIL_USER", "alerts@example.com")
        self.password = os.getenv("EMAIL_PASS", "password")
        self.smtp_host = "smtp.gmail.com"
        self.port = 587

    async def send_alert(self, subject: str, body: str, to_email: str):
        """Sends email without blocking the event loop."""
        def _sync_send():
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
                logger.error(f"SMTP Error: {e}")

        await asyncio.to_thread(_sync_send)

email_service = EmailService()

# --- INFRASTRUCTURE: TASK MANAGER ---
class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 10, wait_timeout: int = 60):
        self._tasks: Set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._max_limit = max_concurrent_tasks
        self._wait_timeout = wait_timeout
        
        self._waiting_count = 0
        self._monitoring_enabled = True
        self._alert_sent = False
        self._is_shutting_down = False
        self.WAITING_THRESHOLD = 50

    @property
    def waiting_tasks(self) -> int:
        return self._waiting_count

    @property
    def active_tasks(self) -> int:
        return self._max_limit - self._semaphore._value

    @property
    def available_slots(self) -> int:
        return self._semaphore._value

    @property
    def total_tracked(self) -> int:
        return len(self._tasks)

    @property
    def is_draining(self) -> bool:
        return self._is_shutting_down

    def run(self, func: Callable, *args, **kwargs):
        """Schedules a task on the running event loop."""
        if self._is_shutting_down:
            logger.warning("Shutdown in progress. Task rejected.")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        task = loop.create_task(self._run_with_semaphore(func, *args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_with_semaphore(self, func, *args, **kwargs):
        self._waiting_count += 1
        try:
            # Phase 1: Wait for a slot in the semaphore
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._wait_timeout)
            self._waiting_count -= 1
            
            # Phase 2: Execute the actual work
            try:
                await func(*args, **kwargs)
            finally:
                self._semaphore.release()
                
        except asyncio.TimeoutError:
            self._waiting_count -= 1
            logger.error(f"Task {func.__name__} timed out waiting for a semaphore slot.")
            if self._monitoring_enabled:
                await email_service.send_alert(
                    "Queue Timeout Alert", 
                    f"Task {func.__name__} timed out after {self._wait_timeout}s",
                    "admin@example.com"
                )
        except Exception as e:
            logger.error(f"Task Execution Error: {e}")

    async def monitor_queue_health(self):
        """Background loop to check for congestion."""
        while True:
            if self._monitoring_enabled and not self._is_shutting_down:
                if self.waiting_tasks > self.WAITING_THRESHOLD and not self._alert_sent:
                    await email_service.send_alert(
                        "⚠️ CRITICAL: Queue Congestion",
                        f"Waiting: {self.waiting_tasks} | Active: {self.active_tasks}",
                        "admin@example.com"
                    )
                    self._alert_sent = True
                elif self.waiting_tasks < (self.WAITING_THRESHOLD / 2):
                    self._alert_sent = False
            await asyncio.sleep(10)

    async def wait_for_completion(self, timeout: int = 10):
        """Graceful shutdown logic."""
        self._is_shutting_down = True
        if not self._tasks:
            return
        logger.info(f"Draining {len(self._tasks)} tasks...")
        done, pending = await asyncio.wait(self._tasks, timeout=timeout)
        for t in pending:
            t.cancel()

# --- DEPENDENCIES ---
async def get_admin_key(header_value: str = Security(api_key_header)):
    if header_value == ADMIN_API_KEY:
        return header_value
    raise HTTPException(status_code=403, detail="Invalid Admin Token")

async def get_task_manager(request: Request) -> TaskManager:
    return request.app.state.task_manager

TaskManagerDep = Annotated[TaskManager, Depends(get_task_manager)]

# --- APP SETUP & ROUTES ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize
    tm = TaskManager(max_concurrent_tasks=10, wait_timeout=30)
    app.state.task_manager = tm
    
    # Start monitor
    monitor_task = asyncio.create_task(tm.monitor_queue_health())
    yield
    # Cleanup
    monitor_task.cancel()
    await tm.wait_for_completion(timeout=15)

app = FastAPI(lifespan=lifespan)

@app.post("/restart")
async def trigger_restart(tm: TaskManagerDep):
    # Dummy service function for demonstration
    async def dummy_service():
        await asyncio.sleep(5)
        
    tm.run(dummy_service)
    return {"status": "accepted"}

@app.get("/admin/status", dependencies=[Depends(get_admin_key)])
async def get_status(tm: TaskManagerDep):
    return {
        "is_monitoring": tm._monitoring_enabled,
        "is_draining": tm.is_draining,
        "active_tasks": tm.active_tasks,
        "waiting_tasks": tm.waiting_tasks,
        "available_slots": tm.available_slots,
        "total_tracked": tm.total_tracked
    }

@app.post("/admin/pause", dependencies=[Depends(get_admin_key)])
async def pause_alerts(tm: TaskManagerDep):
    tm._monitoring_enabled = False
    return {"message": "Alerting paused"}

@app.post("/admin/resume", dependencies=[Depends(get_admin_key)])
async def resume_alerts(tm: TaskManagerDep):
    tm._monitoring_enabled = True
    return {"message": "Alerting resumed"}
