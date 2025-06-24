import pytest
from unittest.mock import MagicMock, AsyncMock

# --- Setup: Define dummy constants to make the tests self-contained ---

# A mock for the ApplicationConstants enum
class MockApplicationConstants:
    class CBOL:
        value = "cbol"
    class MOB:
        value = "mbol"

ApplicationConstants = MockApplicationConstants

# A mock for the STATUS_TRANSITIONS dictionary
# We will manipulate this in each test to control the logic flow.
STATUS_TRANSITIONS = {}

# Assume the code snippet is in a method like `MyHandler.process_applications(...)`
# pytestmark tells pytest all tests in this file are async
pytestmark = pytest.mark.asyncio


# --- Test 1: Covers Path A (Invalid Status Transition) ---

async def test_process_applications_with_invalid_transition():
    """
    Tests the path where the status transition is invalid for both applications.
    This forces the `if status is None:` block to be executed.
    """
    # --- Arrange ---
    mock_run_status = MagicMock()
    mock_run_status.backend_service = MagicMock()
    mock_run_status.run_logs_service = MagicMock()
    mock_run_status.run_logs_service.update_check = AsyncMock()

    # Set initial statuses that will result in a failed lookup
    mock_run_status.cbol_status = "Initial"
    mock_run_status.mbol_status = "Initial"
    mock_run_status.operation = "InvalidOperation"

    # CRITICAL PART: Ensure the STATUS_TRANSITIONS lookup fails by providing an empty dict
    mock_status_transitions = {}
    
    # Dummy data for getsafemodes
    mock_getsafemodes = {"cbol": True, "mbol": False}

    # --- Act ---
    # We pass the mock transitions dictionary to the function
    await MyHandler().process_applications(
        mock_run_status, "handler_name", mock_getsafemodes, mock_status_transitions
    )

    # --- Assert ---
    # 1. Check that update_check was called twice, once for each app in the loop.
    assert mock_run_status.run_logs_service.update_check.await_count == 2
    
    # 2. Verify it was called with False for both, indicating failure.
    #    We check the list of all calls made to the mock.
    calls = mock_run_status.run_logs_service.update_check.await_args_list
    assert calls[0].args[1] is False  # Call for CBOL
    assert calls[1].args[1] is False  # Call for MOB

    # 3. CRUCIALLY, verify the backend was NEVER called because we took the early exit path.
    mock_run_status.backend_service.check_safemodeauditlogs_status.assert_not_awaited()


# --- Test 2: Covers Path B (Valid Transition & Backend Success) ---

async def test_process_applications_with_backend_success():
    """
    Tests the path where the transition is valid and the backend check succeeds.
    This forces the `if backend_status:` block to be executed.
    """
    # --- Arrange ---
    mock_run_status = MagicMock()
    mock_run_status.backend_service = MagicMock()
    mock_run_status.run_logs_service = MagicMock()
    mock_run_status.run_logs_service.update_check = AsyncMock()
    
    # CRITICAL PART 1: Configure the backend service to always return success.
    mock_run_status.backend_service.check_safemodeauditlogs_status = AsyncMock(
        return_value=(True, "Backend status is OK")
    )
    
    # Set initial statuses that will succeed
    mock_run_status.cbol_status = "Initial"
    mock_run_status.mbol_status = "Initial"
    mock_run_status.operation = "ValidOperation"

    # CRITICAL PART 2: Ensure the STATUS_TRANSITIONS lookup succeeds.
    mock_status_transitions = {
        ("Initial", "ValidOperation"): "InProgress"
    }

    mock_getsafemodes = {"cbol": True, "mbol": True}

    # --- Act ---
    await MyHandler().process_applications(
        mock_run_status, "handler_name", mock_getsafemodes, mock_status_transitions
    )

    # --- Assert ---
    # 1. Verify the backend check was called for both applications.
    assert mock_run_status.backend_service.check_safemodeauditlogs_status.await_count == 2

    # 2. Verify the log update was called with True for both.
    assert mock_run_status.run_logs_service.update_check.await_count == 2
    calls = mock_run_status.run_logs_service.update_check.await_args_list
    assert calls[0].args[1] is True  # CBOL succeeded
    assert calls[1].args[1] is True  # MOB succeeded

    # 3. Verify the statuses were updated and NOT set back to None.
    assert mock_run_status.cbol_status == "InProgress"
    assert mock_run_status.mbol_status == "InProgress"


# --- Test 3: Covers Path C (Valid Transition & Backend Failure) ---

async def test_process_applications_with_backend_failure():
    """
    Tests the path where the transition is valid but the backend check fails.
    This forces the `else:` block (after `if backend_status:`) to be executed.
    """
    # --- Arrange ---
    mock_run_status = MagicMock()
    mock_run_status.backend_service = MagicMock()
    mock_run_status.run_logs_service = MagicMock()
    mock_run_status.run_logs_service.update_check = AsyncMock()

    # CRITICAL PART 1: Configure the backend service to return failure.
    mock_run_status.backend_service.check_safemodeauditlogs_status = AsyncMock(
        return_value=(False, "Backend audit log shows failure")
    )

    # Set initial statuses that will succeed
    mock_run_status.cbol_status = "Initial"
    mock_run_status.mbol_status = "Initial"
    mock_run_status.operation = "ValidOperation"

    # CRITICAL PART 2: Ensure the STATUS_TRANSITIONS lookup succeeds.
    mock_status_transitions = {
        ("Initial", "ValidOperation"): "InProgress"
    }

    mock_getsafemodes = {"cbol": False, "mbol": False}

    # --- Act ---
    await MyHandler().process_applications(
        mock_run_status, "handler_name", mock_getsafemodes, mock_status_transitions
    )

    # --- Assert ---
    # 1. Verify the backend check was still called for both applications.
    assert mock_run_status.backend_service.check_safemodeauditlogs_status.await_count == 2

    # 2. Verify the log update was called with False for both.
    assert mock_run_status.run_logs_service.update_check.await_count == 2
    calls = mock_run_status.run_logs_service.update_check.await_args_list
    assert calls[0].args[1] is False
    assert calls[1].args[1] is False

    # 3. CRUCIALLY, verify the statuses were reset to None due to the backend failure.
    assert mock_run_status.cbol_status is None
    assert mock_run_status.mbol_status is None
