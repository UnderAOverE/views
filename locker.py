# builder.py
from __future__ import annotations
from typing import Any

from context import AppContext, ThrottleLogsService, NotificationService


class AppContextBuilder:
    """
    Constructs an AppContext object using a fluent interface.
    This separates the complex construction logic from the AppContext's representation.
    """
    def __init__(self, application: str, environment: str):
        # Required parameters are set in the constructor
        self._application = application
        self._environment = environment
        
        # Optional/fetched parameters are initialized to None
        self._cbql_status: str | None = None
        self._appdynamics_lps: float | None = None
        self._akamai_details: dict[str, int | str] | None = None
        self._current_status: dict[str, Any] | None = None
        self._spunk_lps: dict[str, Any] | None = None
        self._messages: dict[str, str] | None = None
        self._settings: dict[str, Any] | None = None
        self._throttle_logs_service: ThrottleLogsService | None = None
        self._notification_service: NotificationService | None = None
        self._execution_id: str | None = None

    def with_cbql_status(self, status: str) -> AppContextBuilder:
        self._cbql_status = status
        return self

    def with_appdynamics_lps(self, lps: float) -> AppContextBuilder:
        self._appdynamics_lps = lps
        return self

    def with_akamai_details(self, details: dict[str, int | str]) -> AppContextBuilder:
        self._akamai_details = details
        return self

    def with_current_status(self, status: dict[str, Any]) -> AppContextBuilder:
        self._current_status = status
        return self

    def with_spunk_lps(self, lps: dict[str, Any]) -> AppContextBuilder:
        self._spunk_lps = lps
        return self

    def with_messages(self, messages: dict[str, str]) -> AppContextBuilder:
        self._messages = messages
        return self

    def with_settings(self, settings: dict[str, Any]) -> AppContextBuilder:
        self._settings = settings
        return self
        
    def with_throttle_logs_service(self, service: ThrottleLogsService) -> AppContextBuilder:
        self._throttle_logs_service = service
        return self

    def with_notification_service(self, service: NotificationService) -> AppContextBuilder:
        self._notification_service = service
        return self
        
    def with_execution_id(self, execution_id: str) -> AppContextBuilder:
        self._execution_id = execution_id
        return self

    def build(self) -> AppContext:
        """
        Validates that all required fields are set and creates the final AppContext object.
        """
        required_attrs = [
            '_cbql_status', '_appdynamics_lps', '_akamai_details', '_current_status', 
            '_spunk_lps', '_messages', '_settings', '_throttle_logs_service', '_notification_service'
        ]
        for attr in required_attrs:
            if getattr(self, attr) is None:
                raise ValueError(f"Cannot build AppContext: '{attr}' is not set.")

        return AppContext(
            application=self._application,
            environment=self._environment,
            cbql_status=self._cbql_status,
            appdynamics_lps=self._appdynamics_lps,
            akamai_details=self._akamai_details,
            current_status=self._current_status,
            spunk_lps=self._spunk_lps,
            messages=self._messages,
            settings=self._settings,
            throttle_logs_service=self._throttle_logs_service,
            notification_service=self._notification_service,
            execution_id=self._execution_id
        )



app_context = (
    AppContextBuilder(application=digital_application, environment=throttle_config.environment)
    .with_cbql_status(backend_service.check_cbql_status())
    .with_appdynamics_lps(backend_service.get_appdynamics_lps())
    .with_akamai_details(backend_service.get_akamai_details())
    .with_current_status(backend_service.get_current_status())
    .with_spunk_lps(backend_service.get_spunk_lps())
    .with_messages(backend_service.get_messages())
    .with_settings(backend_service.get_settings())
    .with_throttle_logs_service(backend_service.get_throttle_logs_service())
    .with_notification_service(backend_service.get_notification_service())
    .build()
)
