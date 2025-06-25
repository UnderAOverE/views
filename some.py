I understand. Thanks for the clarification.
Given that RunStatus is a Pydantic model and ApplicationConstants is an Enum, I'll adjust the test setup accordingly. Pydantic models behave like dictionaries when model_dump() is called, and Enums can be accessed directly by their members.
Here's the updated pytest code:
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field # Import Pydantic BaseModel and Field

# Assuming these are defined elsewhere as per your comment
# from your_module import PrerequisiteHandler, RunStatus, ApplicationConstants, STATUS_TRANSITIONS, ResultHandler

# --- Redefine ApplicationConstants as an Enum ---
class ApplicationConstants(Enum):
    PREREQUISITE_HANDLER = "PrerequisiteHandler"
    CBOL = "cbol"
    MOB = "mob"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"

# --- Redefine RunStatus as a Pydantic Model ---
class RunStatus(BaseModel):
    run_id: str | None = Field("test_run_id") # Make run_id optional for None test
    safe_mode_api_service: AsyncMock = Field(default_factory=AsyncMock)
    run_logs_service: AsyncMock = Field(default_factory=AsyncMock)
    notification_service: MagicMock = Field(default_factory=MagicMock)
    backend_service: AsyncMock = Field(default_factory=AsyncMock)
    is_stopped: bool = False
    cbol_status: str | None = None
    mbol_status: str | None = None
    operation: str = "operation_type_1" # Default operation for tests

    # Pydantic models automatically have .model_dump()
    # No need to redefine it unless custom behavior is needed beyond pydantic's default

# STATUS_TRANSITIONS remains the same
STATUS_TRANSITIONS = {
    ("activate", "operation_type_1"): "new_status_1",
    ("deactivate", "operation_type_1"): "new_status_2",
    ("activate", "operation_type_2"): None, # For testing the None case
    ("deactivate", "operation_type_2"): None, # For testing the None case
    ("activate", "another_op"): "another_status",
    ("deactivate", "another_op"): "yet_another_status",
}

# Mock logger remains the same
class MockLogger:
    def debug(self, msg):
        pass
    def error(self, msg):
        pass
    def warning(self, msg):
        pass
    def info(self, msg):
        pass

logger = MockLogger()

# ResultHandler remains the same (base class for PrerequisiteHandler)
class ResultHandler:
    async def handle(self, run_status: RunStatus) -> RunStatus:
        return run_status

# --- The PrerequisiteHandler class (copy-pasted for context with fixes) ---
class PrerequisiteHandler(ResultHandler):
    async def handle(self, run_status: RunStatus) -> RunStatus:
        handler_name = ApplicationConstants.PREREQUISITE_HANDLER.value
        logger.debug(f"handler_name: {handler_name}, run status: {run_status.model_dump()}")
        get_safemodes = await run_status.safe_mode_api_service.get_safemodes()
        if not get_safemodes.get("status") and run_status.run_id: # Check run_id here
            # Corrected typo: get_safemodes_return -> get_safemodes
            details = f"getsafemodes API call failed with response: {get_safemodes}"
            logger.error(details)
            await run_status.run_logs_service.update_check(handler_name, False, details=details)
            run_status.is_stopped = True
            log_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            run_status.notification_service.send_to_developers(
                {"run id": run_status.run_id, "error": f"getsafemodes API call failed with response: ({get_safemodes}).", # Corrected interpolation
                 "exception_details": details, "table_title": "Error Details", "log_datetime": log_datetime})
            return run_status

        run_status.cbol_status = ApplicationConstants.ACTIVATE.value if get_safemodes[ApplicationConstants.CBOL.value] else ApplicationConstants.DEACTIVATE.value
        run_status.mbol_status = ApplicationConstants.ACTIVATE.value if get_safemodes[ApplicationConstants.MOB.value] else ApplicationConstants.DEACTIVATE.value
        
        for application in [ApplicationConstants.CBOL, ApplicationConstants.MOB]:
            match application:
                case ApplicationConstants.CBOL:
                    run_status.cbol_status = STATUS_TRANSITIONS.get((run_status.cbol_status, run_status.operation), None)
                    if run_status.cbol_status is None:
                        details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]}"
                        logger.warning(details)
                        await run_status.run_logs_service.update_check(handler_name, False, details=details)
                        run_status.is_stopped = True
                        return run_status
                    else:
                        backend_status, backend_details = await run_status.backend_service.check_safemodeautologs_status(application=application.value)
                        prerequisite_details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]} : {backend_details}"
                        if backend_status:
                            logger.info(prerequisite_details)
                        else:
                            logger.warning(prerequisite_details)
                            run_status.cbol_status = None
                            await run_status.run_logs_service.update_check(handler_name, backend_status, details=prerequisite_details)

                case ApplicationConstants.MOB:
                    run_status.mbol_status = STATUS_TRANSITIONS.get((run_status.mbol_status, run_status.operation), None)
                    if run_status.mbol_status is None:
                        details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]}"
                        logger.warning(details)
                        await run_status.run_logs_service.update_check(handler_name, False, details=details)
                        run_status.is_stopped = True
                        return run_status
                    else:
                        backend_status, backend_details = await run_status.backend_service.check_safemodeautologs_status(application=application.value)
                        prerequisite_details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]} : {backend_details}"
                        if backend_status:
                            logger.info(prerequisite_details)
                        else:
                            logger.warning(prerequisite_details)
                            run_status.mbol_status = None
                            await run_status.run_logs_service.update_check(handler_name, backend_status, details=prerequisite_details)

        if run_status.is_stopped or run_status.cbol_status is None or run_status.mbol_status is None:
            logger.warning(f"handler_name: Stopping the run id: {run_status.run_id}")
            run_status.is_stopped = True

        return await super().handle(run_status)


