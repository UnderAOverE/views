class PrerequisiteHandler(ResultHandler):
    async def handle(self, run_status: RunStatus) -> RunStatus:
        handler_name = ApplicationConstants.PREREQUISITE_HANDLER.value
        logger.debug(f"handler_name: {handler_name}, run status: {run_status.model_dump()}")
        get_safemodes = await run_status.safe_mode_api_service.get_safemodes()
        if not get_safemodes.get("status") and run_status.run_id:
            details = f"getsafemodes API call failed with response: {get_safemodes_return}"
            logger.error(details)
            await run_status.run_logs_service.update_check(handler_name, False, details=details)
            run_status.is_stopped = True
            log_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            run_status.notification_service.send_to_developers(
                {"run id": run_status.run_id, "error": "getsafemodes API call failed with response: (getsafemodes_return).",
                 "exception_details": details, "table_title": "Error Details", "log_datetime": log_datetime})
            return run_status

        run_status.cbol_status = ApplicationConstants.ACTIVATE if get_safemodes[ApplicationConstants.CBOL.value] else ApplicationConstants.DEACTIVATE
        run_status.mbol_status = ApplicationConstants.ACTIVATE if get_safemodes[ApplicationConstants.MOB.value] else ApplicationConstants.DEACTIVATE
        
        for application in [ApplicationConstants.CBOL, ApplicationConstants.MOB]:
            match application:
                case ApplicationConstants.CBOL:
                    run_status.cbol_status = STATUS_TRANSITIONS.get((run_status.cbol_status, run_status.operation), None)
                    if run_status.cbol_status is None:
                        details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]}"
                        logger.warning(details)
                        await run_status.run_logs_service.update_check(handler_name, False, details=details)
                        run_status.is_stopped = True
                        return run_status
                    else:
                        backend_status, backend_details = await run_status.backend_service.check_safemodeautologs_status(application=application.value)
                        prerequisite_details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]} : {backend_details}"
                        if backend_status:
                            logger.info(prerequisite_details)
                        else:
                            logger.warning(prerequisite_details)
                            run_status.cbol_status = None
                            await run_status.run_logs_service.update_check(handler_name, backend_status, details=prerequisite_details)

                case ApplicationConstants.MOB:
                    run_status.mbol_status = STATUS_TRANSITIONS.get((run_status.mbol_status, run_status.operation), None)
                    if run_status.mbol_status is None:
                        details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]}"
                        logger.warning(details)
                        await run_status.run_logs_service.update_check(handler_name, False, details=details)
                        run_status.is_stopped = True
                        return run_status
                    else:
                        backend_status, backend_details = await run_status.backend_service.check_safemodeautologs_status(application=application.value)
                        prerequisite_details: str = f"getsafemodes/{application.value} active - {get_safemodes[application.value]} : {backend_details}"
                        if backend_status:
                            logger.info(prerequisite_details)
                        else:
                            logger.warning(prerequisite_details)
                            run_status.mbol_status = None
                            await run_status.run_logs_service.update_check(handler_name, backend_status, details=prerequisite_details)

        if run_status.is_stopped or run_status.cbol_status is None or run_status.mbol_status is None:
            logger.warning(f"handler_name: Stopping the run id: {run_status.run_id}")
            run_status.is_stopped = True

        return await super().handle(run_status)
