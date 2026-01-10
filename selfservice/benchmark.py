"""
How to Run This Test Suite
1. Start the server: uvicorn filename:app --reload
2. Test Scenario 1: Basic Concurrency
• Send 10 tasks that take 2 seconds each:
• POST /simulate?count=10&duration=2.0
• Observe: You will see 5 tasks start immediately, and 5 tasks wait. As one finishes, a new one starts.
3. Test Scenario 2: Wait Timeout (The "Crash" Test)
• Send 20 tasks that take 15 seconds each:
• POST /simulate?count=20&duration=15.0
• Observe: Since the wait_timeout is 10s, the tasks at the back of the line will start timing out and throwing errors before they ever get a chance to run.
4. Test Scenario 3: Monitoring & Alerting
• Keep the queue full enough to exceed the WAITING_THRESHOLD (10).
• Observe: Look for the 🚨 MONITOR ALERT in your terminal.
5. Test Scenario 4: Security
• Try to hit /admin/status without the X-Admin-Token: test-secret-123 header. It will return a 403 Forbidden.
"""


# ==========================================
# infrastructure.py (Integrated for Testing)
# ==========================================
import asyncio
import logging
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, Request, Depends, HTTPException, status, Security
from fastapi.security.api_key import APIKeyHeader

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Security Config
API_KEY = "test-secret-123"
API_KEY_NAME = "X-Admin-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_admin_key(header_value: str = Security(api_key_header)):
    if header_value == API_KEY: return header_value
    raise HTTPException(status_code=403, detail="Invalid API Key")

