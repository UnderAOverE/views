import sys
sys.dont_write_bytecode = True
from enum import StrEnum
import os

__author__ = "author"
module_version: str = "1.0.0"

CONTENT_TYPE: str = "application/json"
DEVELOPER_ATTENTION_EMAIL_SUBJECT: str = "ATTENTION: Notification Service: Error Occurred"

HOME_DIRECTORIES: dict[str, str] = {
    "app": "/opt/application",       # this is inside servers.
    "ose": "/pythonapps",            # this inside OpenShift environments.
    "workspace": "/projects",        # this is inside the dev-spaces (Orion).
}

HOME_DIRECTORY: str = HOME_DIRECTORIES.get(
    os.environ.get("SOURCE_PLATFORM", "app"), "/opt/application"
)

class Constants(StrEnum):
    cancelled = "cancelled"
    completed = "completed"
    disabled = "disabled"
    enabled = "enabled"
    failed = "failed"
    incorrect = "incorrect"
    in_progress = "in_progress"
    not_applicable = "not_applicable"
    not_found = "not_found"
    not_required = "not_required"
    pending = "pending"
    stopped = "stopped"
    success = "success"
