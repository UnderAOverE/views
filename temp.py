# test_user_database_pytest.py
# This file contains the pytest tests for our UserDatabase class.

import pytest
import mongomock
from user_database import UserDatabase

# --- The Pytest Fixture ---
# This fixture replaces the need for setUp and tearDown methods.
# The @pytest.fixture decorator tells pytest that this is a setup function.
# The name of the function ('user_db') is what tests will use to request it.
@pytest.fixture
def user_db():
    """
    Fixture to set up a clean, in-memory database for each test.
    It yields an instance of our UserDatabase class initialized with a
    mock client.
    """
    print("\n--- Setting up a mock database fixture ---")
    mock_client = mongomock.MongoClient()
    db_instance = UserDatabase(mongo_client=mock_client)
    
    # 'yield' is like 'return', but it allows code to run after the test.
    # The test function will run at this 'yield' point.
    yield db_instance
    
    # --- Teardown Code ---
    # This code runs *after* the test function that used the fixture is complete.
    print("\n--- Tearing down the mock database ---")
    mock_client.drop_database('my_app_db')


# --- The Pytest Test Functions ---
# Notice there is no class and no 'self'.
# The test functions simply accept the fixture 'user_db' as an argument.

def test_add_and_get_user(user_db):
    """
    Test adding a user and then retrieving them.
    The 'user_db' argument tells pytest to run the user_db fixture
    and pass its result here.
    """
    # Add a user using the fixture
    user_id = user_db.add_user(1, "Alice", "alice@example.com")
    # Pytest uses the standard 'assert' statement
    assert user_id == 1

    # Retrieve the user
    user = user_db.get_user(1)

    # Assertions are simple and readable
    assert user is not None
    assert user['name'] == "Alice"
    assert user['email'] == "alice@example.com"


def test_get_nonexistent_user(user_db):
    """
    Test that getting a user who doesn't exist returns None.
    This test gets its own, completely separate, fresh database from the fixture.
    """
    user = user_db.get_user(999) # This user ID does not exist
    assert user is None


def test_update_user_email(user_db):
    """
    Test updating a user's email.
    """
    # First, add a user to have something to update
    user_db.add_user(2, "Bob", "bob@example.com")
    
    # Now, update the email
    updated = user_db.update_user_email(2, "bobby.new@example.com")
    assert updated is True

    # Verify the update by retrieving the user again
    updated_user = user_db.get_user(2)
    assert updated_user['email'] == "bobby.new@example.com"


def test_add_existing_user(user_db):
    """
    Test that adding a user with a pre-existing ID fails gracefully.
    """
    # Add a user with ID 3
    user_db.add_user(3, "Charlie", "charlie@example.com")
    
    # Try to add the same user again
    result = user_db.add_user(3, "Charlie Clone", "clone@example.com")
    
    # Assert that the second add operation failed as expected
    assert result is None


# user_database.py
# This is our application code that we want to test.
# This file does NOT need to change when switching testing frameworks.
# The Dependency Injection pattern makes it testable with anything.

class UserDatabase:
    """A class to manage users in a MongoDB collection."""

    def __init__(self, mongo_client):
        """
        Initializes the UserDatabase with a MongoDB client.
        """
        self.db = mongo_client.my_app_db
        self.users = self.db.users

    def add_user(self, user_id, name, email):
        """Adds a new user to the database."""
        # Check if user already exists
        if self.users.find_one({"_id": user_id}):
            return None # Or raise an error, depending on desired behavior
        
        user_data = {
            "_id": user_id,
            "name": name,
            "email": email
        }
        result = self.users.insert_one(user_data)
        return result.inserted_id

    def get_user(self, user_id):
        """Finds a user by their ID."""
        return self.users.find_one({"_id": user_id})

    def update_user_email(self, user_id, new_email):
        """Updates the email for a given user."""
        result = self.users.update_one(
            {"_id": user_id},
            {"$set": {"email": new_email}}
        )
        return result.modified_count > 0

# Pytest and PyMongo Example

This project demonstrates how to test Python code that interacts with MongoDB using the `pytest` framework. It showcases the power and simplicity of `pytest` fixtures for managing resources like database connections.

## The `pytest` Approach: Fixtures

Instead of using `unittest`'s `setUp` and `tearDown` methods, `pytest` uses **fixtures**.

A fixture is a function that sets up a specific environment or resource (like our mock database) and provides it to the tests that need it. This has several advantages:

1.  **Explicit:** A test explicitly declares which fixtures it needs by name in its function signature. This makes the test's dependencies clear.
2.  **Modular & Reusable:** Fixtures can be defined once and used by any number of tests.
3.  **Scalable:** Fixtures have different "scopes," allowing you to create a resource once per test, per class, per module, or even for the entire test session, which is highly efficient.

In this example, we create a `user_db` fixture that creates a new, empty, in-memory database for every single test that requests it, ensuring perfect test isolation.

## Project Files

*   **`user_database.py`**: The same application code as before. Its design, using Dependency Injection, allows it to work with any testing framework.
*   **`test_user_database_pytest.py`**: The test suite written for `pytest`. Notice there is no test class. We use plain functions and a `@pytest.fixture`.

## How to Run

1.  **Install dependencies:**
    You will need `pytest`, `pymongo`, and `mongomock`.
    ```bash
    pip install pytest pymongo mongomock
    ```

2.  **Run the tests:**
    Navigate to your project directory in the terminal and simply run `pytest`. It will automatically discover and run files named `test_*.py`.
    ```bash
    pytest
    ```

    For more detailed output, use the verbose flag (`-v`).
    ```bash
    pytest -v
    ```