# --- Task Manager ---
class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 5, wait_timeout: int = 10):
        self._tasks = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._wait_timeout = wait_timeout
        self._waiting_count = 0
        self._monitoring_enabled = True
        self._alert_sent = False
        self.WAITING_THRESHOLD = 10 # Low threshold for testing

    @property
    def active_tasks(self): return 5 - self._semaphore._value
    @property
    def waiting_tasks(self): return self._waiting_count

    def run(self, func, *args, **kwargs):
        task = asyncio.create_task(self._run_with_semaphore(func, *args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_with_semaphore(self, func, *args, **kwargs):
        self._waiting_count += 1
        try:
            # Test the Wait Timeout logic here
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._wait_timeout)
            self._waiting_count -= 1
            try:
                await func(*args, **kwargs)
            finally:
                self._semaphore.release()
        except asyncio.TimeoutError:
            self._waiting_count -= 1
            logger.error(f"ALERT: Task {func.__name__} timed out waiting for a slot!")
            # In real code, email_service.send_alert() would go here

    async def monitor_queue_health(self):
        """Checks every 2 seconds for test visibility."""
        while True:
            if self._monitoring_enabled:
                if self.waiting_tasks > self.WAITING_THRESHOLD and not self._alert_sent:
                    logger.warning("🚨 MONITOR ALERT: Queue is congested! (Simulation: Email Sent)")
                    self._alert_sent = True
                elif self.waiting_tasks < (self.WAITING_THRESHOLD / 2):
                    self._alert_sent = False
            await asyncio.sleep(2)

task_manager = TaskManager(max_concurrent_tasks=5, wait_timeout=10)

# ==========================================
# simulated_services.py
# ==========================================
async def simulated_io_task(task_id: int, duration: float):
    """Simulates a database or email operation."""
    logger.info(f" -> Task {task_id} starting (will take {duration}s)")
    await asyncio.sleep(duration)
    logger.info(f" <- Task {task_id} completed")

# ==========================================
# main.py (The App)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the monitor
    monitor_task = asyncio.create_task(task_manager.monitor_queue_health())
    logger.info("Test Environment Ready. Semaphore: 5, Wait Timeout: 10s")
    yield
    # Shutdown
    monitor_task.cancel()
    await task_manager.wait_for_completion(timeout=5)

app = FastAPI(lifespan=lifespan)

@app.post("/simulate", tags=["Test"])
async def trigger_test(count: int, duration: float, background_tasks: BackgroundTasks):
    """
    Fire a batch of simulated tasks.
    - count: How many tasks to queue.
    - duration: How long each task takes.
    """
    for i in range(count):
        background_tasks.add_task(task_manager.run, simulated_io_task, i, duration)
    return {"message": f"Queued {count} tasks", "concurrency_limit": 5}

@app.get("/admin/status", dependencies=[Depends(get_admin_key)])
async def get_status():
    return {
        "active_running": task_manager.active_tasks,
        "waiting_in_line": task_manager.waiting_tasks,
        "total_tracked": len(task_manager._tasks),
        "monitoring_on": task_manager._monitoring_enabled
    }

@app.post("/admin/pause", dependencies=[Depends(get_admin_key)])
async def pause():
    task_manager._monitoring_enabled = False
    return {"status": "Monitoring paused"}

@app.post("/admin/resume", dependencies=[Depends(get_admin_key)])
async def resume():
    task_manager._monitoring_enabled = True
    return {"status": "Monitoring resumed"}


# tedt script

import asyncio
import httpx
import time

# Configuration
BASE_URL = "http://127.0.0.1:8000"
ADMIN_KEY = "test-secret-123"
HEADERS = {"X-Admin-Token": ADMIN_KEY}

async def run_test_scenarios():
    async with httpx.AsyncClient(timeout=30) as client:
        print("\n--- 🛡️ SCENARIO 1: Security Check ---")
        # Try accessing status without a key
        bad_res = await client.get(f"{BASE_URL}/admin/status")
        print(f"Unauthorized access check (should be 403): {bad_res.status_code}")
        
        # Try with correct key
        good_res = await client.get(f"{BASE_URL}/admin/status", headers=HEADERS)
        print(f"Authorized access check (should be 200): {good_res.status_code}")

        print("\n--- 🏎️ SCENARIO 2: Concurrency & Semaphore ---")
        # Trigger 15 tasks, each taking 3 seconds. 
        # Since semaphore is 5, it should process in 3 waves.
        print("Firing 15 tasks (3 waves of 5)...")
        await client.post(f"{BASE_URL}/simulate?count=15&duration=3.0")
        
        # Check status immediately to see active vs waiting
        await asyncio.sleep(0.5)
        status = await client.get(f"{BASE_URL}/admin/status", headers=HEADERS)
        data = status.json()
        print(f"Active Tasks (should be 5): {data['active_running']}")
        print(f"Waiting Tasks (should be 10): {data['waiting_in_line']}")

        print("\n--- 🚨 SCENARIO 3: Monitoring & Thresholds ---")
        # Trigger enough tasks to hit the threshold (10 waiting)
        # 5 active + 12 waiting = 17 tasks
        print("Increasing load to trigger Monitor Alert...")
        await client.post(f"{BASE_URL}/simulate?count=17&duration=5.0")
        
        # Give the monitor loop (which runs every 2s) a moment to fire
        await asyncio.sleep(3)
        print("Check your server terminal for '🚨 MONITOR ALERT'!")

        print("\n--- ⏳ SCENARIO 4: Wait Timeout ---")
        # The wait_timeout is 10s. If we send tasks that take 15s, 
        # the ones at the end of the line will time out before starting.
        print("Firing long tasks to force 'Wait Timeout'...")
        await client.post(f"{BASE_URL}/simulate?count=20&duration=15.0")
        
        print("\n--- ⏸️ SCENARIO 5: Pause/Resume ---")
        pause_res = await client.post(f"{BASE_URL}/admin/pause", headers=HEADERS)
        print(f"Pause Monitoring: {pause_res.json()['status']}")
        
        check_status = await client.get(f"{BASE_URL}/admin/status", headers=HEADERS)
        print(f"Is Monitoring On? {check_status.json()['monitoring_on']}")

        print("\nTests complete. Check the server console for final logs.")

if __name__ == "__main__":
    asyncio.run(run_test_scenarios())



"""
What to watch for in the Server Console:
As this script runs, your FastAPI terminal will provide the "truth" of what's happening:
1. Concurrency: You'll see -> Task X starting appear in groups of exactly 5.
2. Order: As one task finishes (<- Task X completed), you will see exactly one new task start. This confirms the Semaphore is working.
3. Alerts: When Scenario 3 runs, the logs should show the 🚨 MONITOR ALERT.
4. Timeouts: When Scenario 4 runs, you will see ERROR: ALERT: Task simulated_io_task timed out waiting for a slot!. This confirms your Wait Timeout is preventing the queue from growing indefinitely.
Comparison: Why this is better than Flask
In a traditional Flask setup, the test_suite.py would likely hang or timeout itself because the server would be busy waiting on the first few time.sleep() calls. With this FastAPI design, the server stays responsive, allows you to check /admin/status even under heavy load, and handles the queue gracefully in the background.
Would you like me to help yo


"""