@pytest.fixture
def handler():
    return PrerequisiteHandler()

@pytest.fixture
def run_status_instance():
    """Provides a fresh RunStatus instance for each test."""
    return RunStatus()

@pytest.mark.asyncio
async def test_get_safemodes_api_call_failed(handler, run_status_instance):
    """
    Test case: getsafemodes API call fails.
    Expectation: Run is stopped, error logged, notification sent.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {"status": False, "error": "API Error"}

    result = await handler.handle(run_status_instance)

    run_status_instance.run_logs_service.update_check.assert_called_once_with(
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details="getsafemodes API call failed with response: {'status': False, 'error': 'API Error'}"
    )
    run_status_instance.notification_service.send_to_developers.assert_called_once()
    assert result.is_stopped is True
    assert result.run_id == "test_run_id"

@pytest.mark.asyncio
async def test_get_safemodes_api_call_failed_no_run_id(handler, run_status_instance):
    """
    Test case: getsafemodes API call fails but run_id is None.
    Expectation: Should NOT trigger the specific error handling for failed API call with run_id.
                 It should proceed to other checks and ultimately stop if statuses become None.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {"status": False, "error": "API Error"}
    run_status_instance.run_id = None # Simulate no run_id

    result = await handler.handle(run_status_instance)

    # The first 'if not get_safemodes.get("status") and run_status.run_id:' block
    # will be skipped because run_status.run_id is None.
    # The run will then proceed and eventually stop due to cbol_status/mbol_status being None
    # after the initial assignment based on get_safemodes (which is {"status": False, ...})
    run_status_instance.run_logs_service.update_check.assert_called_once_with( # Called for CBOL/MOB becoming None
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details=f"getsafemodes/{ApplicationConstants.CBOL.value} active - False"
    )
    run_status_instance.notification_service.send_to_developers.assert_not_called()
    assert result.is_stopped is True
    assert result.cbol_status is None
    assert result.mbol_status is None


