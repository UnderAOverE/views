def get_aws_credentials_from_environment() -> tuple[str | None, str | None, str | None]:
    """
    Fetches AWS credentials from vault location and loads them into the environment variables.
    :return: AWS credentials (access key ID, secret access key, session token).

    :return: Tuple containing AWS access key ID, secret access key, and session token.
    :rtype: tuple[str | None, str | None, str | None]
    :raises FileNotFoundError: If the vault file is not found.
    :raises KeyError: If the required keys are not found in the vault.
    :raises Exception: If any other error occurs while fetching the credentials.
    :note: The function loads the AWS credentials from a .env file using the dotenv library, refer AWSVaultConfig
    """

    try:
        credentials_file: str = f"/vault/secrets/credentials.aws"
        if not os.path.exists(credentials_file):
            logger.error(f"Vault file not found at {credentials_file}, please ensure the file exists and the path is correct.")
            return None, None, None

        # Load the AWS credentials from the vault
        load_dotenv(dotenv_path=credentials_file)

        # Get the AWS credentials from the environment variables
        aws_access_key_id = os.environ.get("eks_settings.hashicorp_config.aws_access_key_id")
        aws_secret_access_key = os.environ.get("eks_settings.hashicorp_config.aws_secret_access_key")
        aws_session_token = os.environ.get("eks_settings.hashicorp_config.aws_session_token")

        # Return the AWS credentials
        return aws_access_key_id, aws_secret_access_key, aws_session_token

    except Exception as generic_exception:
        logger.error(f"Error fetching AWS credentials from vault: {repr(generic_exception)}")

    return None, None, None