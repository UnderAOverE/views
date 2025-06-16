# In test_failover_system.py (or a models file)

import datetime
from typing import List, Optional, Literal, Generic, TypeVar, Any
from pydantic import BaseModel, Field

# --- Pydantic Models for the Audit Log ---

class CheckResult(BaseModel):
    """A Pydantic model for a single entry in the 'checks' list."""
    name: str
    passed: bool
    details: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class ActionResult(BaseModel):
    """A Pydantic model for a single entry in the 'actions' list."""
    application: str
    new_state: str
    details: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class AuditLog(BaseModel):
    """The Pydantic model for the entire audit log document."""
    run_id: str
    user: str = "ai-agent"
    operation_type: Literal["FAILOVER", "ROLLBACK"]
    status: str = "IN_PROGRESS"
    start_time: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    end_time: Optional[datetime.datetime] = None
    
    # Using the sub-models for type safety
    checks: List[CheckResult] = []
    actions: List[ActionResult] = []

    # The summary is a snapshot and can be represented as a generic dict
    summary: Optional[dict] = None

# --- Generic Type Definitions for the Base Repository ---
# This defines a generic type 'T' that must be a subclass of Pydantic's BaseModel
T = TypeVar("T", bound=BaseModel)
