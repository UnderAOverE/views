# Inside main.py
backend_service = BackendService = BackendService.get_service(application=digital_application, environment=throttle_config.environment)
backend_details = (backend_service.check_cbql_status(), backend_service.get_appdynamics_lps(), backend_service.get_akamai_details(),
                   backend_service.get_current_status(), backend_service.get_spunk_lps(), backend_service.get_messages(),
                   backend_service.get_settings(), backend_service.get_throttle_logs_service(), backend_service.get_notification_service())
manager = Manager(application=digital_application, environment=throttle_config.environment, backend_details=backend_details)

# Inside manager.py
class Manager:
    def __init__(self, application: str, environment: str, backend_details: tuple[float, dict[str, Any], dict[str, int | str], 
                 str, dict[str, Any], dict[str, str], dict[str, Any], float | None]):
        self.appdynamics_lps, self.application, self.application_details, self.akamai_details, self.cbql_status, self.current_status, \
        self.environment, self.messages, self.settings, self.spunk_lps = backend_details
        self.helper = Helper(appdynamics_lps=self.appdynamics_lps, application=self.application,
                             application_details=self.application_details, akamai_details=self.akamai_details,
                             cbql_status=self.cbql_status, current_status=self.current_status,
                             environment=self.environment, messages=self.messages, settings=self.settings, spunk_lps=self.spunk_lps)

# Inside helper.py
class Helper:
    def __init__(self, appdynamics_lps: float, application: str, application_details: dict[str, Any], akamai_details: dict[str, int | str],
                 cbql_status: str, current_status: dict[str, Any], environment: str, messages: dict[str, Any],
                 settings: dict[str, Any], spunk_lps: float, execution_id: str | None = None, throttle_logs_service: ThrottleLogsService | None = None,
                 notification_service: NotificationService | None = None):

        self.appdynamics_lps = float(appdynamics_lps)
        self.application = application
        self.application_details = application_details
        self.akamai_details = akamai_details
        self.cbql_status = cbql_status
        self.current_status = current_status
        self.environment = environment
        self.messages = messages
        self.settings = settings
        self.spunk_lps = spunk_lps

        # Set the config name based on the application and environment.
        self.config_name = f"{application}_{environment}_throttle_config"

        self.execution_id: str | None = execution_id
        self.throttle_logs_service: ThrottleLogsService | None = throttle_logs_service
        self.notification_service: NotificationService | None = notification_service

        self._operation: StrEnum | None = None

    @property
    def operation(self) -> StrEnum:
        if self._operation is None:
            raise ValueError("Operation is not set. Please set the operation before accessing it.")
        return self._operation

    @operation.setter
    def operation(self, value: StrEnum) -> None:
        if not isinstance(value, StrEnum):
            raise TypeError("Operation must be an instance of StrEnum.")
        self._operation = value