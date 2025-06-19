
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from typing import List, Dict, Any, Optional
from datetime import datetime # For potential testing with datetime objects

# Assume you have your MongoDB collection instance
# client = AsyncIOMotorClient("mongodb://localhost:27017")
# db = client.mydatabase
# my_collection = db.mycollection

async def get_latest_safehouse_failover_actions(
    collection: AsyncIOMotorCollection
) -> Optional[List[Dict[str, str]]]:
    """
    Retrieves a list of {application, handler} dicts from the 'actions' array
    of the latest document matching name="Safehouse" and operation_type="failover".

    Returns the list of dicts, or None if no matching document is found
    or if the 'actions' array is missing/empty in the latest document.
    """
    pipeline = [
        {
            "$match": {
                "name": "Safehouse",
                "operation_type": "failover",
                "actions": {"$exists": True} # Ensure 'actions' field exists
                # You might also want to check if 'actions' is not empty,
                # though $project will handle empty lists gracefully.
                # If you only want docs with non-empty actions, add:
                # "actions.0": {"$exists": True}
                # or
                # "actions": {"$ne": []} (more direct for non-empty)
            }
        },
        {
            "$sort": {
                "start_datetime": -1  # -1 for descending order (latest first)
            }
        },
        {
            "$limit": 1  # Get only the single latest document
        },
        {
            "$project": {
                "_id": 0,  # Exclude the _id field
                "processed_actions": {
                    "$map": {
                        "input": "$actions",  # Iterate over the 'actions' array
                        "as": "action_item",  # Variable for each element in 'actions'
                        "in": {
                            "application": "$$action_item.application",
                            "handler": "$$action_item.handler"
                            # ticket and timestamp are excluded as per your requirement
                        }
                    }
                }
            }
        }
    ]

    result_cursor = collection.aggregate(pipeline)
    latest_document_actions = await result_cursor.to_list(length=1) # Expecting at most one document

    if latest_document_actions and "processed_actions" in latest_document_actions[0]:
        # The result from $project will be a list containing one document like:
        # [{"processed_actions": [{"application": "app1", "handler": "h1"}, ...]}]
        return latest_document_actions[0]["processed_actions"]
    else:
        return None # No matching document found or actions field was not processed

# --- Example Usage (requires a running MongoDB instance and Motor) ---
async def example_usage():
    # Replace with your actual MongoDB connection string and database/collection names
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_db"]
    collection = db["operations_log"]

    # Clear existing data and insert some sample documents for testing
    await collection.delete_many({})
    await collection.insert_many([
        { # Document 1 - Matches, older
            "name": "Safehouse", "operation_type": "failover", "start_datetime": datetime(2023, 1, 1, 10, 0, 0),
            "actions": [
                {"application": "AppA", "handler": "Handler1", "ticket": "T1", "timestamp": datetime.utcnow()},
                {"application": "AppB", "handler": "Handler2", "ticket": "T2", "timestamp": datetime.utcnow()}
            ],
            "checks": []
        },
        { # Document 2 - Matches, LATEST, actions present
            "name": "Safehouse", "operation_type": "failover", "start_datetime": datetime(2023, 1, 1, 12, 0, 0),
            "actions": [
                {"application": "AppX", "handler": "HandlerX", "ticket": "TX", "timestamp": datetime.utcnow()},
                {"application": "AppY", "handler": "HandlerY", "ticket": "TY", "timestamp": datetime.utcnow()}
            ],
            "checks": ["check1"]
        },
        { # Document 3 - Matches, but older than Doc 2
            "name": "Safehouse", "operation_type": "failover", "start_datetime": datetime(2023, 1, 1, 11, 0, 0),
            "actions": [
                {"application": "AppC", "handler": "Handler3", "ticket": "T3", "timestamp": datetime.utcnow()}
            ],
            "checks": []
        },
        { # Document 4 - Name doesn't match
            "name": "OtherApp", "operation_type": "failover", "start_datetime": datetime(2023, 1, 1, 13, 0, 0),
            "actions": [{"application": "AppD", "handler": "Handler4"}], "checks": []
        },
        { # Document 5 - Operation type doesn't match
            "name": "Safehouse", "operation_type": "rollback", "start_datetime": datetime(2023, 1, 1, 14, 0, 0),
            "actions": [{"application": "AppE", "handler": "Handler5"}], "checks": []
        },
        { # Document 6 - Matches criteria, but actions is empty
            "name": "Safehouse", "operation_type": "failover", "start_datetime": datetime(2023, 1, 1, 15, 0, 0),
            "actions": [], # Empty actions
            "checks": []
        },
         { # Document 7 - Matches criteria, LATEST, but actions field missing
            "name": "Safehouse", "operation_type": "failover", "start_datetime": datetime(2023, 1, 1, 16, 0, 0),
            # "actions": [], # Actions field is missing
            "checks": []
        }
    ])

    print("--- Test Case 1: Expecting actions from Document 2 (then Doc 6, then Doc 7 based on time) ---")
    # To test Doc 6 or 7 being latest, adjust their start_datetime to be after Doc 2
    # Current setup will make Doc 7 the latest matching the `$match` initial criteria if "actions: {$exists: true}" is active.
    # If "actions: {$ne: []}" is used, then Doc 2 would be latest, then Doc 6 if its time is after Doc 2.

    # Modify datetimes to make Doc 2 latest among those with actions
    await collection.update_one({"_id": (await collection.find_one({"actions.0.application": "AppX"}))["_id"]}, {"$set": {"start_datetime": datetime(2023, 1, 1, 17, 0, 0)}})
    await collection.update_one({"_id": (await collection.find_one({"actions": []}))["_id"]}, {"$set": {"start_datetime": datetime(2023, 1, 1, 16, 0, 0)}}) # Doc 6
    await collection.update_one({"_id": (await collection.find_one({"name": "Safehouse", "operation_type": "failover", "actions": {"$exists": False}}))["_id"]}, {"$set": {"start_datetime": datetime(2023, 1, 1, 15, 0, 0)}}) # Doc 7

    actions_list = await get_latest_safehouse_failover_actions(collection)
    if actions_list is not None:
        print("Retrieved actions:")
        for action in actions_list:
            print(action)
    else:
        print("No matching document found or actions were empty/missing in the latest one.")
    # Expected output for current setup (Doc 2 is latest with actions):
    # Retrieved actions:
    # {'application': 'AppX', 'handler': 'HandlerX'}
    # {'application': 'AppY', 'handler': 'HandlerY'}


    print("\n--- Test Case 2: Make Doc 6 (empty actions) the latest qualifying document ---")
    # This test depends on how strictly you filter for "actions" in the $match stage.
    # If "$match" includes "actions": {"$ne": []}, then Doc 6 won't be picked.
    # If "$match" only includes "actions": {"$exists": True}, Doc 6 will be picked, and processed_actions will be [].
    await collection.update_one({"_id": (await collection.find_one({"actions": []}))["_id"]}, {"$set": {"start_datetime": datetime(2023, 1, 1, 18, 0, 0)}}) # Doc 6 now latest
    
    actions_list_doc6 = await get_latest_safehouse_failover_actions(collection)
    if actions_list_doc6 is not None:
        print("Retrieved actions (from Doc 6 which had empty actions):")
        if actions_list_doc6:
            for action in actions_list_doc6:
                print(action)
        else:
            print("Actions list is empty (as expected for Doc 6).")
    else:
        print("No matching document found or actions were missing in the latest one.")
    # Expected output if Doc 6 is latest:
    # Retrieved actions (from Doc 6 which had empty actions):
    # Actions list is empty (as expected for Doc 6).

    await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