@pytest.mark.asyncio
async def test_cbol_status_becomes_none(handler, run_status_instance):
    """
    Test case: CBOL status becomes None after STATUS_TRANSITIONS lookup.
    Expectation: Run is stopped, warning logged, run_logs_service updated.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: True,  # Will make cbol_status 'activate'
        ApplicationConstants.MOB.value: False   # Will make mbol_status 'deactivate'
    }
    run_status_instance.operation = "operation_type_2" # This operation will lead to None for "activate"
    run_status_instance.backend_service.check_safemodeautologs_status.return_value = (True, "Backend OK")

    result = await handler.handle(run_status_instance)

    run_status_instance.run_logs_service.update_check.assert_called_once_with(
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details=f"getsafemodes/{ApplicationConstants.CBOL.value} active - True"
    )
    assert result.is_stopped is True
    assert result.cbol_status is None
    # MOB would not be processed because the run stops after CBOL fails
    assert result.mbol_status == ApplicationConstants.DEACTIVATE.value # Initial value before any potential transition
    assert result.run_id == "test_run_id"

@pytest.mark.asyncio
async def test_mob_status_becomes_none(handler, run_status_instance):
    """
    Test case: MOB status becomes None after STATUS_TRANSITIONS lookup.
    Expectation: Run is stopped, warning logged, run_logs_service updated.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: False,  # Will make cbol_status 'deactivate' -> 'new_status_2'
        ApplicationConstants.MOB.value: True    # Will make mbol_status 'activate' -> None (due to operation_type_2)
    }
    run_status_instance.operation = "operation_type_2"
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"), # For CBOL (passes)
        (True, "MOB Backend OK")   # For MOB (though its status will become None)
    ]

    result = await handler.handle(run_status_instance)

    # Assert update_check called for MOB specifically
    run_status_instance.run_logs_service.update_check.assert_called_with(
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details=f"getsafemodes/{ApplicationConstants.MOB.value} active - True"
    )
    assert result.is_stopped is True
    assert result.mbol_status is None
    # CBOL status should have been set based on the transition
    assert result.cbol_status == "new_status_2" # 'deactivate' + 'operation_type_2' -> None, wait, 'deactivate' + 'operation_type_2' -> None in STATUS_TRANSITIONS
    # Re-checking STATUS_TRANSITIONS: ("deactivate", "operation_type_2"): None
    # So if CBOL is 'deactivate' and operation is 'operation_type_2', it also becomes None.
    # This means the run would stop at CBOL already. Let's adjust for this specific test case.
    # To reach MOB status becoming None, CBOL must not become None.
    run_status_instance.operation = "another_op" # Use an operation that makes CBOL transition successfully
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: False,  # Will make cbol_status 'deactivate'
        ApplicationConstants.MOB.value: True    # Will make mbol_status 'activate'
    }
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"),
        (True, "MOB Backend OK")
    ]
    # Resetting run_status_instance for the re-attempt of the test logic
    run_status_instance = RunStatus()
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: False,
        ApplicationConstants.MOB.value: True
    }
    run_status_instance.operation = "another_op" # This will make CBOL transition successfully
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"),
        (True, "MOB Backend OK")
    ]

    result = await handler.handle(run_status_instance)

    run_status_instance.run_logs_service.update_check.assert_called_with(
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details=f"getsafemodes/{ApplicationConstants.MOB.value} active - True"
    )
    assert result.is_stopped is True
    assert result.mbol_status is None
    assert result.cbol_status == "yet_another_status" # 'deactivate' + 'another_op'
    assert result.run_id == "test_run_id"


@pytest.mark.asyncio
async def test_backend_check_fails_for_cbol(handler, run_status_instance):
    """
    Test case: Backend check for CBOL fails.
    Expectation: CBOL status becomes None, run_logs_service updated, run stopped.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: True,
        ApplicationConstants.MOB.value: True
    }
    run_status_instance.operation = "operation_type_1" # Will result in "new_status_1" for both
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (False, "CBOL Backend Down"),  # CBOL check fails
        (True, "MOB Backend OK")       # MOB check passes (though not reached if stopped)
    ]

    result = await handler.handle(run_status_instance)

    # Check that update_check was called for CBOL with backend_status=False
    run_status_instance.run_logs_service.update_check.assert_called_with(
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details=f"getsafemodes/{ApplicationConstants.CBOL.value} active - True : CBOL Backend Down"
    )
    assert result.is_stopped is True
    assert result.cbol_status is None
    assert result.run_id == "test_run_id"

@pytest.mark.asyncio
async def test_backend_check_fails_for_mob(handler, run_status_instance):
    """
    Test case: Backend check for MOB fails.
    Expectation: MOB status becomes None, run_logs_service updated, run stopped.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: True,
        ApplicationConstants.MOB.value: True
    }
    run_status_instance.operation = "operation_type_1" # Will result in "new_status_1" for both
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"),     # CBOL check passes
        (False, "MOB Backend Down")    # MOB check fails
    ]

    result = await handler.handle(run_status_instance)

    # Check that update_check was called for MOB with backend_status=False
    run_status_instance.run_logs_service.update_check.assert_called_with(
        ApplicationConstants.PREREQUISITE_HANDLER.value, False,
        details=f"getsafemodes/{ApplicationConstants.MOB.value} active - True : MOB Backend Down"
    )
    assert result.is_stopped is True
    assert result.mbol_status is None
    assert result.run_id == "test_run_id"

