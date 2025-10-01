import os
import logging
import asyncio
import aiofiles # You'll need to install this: pip install aiofiles

# Configure logging (replace with your actual logging setup)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_aws_credentials_from_vault_files_async(vault_directory: str = "/vault/secrets/") -> list[dict]:
    """
    Asynchronously scans the specified directory for .credentials files,
    loads them, and returns a list of dictionaries containing AWS credentials
    for each account.

    Each dictionary in the list will have the following keys:
    - 'account_id': The AWS account ID derived from the filename.
    - 'aws_access_key_id': The AWS access key ID.
    - 'aws_secret_access_key': The AWS secret access key.
    - 'aws_session_token': The AWS session token (can be None).

    :param vault_directory: The path to the directory containing .credentials files.
    :return: A list of dictionaries, each representing an AWS account's credentials.
             Returns an empty list if no credentials files are found or if errors occur.
    :rtype: list[dict]
    """
    all_credentials: list[dict] = []

    if not os.path.exists(vault_directory):
        logger.error(f"Vault directory not found at {vault_directory}. Please ensure the directory exists.")
        return []

    try:
        # os.listdir is synchronous. If vault_directory can be very large
        # or on a slow network file system, this might still block.
        # For truly async listing, you might need specific async OS libraries
        # or run it in a thread pool executor. For most cases, this is acceptable.
        filenames = [f for f in os.listdir(vault_directory) if f.endswith(".credentials")]

        # Create a list of async tasks for processing each file
        tasks = []
        for filename in filenames:
            tasks.append(_process_credentials_file_async(os.path.join(vault_directory, filename)))

        # Run all file processing tasks concurrently
        results = await asyncio.gather(*tasks)

        # Filter out None results (from files that failed to process) and append valid credentials
        for result in results:
            if result:
                all_credentials.append(result)

    except Exception as generic_exception:
        logger.error(f"Error scanning or processing vault directory: {repr(generic_exception)}")

    return all_credentials

async def _process_credentials_file_async(file_path: str) -> dict | None:
    """
    Asynchronously processes a single .credentials file, extracts AWS credentials,
    and returns them as a dictionary.

    :param file_path: The full path to the .credentials file.
    :return: A dictionary of credentials or None if processing failed.
    """
    account_id = os.path.splitext(os.path.basename(file_path))[0]
    logger.info(f"Processing credentials file: {file_path} for account ID: {account_id}")

    try:
        loaded_env_vars = {}
        async with aiofiles.open(file_path, mode='r') as f:
            async for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    loaded_env_vars[key.strip()] = value.strip()

        aws_access_key_id = loaded_env_vars.get("eks_settings.hashicorp_config.aws_access_key_id")
        aws_secret_access_key = loaded_env_vars.get("eks_settings.hashicorp_config.aws_secret_access_key")
        aws_session_token = loaded_env_vars.get("eks_settings.hashicorp_config.aws_session_token")

        if aws_access_key_id and aws_secret_access_key:
            logger.info(f"Successfully loaded credentials for account ID: {account_id}")
            return {
                "account_id": account_id,
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
                "aws_session_token": aws_session_token
            }
        else:
            logger.warning(f"Missing AWS access key ID or secret access key in {os.path.basename(file_path)}. Skipping.")
            return None

    except Exception as file_exception:
        logger.error(f"Error processing credentials file {file_path}: {repr(file_exception)}")
        return None

# Example usage (for testing purposes)
async def main():
    # Create dummy vault directory and files for demonstration
    dummy_vault_dir = "./temp_vault_secrets_async"
    os.makedirs(dummy_vault_dir, exist_ok=True)

    with open(os.path.join(dummy_vault_dir, "422313.credentials"), "w") as f:
        f.write("eks_settings.hashicorp_config.aws_access_key_id=AKIADUMMY1_ASYNC\n")
        f.write("eks_settings.hashicorp_config.aws_secret_access_key=dummysecretkey1_ASYNC\n")
        f.write("eks_settings.hashicorp_config.aws_session_token=dummytoken1_ASYNC\n")

    with open(os.path.join(dummy_vault_dir, "8975383.credentials"), "w") as f:
        f.write("eks_settings.hashicorp_config.aws_access_key_id=AKIADUMMY2_ASYNC\n")
        f.write("eks_settings.hashicorp_config.aws_secret_access_key=dummysecretkey2_ASYNC\n")
        # No session token for this one to show it handles None

    with open(os.path.join(dummy_vault_dir, "another_file.txt"), "w") as f:
        f.write("This is not a credentials file.\n")

    print("\n--- Running example with dummy async vault files ---")
    credentials_list = await get_aws_credentials_from_vault_files_async(vault_directory=dummy_vault_dir)

    if credentials_list:
        print("\nFetched AWS Credentials (Async):")
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

if __name__ == "__main__":
    asyncio.run(main())
