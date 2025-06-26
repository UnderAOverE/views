import pytest
from unittest.mock import AsyncMock, MagicMock

# Import the function we want to test
from main import run_operations

# --- Test for the Success Scenario ---

@pytest.mark.asyncio
async def test_run_operations_success(mocker):
    """
    Tests the successful execution path of run_operations.
    """
    # 1. Mock all external dependencies to isolate our function
    mock_failover_manager = mocker.patch("main.FailoverManager", autospec=True)
    mock_rollback_manager = mocker.patch("main.RollbackManager", autospec=True)
    mock_notification_service = mocker.patch("main.NotificationService", autospec=True)
    mock_sys_exit = mocker.patch("main.sys.exit")
    mocker.patch("main.logger") # Mock the logger to prevent real logs

    # Mock the async methods on the *instances* of the managers
    mock_failover_instance = mock_failover_manager.return_value
    mock_failover_instance.execute_failover_operation = AsyncMock()
    
    mock_rollback_instance = mock_rollback_manager.return_value
    mock_rollback_instance.execute_failover_operation = AsyncMock()

    # 2. Run the function with test data
    test_switch = "TestSwitch"
    test_env = "test-env"
    await run_operations(switchname=test_switch, ose_environment=test_env)

    # 3. Assert that our mocks were called as expected
    # Check that managers were instantiated correctly
    mock_failover_manager.assert_called_once_with(switchname=test_switch, ose_environment=test_env)
    mock_rollback_manager.assert_called_once_with(switchname=test_switch, ose_environment=test_env)

    # Check that the async operations were awaited
    mock_failover_instance.execute_failover_operation.assert_awaited_once()
    mock_rollback_instance.execute_failover_operation.assert_awaited_once()

    # Check that NO notifications were sent and the script did NOT exit
    mock_notification_service.return_value.send_email_to_developers.assert_not_called()
    mock_sys_exit.assert_not_called()


# --- Test for the Failure Scenario ---

@pytest.mark.asyncio
async def test_run_operations_failure_during_failover(mocker):
    """
    Tests the failure path where the FailoverManager raises an exception.
    """
    # 1. Mock dependencies again for this isolated test
    mock_failover_manager = mocker.patch("main.FailoverManager", autospec=True)
    mocker.patch("main.RollbackManager", autospec=True) # Still need to mock it
    mock_notification_service = mocker.patch("main.NotificationService", autospec=True)
    mock_sys_exit = mocker.patch("main.sys.exit")
    mocker.patch("main.logger")

    # This time, configure the mock to raise an error when awaited
    error = RuntimeError("Connection to switch failed!")
    mock_failover_instance = mock_failover_manager.return_value
    mock_failover_instance.execute_failover_operation = AsyncMock(side_effect=error)

    mock_notification_instance = mock_notification_service.return_value

    # 2. Run the function
    test_switch = "FailedSwitch"
    test_env = "prod"
    await run_operations(switchname=test_switch, ose_environment=test_env)

    # 3. Assert the failure behavior
    # Check that the failing method was at least awaited
    mock_failover_instance.execute_failover_operation.assert_awaited_once()

    # Check that the notification service was called with the correct error
    mock_notification_instance.send_email_to_developers.assert_called_once()
    # You can get more specific and check the contents of the call
    call_args, call_kwargs = mock_notification_instance.send_email_to_developers.call_args
    assert call_kwargs['table_details']['error'] == repr(error)
    assert call_kwargs['table_details']['switchname'] == test_switch

    # Crucially, check that the script tried to exit with an error code
    mock_sys_exit.assert_called_once_with(1)


import sys
# It's better to control this via runner command (e.g., python -B) if possible
# But leaving it here is fine.
sys.dont_write_bytecode = True

import asyncio
from datetime import datetime, timezone
import os

# Assuming these are correct import paths
from common.logger import logger
from application.handlers.failover_manager import FailoverManager
from application.handlers.rollback_manager import RollbackManager
from application.services.notification_service import NotificationService

module_version: str = "1.0.0v"

# This is our main, testable logic function
async def run_operations(switchname: str, ose_environment: str):
    """
    Contains all the core logic for failover, rollback, and error handling.
    This function can be imported and tested.
    """
    log_datetime = datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")
    logger_extras = {
        "switchname": switchname,
        "module_name": "__main__",
        "ose_environment": ose_environment,
        "version": module_version, # Corrected typo from "verion"
    }

    # Instantiate services inside the function so we can mock them in tests
    notification_service = NotificationService()
    failover_manager = FailoverManager(switchname=switchname, ose_environment=ose_environment)
    rollback_manager = RollbackManager(switchname=switchname, ose_environment=ose_environment)

    try:
        logger.debug("Starting failover and rollback operations", extra=logger_extras)
        
        logger.info("Starting failover...", extra=logger_extras)
        await failover_manager.execute_failover_operation()
        logger.info("Failover completed.", extra=logger_extras)

        logger.info("Starting rollback...", extra=logger_extras)
        # Assuming the method name is the same for rollback, adjust if not
        await rollback_manager.execute_failover_operation()
        logger.info("Rollback completed.", extra=logger_extras)

    except Exception as generic_exception:
        error_message = f"An error occurred: {repr(generic_exception)}"
        logger.error(error_message, extra=logger_extras)
        
        exception_details = {
            "switchname": switchname,
            "module_name": "__main__",
            "ose_environment": ose_environment,
            "version": module_version,
            "error": repr(generic_exception),
        }
        
        # We need to test that this gets called on failure
        notification_service.send_email_to_developers(
            table_details=exception_details, 
            table_title=f"Error details {log_datetime}"
        )
        # We need to test that the script exits on failure
        sys.exit(1)


# The "Execution Harness" - this part is not meant to be covered by tests.
if __name__ == "__main__":
    # 1. Get inputs from the outside world
    cli_switchname = sys.argv[1] if len(sys.argv) > 1 else "Outage"
    env_ose = os.environ.get("OSE_ENVIRONMENT", "dev1")
    
    # 2. Call the main logic function
    asyncio.run(run_operations(switchname=cli_switchname, ose_environment=env_ose))
