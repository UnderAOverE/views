# test_my_app.py
from my_app import process_user_data

def test_process_user_data_with_patch(mocker):
    """
    Tests the logic of process_user_data without calling the slow API.
    """
    # --- Arrange ---
    # 1. Use mocker.patch to find and replace the slow function.
    #    The target string 'my_app.get_data_from_slow_api' tells patch:
    #    "Go into the 'my_app' module and replace the 'get_data_from_slow_api' object."
    mocked_api_call = mocker.patch(
        'my_app.get_data_from_slow_api', 
        return_value="Mocked data for user123"  # Tell our mock what to return
    )
    
    print("\nPatch is active. The real function will NOT be called.")

    # --- Act ---
    # 2. Call the function we are testing. When it tries to call 
    #    get_data_from_slow_api, it will hit our mock instead.
    result = process_user_data("user123")

    # --- Assert ---
    # 3. Check that the logic of our main function worked correctly with the FAKE data.
    assert result == "Processed: MOCKED DATA FOR USER123"

    # 4. (Crucial) Check that our mock (the stunt double) was actually used as expected.
    #    This proves the connection was made correctly.
    mocked_api_call.assert_called_once_with("user123")


# my_app.py
import time
import requests

def get_data_from_slow_api(user_id):
    """
    This is the function we want to AVOID calling in our test.
    It simulates a slow network request.
    """
    print("\nMaking a REAL, SLOW network call...")
    time.sleep(2) # Simulate slowness
    # response = requests.get(f"https://api.example.com/data/{user_id}")
    return f"Real data for {user_id}"

def process_user_data(user_id):
    """
    This is the function we WANT to test.
    Its logic depends on the result of the slow function.
    """
    print("\nProcessing user data...")
    # This is where 'get_data_from_slow_api' is LOOKED UP and used.
    data = get_data_from_slow_api(user_id)
    
    if "Real data" in data:
        return f"Processed: {data.upper()}"
    else:
        return "Processing failed: No data"
