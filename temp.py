class Settings(BaseSettings):
    """
    Settings class: This class is used to manage and load application settings from environment,
    related to MongoDB connection, TLS options, write concerns, and connection pooling.
    """

    # Mongo settings
    mongo_db_tls_ca_certificates: str | None = "ca-prod.pem"
    mongo_db_tls_allow_invalid_certificates: bool | None = Field(default=True)
    mongo_db_tls_enabled: bool | None = Field(default=True)

    mongo_db_write_concern: int | str | None = Field(default=1)
    mongo_db_write_journal_acknowledge: bool | None = Field(default=False)
    mongo_db_write_concern_timeout_ms: int | None = Field(default=30000)
    mongo_db_retry_writes: bool | None = Field(default=True)
    mongo_db_tz_aware: bool | None = Field(default=False)

    mongo_db_maximum_pool_size: int | None = Field(default=10)
    mongo_db_minimum_pool_size: int | None = Field(default=1)
    mongo_db_maximum_idle_time_ms: int | None = Field(default=30000)
    mongo_db_connection_timeout_ms: int | None = Field(default=900000)
    mongo_db_socket_timeout_ms: int | None = Field(default=60000)

    mongo_db_server_port_pairs: str = "server1:37017,server2:37017,server3:37017"
    mongo_db_username: str = "MONGO_PROD"

    model_config = ConfigDict(
        extra="allow",
    )

    @classmethod
    @lru_cache()
    def load_from_environment(cls,) -> Self:
        """
        Environment vars loader
        :return None:
        """
        
        
# Database client.
def get_mongo_uri() -> str:
    """
    This is to get the mongo uri string.

    :return: mongo uri string
    :rtype: str
    """
    environment_settings = Settings.load_from_environment()
    app_name = os.getenv("APP_NAME", get_hostname())

    return f"mongodb://{environment_settings.mongo_db_username}:{os.getenv('MONGO_DB_CYBERARK_PASSWORD')}@" \
           f"{environment_settings.mongo_db_server_port_pairs}/admin?tls=" \
           f"{bool_to_str(environment_settings.mongo_db_tls_enabled)}&tlsCAFile=" \
           f"{environment_settings.mongo_db_tls_ca_certificates}&retryWrites=" \
           f"{bool_to_str(environment_settings.mongo_db_retry_writes)}&w=" \
           f"{environment_settings.mongo_db_write_concern}&journal=" \
           f"{bool_to_str(environment_settings.mongo_db_write_journal_acknowledge)}&wtimeoutMS=" \
           f"{environment_settings.mongo_db_write_concern_timeout_ms}&tz_aware=" \
           f"{bool_to_str(environment_settings.mongo_db_tz_aware)}&appname={app_name}" \
           f"&maxPoolSize={environment_settings.mongo_db_maximum_pool_size}" \
           f"&minPoolSize={environment_settings.mongo_db_minimum_pool_size}" \
           f"&maxIdleTimeMS={environment_settings.mongo_db_maximum_idle_time_ms}" \
           f"&connectTimeoutMS={environment_settings.mongo_db_connection_timeout_ms}" \
           f"&socketTimeoutMS={environment_settings.mongo_db_socket_timeout_ms}"


class Database:
    """
    This is the database client class, implemented as a singleton.
    """

    def __new__(cls) -> Self:
        global _mongo_client

        if _mongo_client is None:
            with _mongo_lock:
                if _mongo_client is None:
                    _mongo_client = super(Database, cls).__new__(cls)

        return _mongo_client
