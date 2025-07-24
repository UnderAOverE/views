@distributed_lock("DigitalResiliency_throttle_engine", 300)
async def run_operations() -> None:
    digital_application: StrEnum = MongoConstants.Application
    throttle_config_environment: str = OSE_THROTTLE_ENVIRONMENT_MAPPER.get(
        os.environ.get(
            "AMP_OSE_ENVIRONMENT",
            "towncenter"
        ),
        "UAT"
    )

    log_datetime: str = datetime.now(timezone.utc).strftime("%m-%d-%Y %H:%M:%S %Z")
    logger_extras = {
        "application": digital_application,
        "environment": throttle_config_environment,
        "module_name": "__main__",
        "version": module_version,
    }

    try:
        logger.debug("Starting throttling and un-throttling operations", extra=logger_extras)

        backend_service: BackendService = await BackendService.get_service(
            application=digital_application,
            environment=throttle_config_environment,
        )

        # Below service calls are used to fetch the application details, Akamai details, throttle settings, and status.
        backend_details = {
            "appdynamics_lps": await backend_service.get_appdynamics_lps(),
            "application_details": await backend_service.get_application_details(),
            "akamai_details": await backend_service.get_akamai_details(),
            "cbol_status": await backend_service.check_cbol_status(),
            "current_status": await backend_service.get_current_status(),
            "throttle_messages": await backend_service.get_throttle_messages(),
            "throttle_settings": await backend_service.get_throttle_settings(),
            "splunk_lps": await backend_service.get_splunk_lps(),
        }

        manager = Manager(application=digital_application, environment=throttle_config_environment, backend_details=backend_details)
        logger.info("__________________________THROTTLE OPERATION__________________________", extra=logger_extras)
        await manager.execute_throttle()
        
        
def distributed_lock(job_name: str, dblock_ttl: int = 60) -> Callable[[Callable], Callable]:
    def decorator(func):
        @wraps(func)  # This is crucial for preserving the metadata (name, docstring, etc.) of the decorated function.
        # HC Reid & OB Mahomes can't win with Mr. Brady in the building.
        def wrapper(*args, **kwargs):
            # Generate the lock name based on function name and its arguments.
            hashed_arg_string = hashlib.md5(f"{args}{kwargs}".encode("utf-8")).hexdigest()
            lock_name = f"{job_name}_{hashed_arg_string}"

            # Acquire the lock before running the job
            if acquire_lock(lock_name, dblock_ttl):

                try:
                    if asyncio.iscoroutinefunction(func):  # Async function
                        return asyncio.run(func(*args, **kwargs))

                    else:  # Sync function
                        return func(*args, **kwargs)

                except Exception as generic_exception:
                    logger.error(f"Error during job execution: {repr(generic_exception)}", extra={"version": module_version})
                    raise

                finally:
                    release_lock(lock_name)

            else:
                return None

        return wrapper

    return decorator