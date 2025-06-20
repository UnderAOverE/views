from typing import Dict, List, Any, Set, Optional
from pymongo import MongoClient

# --- 1. Function to Extract and Clean ci_items ---
def extract_and_clean_ci_items(data: Dict[str, Any]) -> Set[str]:
    """
    Extracts all 'ci_item' values from the 'related_items' structure
    and cleans them to get the base device name (part before '\\').
    Returns a set of unique, cleaned device names.
    """
    cleaned_device_names: Set[str] = set()
    related_items_list = data.get("related_items", [])

    for item_group in related_items_list:
        if isinstance(item_group, dict):
            ci_data_list = item_group.get("data", [])
            for ci_entry in ci_data_list:
                if isinstance(ci_entry, dict):
                    ci_item_value = ci_entry.get("ci_item")
                    if isinstance(ci_item_value, str):
                        # Clean the ci_item: take only the part before '\\'
                        # Handle both single and double backslashes if they might occur
                        base_device_name = ci_item_value.split('\\\\')[0].split('\\')[0]
                        cleaned_device_names.add(base_device_name)
    return cleaned_device_names

# --- 2. Function to Lookup App IDs in MongoDB ---
def fetch_app_ids_for_devices(
    db_collection, # Your PyMongo collection object
    device_names: Set[str]
) -> Dict[str, Optional[str]]:
    """
    Looks up documents in MongoDB where 'DeviceName' matches any of the
    provided device_names and fetches their 'appid'.

    :param db_collection: PyMongo collection object.
    :param device_names: A set of cleaned device names to look up.
    :return: A dictionary mapping device names to their appid (or None if not found/no appid).
    """
    if not device_names:
        return {}

    # Query for documents where DeviceName is in our list of device_names
    # We only need the DeviceName and appid fields
    query = {"DeviceName": {"$in": list(device_names)}}
    projection = {"DeviceName": 1, "appid": 1, "_id": 0}

    results = db_collection.find(query, projection)

    device_to_appid_map: Dict[str, Optional[str]] = {name: None for name in device_names} # Initialize with None

    for doc in results:
        device_name_from_db = doc.get("DeviceName")
        appid = doc.get("appid") # appid might be missing or None in the DB document
        if device_name_from_db in device_to_appid_map: # Should always be true due to $in query
            device_to_appid_map[device_name_from_db] = appid

    return device_to_appid_map

# --- Example Usage ---
if __name__ == "__main__":
    # Your input data
    input_data = {
        "name": "test",
        "env": "pord",
        "related_items": [
            {
                "table": "task_ci",
                "record_count": 122.0,
                "remarks": [],
                "data": [
                    {"ci_item": "ABCD-PRD1924"},
                    {"ci_item": "EFGH-PRD3922"},
                    {"ci_item": "IJKL-PRD3923\\\\ACQ855GT1-SRV5"}, # Double backslash
                    {"ci_item": "SINGLE-BACKSLASH\\EXTRAINFO"},   # Single backslash
                    {"ci_item": "MNOP-PRD1902"},
                    {"ci_item": "QRST-PRD1922"},
                    {"ci_item": "NOBACKSLASH"}
                ]
            },
            {
                "table": "sysapproval_group",
                "record_count": 0.0,
                "remarks": [],
                "data": []
            }
        ]
    }

    # 1. Extract and clean CI items
    device_names_to_lookup = extract_and_clean_ci_items(input_data)
    print(f"Cleaned device names to look up: {device_names_to_lookup}")
    # Expected: {'MNOP-PRD1902', 'QRST-PRD1922', 'ABCD-PRD1924', 'SINGLE-BACKSLASH', 'IJKL-PRD3923', 'EFGH-PRD3922', 'NOBACKSLASH'}

    # --- Setup MongoDB Connection (replace with your actual connection) ---
    try:
        client = MongoClient('mongodb://localhost:27017/') # Your MongoDB connection string
        db = client['mydatabase']       # Your database name
        ci_collection = db['devices'] # The collection where DeviceName and appid are stored
        
        # --- Create some sample data in MongoDB for testing ---
        ci_collection.delete_many({}) # Clear existing test data
        ci_collection.insert_many([
            {"DeviceName": "ABCD-PRD1924", "appid": "APP001", "other_field": "data1"},
            {"DeviceName": "EFGH-PRD3922", "appid": "APP002"},
            {"DeviceName": "IJKL-PRD3923", "appid": "APP003", "location": "DC1"},
            # MNOP-PRD1902 will not have an appid in this example
            {"DeviceName": "MNOP-PRD1902", "location": "DC2"},
            # QRST-PRD1922 will not be in the DB for this example
            {"DeviceName": "SINGLE-BACKSLASH", "appid": "APP004"},
            {"DeviceName": "NOBACKSLASH", "appid": "APP005"},
            # A device not in our lookup list
            {"DeviceName": "XYZ-OTHER", "appid": "APP999"}
        ])
        print(f"Inserted sample data into MongoDB collection: {ci_collection.name}")

        # 2. Fetch App IDs from MongoDB
        app_id_map = fetch_app_ids_for_devices(ci_collection, device_names_to_lookup)
        print("\n--- Device to AppID Mapping ---")
        for device, appid in app_id_map.items():
            print(f"Device: {device:<20} AppID: {appid}")

        # You can then filter out devices that didn't have an appid or weren't found, if needed
        devices_with_appids = {dev: aid for dev, aid in app_id_map.items() if aid is not None}
        print("\n--- Devices with found AppIDs ---")
        print(devices_with_appids)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'client' in locals():
            client.close()
