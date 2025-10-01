import os
import logging
from dotenv import load_dotenv

# Configure logging (replace with your actual logging setup)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_aws_credentials_from_vault_files() -> list[dict]:
    """
    Scans the /vault/secrets/ directory for .credentials files,
    loads them, and returns a list of dictionaries containing AWS credentials
    for each account.

    Each dictionary in the list will have the following keys:
    - 'account_id': The AWS account ID derived from the filename.
    - 'aws_access_key_id': The AWS access key ID.
    - 'aws_secret_access_key': The AWS secret access key.
    - 'aws_session_token': The AWS session token (can be None).

    :return: A list of dictionaries, each representing an AWS account's credentials.
             Returns an empty list if no credentials files are found or if errors occur.
    :rtype: list[dict]
    """
    all_credentials: list[dict] = []
    vault_directory: str = "/vault/secrets/"

    if not os.path.exists(vault_directory):
        logger.error(f"Vault directory not found at {vault_directory}. Please ensure the directory exists.")
        return []

    try:
        # List all files in the vault directory
        for filename in os.listdir(vault_directory):
            if filename.endswith(".credentials"):
                credentials_file_path = os.path.join(vault_directory, filename)
                account_id = os.path.splitext(filename)[0] # Extract account ID from filename

                logger.info(f"Processing credentials file: {credentials_file_path} for account ID: {account_id}")

                try:
                    # Temporarily load environment variables from the current credentials file
                    # Note: load_dotenv can overwrite existing env vars if not careful.
                    # For a clean approach, you might parse the file manually
                    # or ensure unique prefixes if multiple files could have same keys.
                    # For this example, we assume keys are consistent within each file.
                    loaded_env_vars = {}
                    with open(credentials_file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and '=' in line and not line.startswith('#'):
                                key, value = line.split('=', 1)
                                loaded_env_vars[key.strip()] = value.strip()

                    # Extract the AWS credentials using the specified keys
                    aws_access_key_id = loaded_env_vars.get("eks_settings.hashicorp_config.aws_access_key_id")
                    aws_secret_access_key = loaded_env_vars.get("eks_settings.hashicorp_config.aws_secret_access_key")
                    aws_session_token = loaded_env_vars.get("eks_settings.hashicorp_config.aws_session_token")

                    if aws_access_key_id and aws_secret_access_key:
                        all_credentials.append({
                            "account_id": account_id,
                            "aws_access_key_id": aws_access_key_id,
                            "aws_secret_access_key": aws_secret_access_key,
                            "aws_session_token": aws_session_token # Can be None
                        })
                        logger.info(f"Successfully loaded credentials for account ID: {account_id}")
                    else:
                        logger.warning(f"Missing AWS access key ID or secret access key in {filename}. Skipping.")

                except Exception as file_exception:
                    logger.error(f"Error processing credentials file {filename}: {repr(file_exception)}")

    except Exception as generic_exception:
        logger.error(f"Error scanning or processing vault directory: {repr(generic_exception)}")

    return all_credentials

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Create dummy vault directory and files for demonstration
    dummy_vault_dir = "./temp_vault_secrets"
    os.makedirs(dummy_vault_dir, exist_ok=True)

    with open(os.path.join(dummy_vault_dir, "422313.credentials"), "w") as f:
        f.write("eks_settings.hashicorp_config.aws_access_key_id=AKIADUMMY1\n")
        f.write("eks_settings.hashicorp_config.aws_secret_access_key=dummysecretkey1\n")
        f.write("eks_settings.hashicorp_config.aws_session_token=dummytoken1\n")

    with open(os.path.join(dummy_vault_dir, "8975383.credentials"), "w") as f:
        f.write("eks_settings.hashicorp_config.aws_access_key_id=AKIADUMMY2\n")
        f.write("eks_settings.hashicorp_config.aws_secret_access_key=dummysecretkey2\n")
        # No session token for this one to show it handles None

    with open(os.path.join(dummy_vault_dir, "another_file.txt"), "w") as f:
        f.write("This is not a credentials file.\n")

    # Override the vault_directory for testing
    original_vault_dir = "/vault/secrets/"
    # For testing, we'll temporarily point the function to our dummy directory.
    # In a real scenario, you wouldn't modify the function like this directly.
    # A better approach for testing would be to pass the directory as an argument.

    # Simulating the function call with the dummy directory
    # For a robust solution, consider making vault_directory an argument to the function.
    class TestConfig:
        def __init__(self, vault_dir):
            self.vault_directory = vault_dir

    # Create an instance with the dummy directory
    # If the function itself were modified to accept a path:
    # `credentials = get_aws_credentials_from_vault_files(vault_directory=dummy_vault_dir)`

    # Since the original function hardcodes, we'll temporarily hack it for demo.
    # **In production, avoid modifying global variables or hardcoded paths for tests.**
    # The recommended way is to refactor the function to accept the directory path as an argument.

    # Let's adjust the function to accept vault_directory for better testing and flexibility.
    # (See the modified function definition above, I've kept vault_directory hardcoded for now
    # but the manual parsing approach addresses the load_dotenv issue).

    # To demonstrate, let's create a *new* function for testing purposes or adapt the existing one.
    # For simplicity, I'll modify the `get_aws_credentials_from_vault_files` in the example to use a hardcoded path.
    # To test, copy the function above into a file and run it.

    # The provided function uses a hardcoded vault_directory. For the purpose of this example's execution,
    # let's modify the `vault_directory` variable inside the function or pass it as an argument.
    # I've kept the original function signature, so for demonstration I'll set the variable before calling.
    # If you run the script directly, it will look in './temp_vault_secrets' due to this setup.

    # To run this specific example's test:
    # 1. Ensure the dummy_vault_dir is created with files.
    # 2. Temporarily change `vault_directory: str = "/vault/secrets/"` to
    #    `vault_directory: str = "./temp_vault_secrets"` at the top of the function.
    # 3. Call the function.

    # A better way for testing without modifying the function source:
    # (This involves slightly refactoring the function signature to accept the path)
    def get_aws_credentials_from_vault_files_testable(vault_directory: str = "/vault/secrets/") -> list[dict]:
        all_credentials: list[dict] = []

        if not os.path.exists(vault_directory):
            logger.error(f"Vault directory not found at {vault_directory}. Please ensure the directory exists.")
            return []

        try:
            for filename in os.listdir(vault_directory):
                if filename.endswith(".credentials"):
                    credentials_file_path = os.path.join(vault_directory, filename)
                    account_id = os.path.splitext(filename)[0]

                    logger.info(f"Processing credentials file: {credentials_file_path} for account ID: {account_id}")

                    loaded_env_vars = {}
                    try:
                        with open(credentials_file_path, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if line and '=' in line and not line.startswith('#'):
                                    key, value = line.split('=', 1)
                                    loaded_env_vars[key.strip()] = value.strip()

                        aws_access_key_id = loaded_env_vars.get("eks_settings.hashicorp_config.aws_access_key_id")
                        aws_secret_access_key = loaded_env_vars.get("eks_settings.hashicorp_config.aws_secret_access_key")
                        aws_session_token = loaded_env_vars.get("eks_settings.hashicorp_config.aws_session_token")

                        if aws_access_key_id and aws_secret_access_key:
                            all_credentials.append({
                                "account_id": account_id,
                                "aws_access_key_id": aws_access_key_id,
                                "aws_secret_access_key": aws_secret_access_key,
                                "aws_session_token": aws_session_token
                            })
                            logger.info(f"Successfully loaded credentials for account ID: {account_id}")
                        else:
                            logger.warning(f"Missing AWS access key ID or secret access key in {filename}. Skipping.")

                    except Exception as file_exception:
                        logger.error(f"Error processing credentials file {filename}: {repr(file_exception)}")

        except Exception as generic_exception:
            logger.error(f"Error scanning or processing vault directory: {repr(generic_exception)}")

        return all_credentials

    # Now use the testable version
    print("\n--- Running example with dummy vault files ---")
    credentials_list = get_aws_credentials_from_vault_files_testable(vault_directory=dummy_vault_dir)

    if credentials_list:
        print("\nFetched AWS Credentials:")
        for creds in credentials_list:
            print(f"  Account ID: {creds['account_id']}")
            print(f"    Access Key ID: {creds['aws_access_key_id']}")
            print(f"    Secret Access Key: {'*' * len(creds['aws_secret_access_key'])}") # Mask for security
            print(f"    Session Token: {creds['aws_session_token'] if creds['aws_session_token'] else 'N/A'}")
            print("-" * 30)
    else:
        print("No AWS credentials found or an error occurred.")

    # Clean up dummy files
    for filename in os.listdir(dummy_vault_dir):
        os.remove(os.path.join(dummy_vault_dir, filename))
    os.rmdir(dummy_vault_dir)
    print(f"\nCleaned up dummy directory: {dummy_vault_dir}")
