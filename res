import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- 1. CONFIGURATION & GLOBALS ---
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "audit_service_db"

# This dictionary acts as our local "Cache" for limits stored in Mongo.
# We initialize it with hardcoded defaults in case Mongo is unreachable.
DYNAMIC_LIMITS = {
    "audit_api": "5/minute",
    "default": "100/hour"
}

# --- 2. LIMITER SETUP ---
# storage_uri: Where slowapi stores the "hits" (the counters).
# This uses the synchronous pymongo driver internally.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"{MONGO_URI}/{DB_NAME}?authSource=admin"
)

# This function is passed to the decorator. It is called on every request.
# Because it reads from a local dict, it is extremely fast (nanoseconds).
def get_current_audit_limit(request: Request) -> str:
    return DYNAMIC_LIMITS.get("audit_api", "5/minute")

# --- 3. BACKGROUND SYNC TASK ---
async def sync_limits_from_db(app: FastAPI):
    """
    Periodically pulls the rate limit configuration from MongoDB 
    and updates the local DYNAMIC_LIMITS dictionary.
    """
    while True:
        try:
            db = app.state.db
            # We look for a document that stores our app settings
            config = await db["settings"].find_one({"key": "rate_limit_config"})
            
            if config:
                DYNAMIC_LIMITS["audit_api"] = config.get("audit_api", "5/minute")
                DYNAMIC_LIMITS["default"] = config.get("default", "100/hour")
                # print(f"Synced limits from Mongo: {DYNAMIC_LIMITS}")
        except Exception as e:
            print(f"Error syncing limits from MongoDB: {e}")
        
        # Check for updates every 60 seconds
        await asyncio.sleep(60)

# --- 4. LIFESPAN MANAGEMENT ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Initialize Async Mongo Client (Motor)
    app.state.mongo_client = AsyncIOMotorClient(MONGO_URI)
    app.state.db = app.state.mongo_client[DB_NAME]
    
    # Start the background configuration sync task
    sync_task = asyncio.create_task(sync_limits_from_db(app))
    
    print("API Started: Mongo Connected & Limit Sync Task running.")
    yield
    
    # SHUTDOWN: Clean up
    sync_task.cancel()
    app.state.mongo_client.close()
    print("API Stopped: Connections closed.")

# --- 5. APP INITIALIZATION ---
app = FastAPI(lifespan=lifespan)

# Attach the limiter to the app state
app.state.limiter = limiter

# Correct Exception Handler: Handle RateLimitExceeded errors
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 6. ROUTES ---

@app.get("/api/v1/audit")
@limiter.limit(get_current_audit_limit)  # Uses the dynamic function
async def get_audit_logs(request: Request):
    """
    This route is rate-limited based on the string stored in MongoDB.
    If you change the 'audit_api' field in the 'settings' collection,
    this route will update its limit automatically within 60 seconds.
    """
    return {
        "status": "success",
        "applied_limit": DYNAMIC_LIMITS["audit_api"]
    }

@app.get("/api/v1/status")
async def get_status():
    """This route is NOT rate limited."""
    return {"status": "online"}
