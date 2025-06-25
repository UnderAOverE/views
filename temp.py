# In tests/test_app.py

import pytest
from unittest.mock import MagicMock
from src.app import update_user, delete_user


# --- Combined Test for update_user ---

@pytest.mark.parametrize(
    # 1. Define the parameter names used in the test function.
    "user_id, data_to_update, mock_modified_count, expected_result",
    [
        # 2. Define the test cases as a list of tuples.
        #    Each tuple represents one full run of the test.
        # Scenario: User exists and is successfully updated
        ("existing_user_123", {"status": "updated"}, 1, True),
        
        # Scenario: User does not exist, so nothing is modified
        ("non_existent_user_456", {"status": "updated"}, 0, False),
    ],
    # 3. (Optional but highly recommended) Provide readable IDs for each test case.
    ids=["user_exists_success", "user_does_not_exist_failure"]
)
def test_update_user(mocker, user_id, data_to_update, mock_modified_count, expected_result):
    """
    Tests update_user for both success and failure scenarios using parametrization.
    """
    # --- Arrange ---
    # The setup is now dynamic, using the parameters from the decorator.
    mock_collection = MagicMock()
    
    # Configure the mock's return value based on the current test case.
    mock_collection.update_one.return_value = MagicMock(modified_count=mock_modified_count)
    
    mocker.patch("src.app.client.get_logins_collection", return_value=mock_collection)

    # --- Act ---
    was_updated = update_user(user_id, data_to_update)

    # --- Assert ---
    # The expected result is now a parameter.
    assert was_updated is expected_result
    
    # The arguments for the mock call are also parameters.
    mock_collection.update_one.assert_called_once_with(
        {"_id": user_id},
        {"$set": data_to_update}
    )


# --- Combined Test for delete_user ---

@pytest.mark.parametrize(
    "user_id, mock_deleted_count, expected_result",
    [
        # Scenario: User exists and is successfully deleted
        ("user_to_delete", 1, True),
        
        # Scenario: User does not exist, so nothing is deleted
        ("user_not_found", 0, False),
    ],
    ids=["user_exists", "user_does_not_exist"]
)
def test_delete_user(mocker, user_id, mock_deleted_count, expected_result):
    """
    Tests delete_user for both success and failure scenarios using parametrization.
    """
    # --- Arrange ---
    mock_collection = MagicMock()
    
    # Configure the mock's return value based on the current test case.
    mock_collection.delete_one.return_value = MagicMock(deleted_count=mock_deleted_count)
    
    mocker.patch("src.app.client.get_logins_collection", return_value=mock_collection)

    # --- Act ---
    was_deleted = delete_user(user_id)

    # --- Assert ---
    assert was_deleted is expected_result
    
    mock_collection.delete_one.assert_called_once_with({"_id": user_id})
