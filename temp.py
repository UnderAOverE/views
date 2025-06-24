# test_user_database.py
# This file contains the unit tests for our UserDatabase class.

import unittest
import mongomock  # The star of the show!
from user_database import UserDatabase

class TestUserDatabase(unittest.TestCase):
    """Test cases for the UserDatabase class."""

    def setUp(self):
        """
        Set up a fresh, in-memory database for each test.
        This method runs before each test function.
        """
        # 1. Create a mock MongoDB client using mongomock.
        self.mock_client = mongomock.MongoClient()

        # 2. "Inject" this mock client into the class we are testing.
        # Our UserDatabase class will think it's talking to a real MongoDB
        # server, but it's actually talking to our in-memory mock.
        self.db = UserDatabase(mongo_client=self.mock_client)
        print("\n--- setUp: Created a fresh in-memory database ---")


    def tearDown(self):
        """
        Clean up after each test.
        """
        # 3. Explicitly drop the database to ensure a clean state,
        # although with a new mongomock client per test, this is just for good measure.
        self.mock_client.drop_database('my_app_db')
        print("--- tearDown: Dropped the in-memory database ---")


    def test_add_and_get_user(self):
        """
        Test adding a user and then retrieving them to verify correctness.
        """
        print("Executing: test_add_and_get_user")
        
        # Add a user
        user_id = self.db.add_user(1, "Alice", "alice@example.com")
        self.assertEqual(user_id, 1)

        # Retrieve the user
        user = self.db.get_user(1)

        # Assert that the retrieved user is not None and has the correct data
        self.assertIsNotNone(user)
        self.assertEqual(user['name'], "Alice")
        self.assertEqual(user['email'], "alice@example.com")


    def test_get_nonexistent_user(self):
        """
        Test that getting a user who doesn't exist returns None.
        """
        print("Executing: test_get_nonexistent_user")
        user = self.db.get_user(999) # This user ID does not exist
        self.assertIsNone(user)


    def test_update_user_email(self):
        """
        Test updating a user's email.
        """
        print("Executing: test_update_user_email")

        # First, add a user to have something to update
        self.db.add_user(2, "Bob", "bob@example.com")
        
        # Now, update the email
        updated = self.db.update_user_email(2, "bobby.new@example.com")
        self.assertTrue(updated)

        # Verify the update by retrieving the user again
        updated_user = self.db.get_user(2)
        self.assertEqual(updated_user['email'], "bobby.new@example.com")


    def test_add_existing_user(self):
        """
        Test that adding a user with a pre-existing ID fails gracefully.
        Our current implementation should return None.
        """
        print("Executing: test_add_existing_user")
        # Add a user with ID 3
        self.db.add_user(3, "Charlie", "charlie@example.com")
        
        # Try to add the same user again
        result = self.db.add_user(3, "Charlie Clone", "clone@example.com")
        
        # Assert that the second add operation failed as expected
        self.assertIsNone(result)

# This allows the test to be run from the command line
if __name__ == '__main__':
    unittest.main(verbosity=2)

# user_database.py
# This is our application code that we want to test.
# It interacts with a MongoDB database.

class UserDatabase:
    """A class to manage users in a MongoDB collection."""

    def __init__(self, mongo_client):
        """
        Initializes the UserDatabase with a MongoDB client.

        This is an example of 'Dependency Injection'. We don't create the
        client inside this class; we pass it in. This allows us to pass
        a real client in production and a mock client during tests.
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


# Python Unittest Examples with PyMongo

This project demonstrates how to effectively test Python code that interacts with a MongoDB database using `pymongo`.

## The Challenge of Testing Database Code

When testing code that talks to a database, we want to avoid:
1.  **Dependency:** Requiring a real MongoDB server to be running just to run tests.
2.  **Slowness:** Network and disk I/O to a real database makes tests slow.
3.  **State Pollution:** Tests should be independent. If one test adds data to the database, it shouldn't affect the next test.

## The Solution: Mocking with `mongomock`

We solve these problems by using the `mongomock` library.

*   `mongomock` creates an **in-memory simulation** of a MongoDB database.
*   It has the same interface as `pymongo`, so our application code doesn't need to change.
*   It's extremely fast and requires no installation of MongoDB.
*   Each test can get its own fresh, empty, and isolated database, ensuring tests don't interfere with each other.

## Project Files

*   **`user_database.py`**: A simple class that manages a `users` collection in a database. It's written to accept a `pymongo` client, a pattern known as **Dependency Injection**, which is crucial for testability.
*   **`test_user_database.py`**: The unit test suite. In the `setUp` method, instead of creating a real `pymongo.MongoClient`, we create a `mongomock.MongoClient` and pass it to our `UserDatabase` class.

## How to Run

1.  **Install dependencies:**
    ```bash
    pip install pymongo mongomock
    ```

2.  **Run the tests:**
    You can run the tests using Python's built-in `unittest` runner.
    ```bash
    python -m unittest test_user_database.py
    ```

    Or by running the file directly:
    ```bash
    python test_user_database.py
    ```
