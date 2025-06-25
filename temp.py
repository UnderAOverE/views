#
# A clean, single-file example for handling MongoDB ObjectIds in Pydantic V2.
#

from bson import ObjectId
from pydantic import BaseModel, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from typing import Any, Annotated

# --- Step 1: Define the Custom Type for ObjectId ---

# This class encapsulates the logic for Pydantic. It tells Pydantic how to:
# 1. Validate: Convert incoming strings or ObjectIds into a valid ObjectId instance.
# 2. Serialize: Convert an outgoing ObjectId instance into a plain string for JSON.
class _PyObjectId:
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """
        Defines the validation and serialization behavior for our type.
        """
        # This is a validation function that Pydantic will use.
        def validate_from_str(v: str) -> ObjectId:
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)

        # The core schema defines how to handle different input types.
        return core_schema.json_or_python_schema(
            # For JSON input, we expect a string and validate it.
            json_schema=core_schema.chain_schema(
                [
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(validate_from_str),
                ]
            ),
            # For Python input, we accept an existing ObjectId instance or a string.
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [
                            core_schema.str_schema(),
                            core_schema.no_info_plain_validator_function(validate_from_str),
                        ]
                    ),
                ]
            ),
            # This defines how the ObjectId is serialized (converted to a string).
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: str(instance)
            ),
        )

# --- Step 2: Create the Reusable Annotated Type ---

# PyObjectId is now a reusable type that you can import and use in any Pydantic model.
PyObjectId = Annotated[ObjectId, _PyObjectId]


# --- Step 3: Use the Custom Type in an Example Pydantic Model ---

class User(BaseModel):
    """An example model representing a user from a MongoDB collection."""

    # We use our custom PyObjectId type for the 'id' field.
    # The Field(...) function is used to specify an alias, so that this field
    # maps to MongoDB's '_id' document key.
    id: PyObjectId = Field(alias="_id")
    username: str
    email: str

    class Config:
        # This allows Pydantic to create a model instance using the '_id' alias.
        populate_by_name = True


# --- Step 4: Demonstration of How It Works ---

if __name__ == "__main__":

    # --- SERIALIZATION DEMO (Python Object -> JSON String) ---
    print("--- 1. Serialization Demo ---")
    
    # Create a User instance with a real BSON ObjectId.
    user_in_python = User(
        id=ObjectId("653a9e6a32d4e68e42f954a6"),
        username="john_doe",
        email="john.doe@example.com",
    )
    print(f"Original Python object: {user_in_python}")
    print(f"Type of .id attribute: {type(user_in_python.id)}")
    
    # Serialize the model to a JSON string.
    # `by_alias=True` ensures the output key is `_id` instead of `id`.
    json_output = user_in_python.model_dump_json(by_alias=True, indent=2)
    
    print("\nSerialized JSON output:")
    print(json_output)
    # The ObjectId is now a clean string in the JSON output.
    # Expected output:
    # {
    #   "_id": "653a9e6a32d4e68e42f954a6",
    #   "username": "john_doe",
    #   "email": "john.doe@example.com"
    # }

    print("-" * 30)

    # --- VALIDATION DEMO (Dictionary -> Python Object) ---
    print("\n--- 2. Validation Demo ---")

    # Simulate incoming data from an API request body (as a dictionary).
    # The '_id' field is a string, just like it would be in a JSON payload.
    incoming_data_from_api = {
        "_id": "653b8f2c8f8b4a7b9f8b4a7b",
        "username": "jane_doe",
        "email": "jane.doe@example.com",
    }
    print(f"Incoming data (dict): {incoming_data_from_api}")

    # Create a Pydantic model instance from the dictionary.
    # Pydantic will use our custom validation logic to convert the string `_id`
    # back into a proper ObjectId instance.
    user_from_data = User.model_validate(incoming_data_from_api)

    print(f"\nValidated Python object: {user_from_data}")
    print(f"Type of .id attribute after validation: {type(user_from_data.id)}")
    # The .id attribute is now a real BSON ObjectId, ready to be used with a database.
