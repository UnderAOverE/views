# Pytest and Motor (Asyncio) Example

This project demonstrates how to test asynchronous Python code that uses `motor` (the async driver for MongoDB) with the `pytest` framework.

## The Challenge: Testing Asynchronous Code

Code written with `async`/`await` (coroutines) cannot be tested by standard synchronous test functions. You cannot use `await` inside a regular `def test_...():` function.

## The Solution: `pytest-asyncio` and `motor-mock`

We solve this with two key libraries:

1.  **`pytest-asyncio`**: This is a `pytest` plugin that allows you to write your tests as `async def test_...():`. It automatically runs your async test functions in a proper event loop. You simply mark your tests with `@pytest.mark.asyncio`.

2.  **`motor-mock`**: This is the asynchronous equivalent of `mongomock`. It provides an in-memory mock of a MongoDB server that works with `motor`'s async/await syntax.

## Project Files

*   **`user_database_async.py`**: A new version of our database class, rewritten using `motor` to be fully asynchronous. All database methods are now `async def`.
*   **`test_user_database_async.py`**: The `pytest` test suite.
    *   It uses a `pytest` fixture to create an in-memory `motor-mock` client.
    *   All test functions are defined with `async def` and marked with `@pytest.mark.asyncio`.
    *   All calls to our database methods are properly `await`ed.

## How to Run

1.  **Install dependencies:**
    ```bash
    pip install pytest motor pytest-asyncio motor-mock
    ```

2.  **Run the tests:**
    `pytest` will automatically discover and run the tests. Thanks to `pytest-asyncio`, it will know how to handle the `async` tests correctly.
    ```bash
    pytest
    ```

    For more detailed output, use the verbose flag (`-v`).
    ```bash
    pytest -v
    ```
                                                                                                                      
# user_database_async.py
# This is our application code, rewritten to use motor for async operations.

class UserDatabaseAsync:
    """An ASYNCHRONOUS class to manage users in a MongoDB collection."""

    def __init__(self, motor_client):
        """
        Initializes the UserDatabase with a motor client.
        The dependency injection pattern is the same and remains crucial.
        """
        self.db = motor_client.my_app_db
        self.users = self.db.users

    async def add_user(self, user_id, name, email):
        """ASYNC: Adds a new user to the database."""
        # Check if user already exists
        if await self.users.find_one({"_id": user_id}):
            return None
        
        user_data = {
            "_id": user_id,
            "name": name,
            "email": email
        }
        result = await self.users.insert_one(user_data)
        return result.inserted_id

    async def get_user(self, user_id):
        """ASYNC: Finds a user by their ID."""
        return await self.users.find_one({"_id": user_id})

    async def update_user_email(self, user_id, new_email):
        """ASYNC: Updates the email for a given user."""
        result = await self.users.update_one(
            {"_id": user_id},
            {"$set": {"email": new_email}}
        )
        return result.modified_count > 0

  # test_user_database_async.py
# This file contains the pytest tests for our async UserDatabase class.

import pytest
import motor_mock
from user_database_async import UserDatabaseAsync

# This tells pytest to use the asyncio event loop for tests in this file.
pytestmark = pytest.mark.asyncio


# --- The Pytest Fixture (Async Version) ---
@pytest.fixture
def user_db_async():
    """
    Fixture to set up a clean, in-memory database using motor-mock.
    """
    # 1. Use motor_mock to create a fake async client
    mock_client = motor_mock.AsyncIOMotorClient()
    
    # 2. Inject the mock client into our async class
    db_instance = UserDatabaseAsync(motor_client=mock_client)
    
    # 3. Yield the instance for the test to use
    yield db_instance
    
    # Teardown is handled automatically when the fixture goes out of scope


# --- The Pytest Test Functions (Async Version) ---
# Each test must be defined with 'async def' and calls must use 'await'.

async def test_add_and_get_user(user_db_async):
    """
    Test adding a user and then retrieving them asynchronously.
    """
    # Add a user using the fixture. Note the 'await'.
    user_id = await user_db_async.add_user(1, "Alice", "alice@example.com")
    assert user_id == 1

    # Retrieve the user. Note the 'await'.
    user = await user_db_async.get_user(1)

    # Assertions are still synchronous
    assert user is not None
    assert user['name'] == "Alice"
    assert user['email'] == "alice@example.com"


async def test_get_nonexistent_user(user_db_async):
    """
    Test that getting a user who doesn't exist returns None asynchronously.
    """
    user = await user_db_async.get_user(999)
    assert user is None


async def test_update_user_email(user_db_async):
    """
    Test updating a user's email asynchronously.
    """
    # First, add a user
    await user_db_async.add_user(2, "Bob", "bob@example.com")
    
    # Now, update the email
    updated = await user_db_async.update_user_email(2, "bobby.new@example.com")
    assert updated is True

    # Verify the update by retrieving the user again
    updated_user = await user_db_async.get_user(2)
    assert updated_user['email'] == "bobby.new@example.com"


async def test_add_existing_user(user_db_async):
    """
    Test that adding a user with a pre-existing ID fails gracefully.
    """
    # Add a user with ID 3
    await user_db_async.add_user(3, "Charlie", "charlie@example.com")
    
    # Try to add the same user again
    result = await user_db_async.add_user(3, "Charlie Clone", "clone@example.com")
    
    # Assert that the second add operation failed as expected
    assert result is None