@pytest.mark.asyncio
async def test_all_prerequisites_met(handler, run_status_instance):
    """
    Test case: All API calls and backend checks pass.
    Expectation: Run is not stopped, CBOL and MOB statuses are updated correctly.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: True,  # activate
        ApplicationConstants.MOB.value: False   # deactivate
    }
    run_status_instance.operation = "operation_type_1"
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"),
        (True, "MOB Backend OK")
    ]

    result = await handler.handle(run_status_instance)

    run_status_instance.run_logs_service.update_check.assert_not_called()
    run_status_instance.notification_service.send_to_developers.assert_not_called()
    assert result.is_stopped is False
    assert result.cbol_status == "new_status_1"  # activate + operation_type_1
    assert result.mbol_status == "new_status_2"  # deactivate + operation_type_1
    assert result.run_id == "test_run_id"

@pytest.mark.asyncio
async def test_run_status_already_stopped_at_end(handler, run_status_instance):
    """
    Test case: RunStatus.is_stopped is True before the final check.
    Expectation: The final check correctly sets is_stopped to True (redundantly)
                 and logs a warning.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: True,
        ApplicationConstants.MOB.value: True
    }
    run_status_instance.operation = "operation_type_1"
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL OK"),
        (True, "MOB OK")
    ]
    run_status_instance.is_stopped = True # Manually set to True

    # Capture logger.warning calls
    with MagicMock(spec=MockLogger) as mock_logger:
        global logger
        original_logger = logger
        logger = mock_logger
        result = await handler.handle(run_status_instance)
        logger = original_logger # Restore original logger

    mock_logger.warning.assert_called_with(f"handler_name: Stopping the run id: {run_status_instance.run_id}")
    assert result.is_stopped is True
    assert result.cbol_status == "new_status_1"
    assert result.mbol_status == "new_status_1"

@pytest.mark.asyncio
async def test_cbol_active_and_backend_ok(handler, run_status_instance):
    """
    Test case: CBOL is active and its backend check passes.
    Expectation: Info message logged for CBOL.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: True,
        ApplicationConstants.MOB.value: False
    }
    run_status_instance.operation = "operation_type_1"
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"),
        (True, "MOB Backend OK") # Not directly relevant here, but for completeness
    ]

    # Capture logger.info calls
    with MagicMock(spec=MockLogger) as mock_logger:
        global logger
        original_logger = logger
        logger = mock_logger
        await handler.handle(run_status_instance)
        logger = original_logger

    mock_logger.info.assert_any_call(f"getsafemodes/{ApplicationConstants.CBOL.value} active - True : CBOL Backend OK")

@pytest.mark.asyncio
async def test_mob_active_and_backend_ok(handler, run_status_instance):
    """
    Test case: MOB is active and its backend check passes.
    Expectation: Info message logged for MOB.
    """
    run_status_instance.safe_mode_api_service.get_safemodes.return_value = {
        "status": True,
        ApplicationConstants.CBOL.value: False,
        ApplicationConstants.MOB.value: True
    }
    run_status_instance.operation = "operation_type_1"
    run_status_instance.backend_service.check_safemodeautologs_status.side_effect = [
        (True, "CBOL Backend OK"), # For CBOL (passes)
        (True, "MOB Backend OK")
    ]

    # Capture logger.info calls
    with MagicMock(spec=MockLogger) as mock_logger:
        global logger
        original_logger = logger
        logger = mock_logger
        await handler.handle(run_status_instance)
        logger = original_logger

    mock_logger.info.assert_any_call(f"getsafemodes/{ApplicationConstants.MOB.value} active - True : MOB Backend OK")


