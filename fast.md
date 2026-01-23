class OSEGuardRailService:
    RESOURCE_POD_READINESS: str = "Resource Pod Readiness"
    CURRENT_REPLICAS: str = "Current Replicas Check"
    PDB_CONSTRAINTS: str = "PDB Constraints Check"
    HPA_CONSTRAINTS: str = "HPA Constraints Check"
    RESOURCE_QUOTA: str = "Resource Quota Check"
    LIMIT_RANGE: str = "Limit Range Check"
    REPLICA_LIMIT: str = "Replica Limit Check"

    CHECK_NAMES: dict[str, str] = {
        "RESOURCE_POD_READINESS": RESOURCE_POD_READINESS,
        "CURRENT_REPLICAS": CURRENT_REPLICAS,
        "PDB_CONSTRAINTS": PDB_CONSTRAINTS,
        "HPA_CONSTRAINTS": HPA_CONSTRAINTS,
        "RESOURCE_QUOTA": RESOURCE_QUOTA,
        "LIMIT_RANGE": LIMIT_RANGE,
        "REPLICA_LIMIT": REPLICA_LIMIT,
    }

    def __init__(self,) -> None:
        """
        OSEGuardRailService constructor.
        :return: None
        :rtype: None
        """
        self.ose_settings = environment_settings.ose
        self.content_type = f"Content-Type: {self.ose_settings.content_type}"
        self.httpx_client: HTTPXClient = HTTPXClient(
            ca_certificate_path=self.ose_settings.ca_certificate_path,
            verify_ssl=self.ose_settings.ssl_verify,
        )
    # enddef

    @classmethod
    async def get_service(cls,) -> Self:
        """
        Factory method to create an instance of OSEGuardRailService.
        :return: An instance of OSEGuardRailService.
        :rtype: OSEGuardRailService
        """
        return cls()
    # endAsyncDef

    async def get_scale_settings(self,) -> ScaleSettingsModel:
        """
        Get scale settings from database with fallback to defaults.
        :return: Scale settings model with configured limits and enforcement flags.
        :rtype: ScaleSettingsModel
        """
        try:
            db_settings = await self.settings_service.get_db_settings(
                environment=OSE_ENVIRONMENT,
            )
            if isinstance(db_settings, str) or db_settings is None:
                logger.warning(
                    f"Could not fetch DB settings for {OSE_ENVIRONMENT}, using defaults"
                )
                return ScaleSettingsModel()

            return db_settings
        except Exception as generic_exception:
            logger.warning(
                f"Error fetching scale settings: {generic_exception}, using defaults"
            )
            return ScaleSettingsModel()
    # endTryExcept
# endAsyncDef