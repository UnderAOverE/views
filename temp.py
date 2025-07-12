import json

def load_and_update_rule(filepath, rule_identifier, new_values):
    """
    Loads a JSON file, updates a specific rule in memory, and returns the result as a dictionary.

    Args:
        filepath (str): The path to the input JSON file.
        rule_identifier (dict): A key-value pair to find the rule to update.
                                Example: {'header': 'Login'}
        new_values (dict): A dictionary containing the new data to set.
                           Keys can be 'path', 'client_id', 'moreInfo', etc.

    Returns:
        dict: The modified Python dictionary with the updated rule.
        None: Returns None if the file cannot be found or parsed as JSON.
    """
    try:
        # Step 1: Load the JSON file into a Python dictionary
        with open(filepath, 'r') as f:
            config_data = json.load(f)
            
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filepath}'. Please check its format.")
        return None

    # Step 2: Find and update the specific rule within the loaded dictionary
    rule_found = False
    
    # We assume the identifier has one key-value pair for this example
    id_key, id_value = list(rule_identifier.items())[0]

    if 'Rules' in config_data and isinstance(config_data['Rules'], list):
        for rule in config_data['Rules']:
            # Check if this is the rule we want to update
            if rule.get(id_key) == id_value:
                print(f"Found rule with '{id_key}: {id_value}'. Applying updates...")
                
                # Update top-level keys if provided
                if 'path' in new_values:
                    rule['path'] = new_values['path']
                if 'client_id' in new_values:
                    rule['client_id'] = new_values['client_id']
                
                # Update the nested 'moreInfo' key
                if 'moreInfo' in new_values:
                    if 'response' in rule:
                        rule['response']['moreInfo'] = new_values['moreInfo']
                
                rule_found = True
                break # Stop searching after finding and updating the rule

    if not rule_found:
        print(f"Warning: No rule found matching '{rule_identifier}'. Returning data as is.")

    # Step 3: Return the modified dictionary
    return config_data


# --- Example of How to Use the Function ---
if __name__ == "__main__":
    # First, let's create a sample config.json for the example to work
    sample_data = {
        "Rules": [
            {
                "path": [], "client_id": [], "percentage": 0, "header": "Login",
                "response": {"type": "ERROR", "code": "ERR01", "details": "Outage", "moreInfo": ""},
                "status": 503
            },
            {
                "path": ["/dashboard"], "client_id": ["dash-ui"], "percentage": 100, "header": "Dashboard",
                "response": {"type": "OK", "code": "OK200", "details": "Operational", "moreInfo": ""},
                "status": 200
            }
        ]
    }
    config_filename = 'config.json'
    with open(config_filename, 'w') as f:
        json.dump(sample_data, f, indent=4)
    print(f"Created a sample '{config_filename}' for demonstration.")
    
    # --- Now, use the function ---
    
    # Define the new values you want to insert
    updates_for_login_rule = {
        "path": ["/api/auth/login", "/api/auth/token"],
        "client_id": ["webapp-v1", "mobile-app-v3"],
        "moreInfo": "https://status.example.com/outages/login-service-degraded"
    }

    # Call the function. It reads the file and returns a dictionary.
    updated_dict = load_and_update_rule(
        filepath=config_filename,
        rule_identifier={'header': 'Login'},
        new_values=updates_for_login_rule
    )

    # The function returns the dictionary, which we can now use or inspect
    if updated_dict:
        print("\n--- Function returned the following dictionary: ---")
        # Use json.dumps to pretty-print the dictionary for verification
        print(json.dumps(updated_dict, indent=4))
