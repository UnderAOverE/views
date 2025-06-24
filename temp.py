for application in [ApplicationConstants.CBOL, ApplicationConstants.MOB]:

    # Validate if the current application status and requested operation is valid.
    match application:

        case ApplicationConstants.CBOL:
            run_status.cbol_status = STATUS_TRANSITIONS.get((run_status.cbol_status, run_status.operation), None)
            if run_status.cbol_status is None:
                details: str = f"getsafemodes[{application.value}] active = {getsafemodes[application.value]}"
                logger.warning(details)
                await run_status.run_logs_service.update_check(handler_name, False, details=details)
            else:
                # Query backend collection to get the status for the application.
                backend_status, backend_details = await run_status.backend_service.check_safemodeauditlogs_status(application=application.value)
                prerequisite_details: str = f"getsafemodes[{application.value}] active = {getsafemodes[application.value]} & {backend_details}"

                if backend_status:
                    logger.info(prerequisite_details)
                else:
                    logger.warning(prerequisite_details)
                    run_status.cbol_status = None

                await run_status.run_logs_service.update_check(handler_name, backend_status, details=prerequisite_details)

        case ApplicationConstants.MOB:
            run_status.mbol_status = STATUS_TRANSITIONS.get((run_status.mbol_status, run_status.operation), None)
            if run_status.mbol_status is None:
                details: str = f"getsafemodes[{application.value}] active = {getsafemodes[application.value]}"
                logger.warning(details)
                await run_status.run_logs_service.update_check(handler_name, False, details=details)
            else:
                # Query backend collection to get the status for the application.
                backend_status, backend_details = await run_status.backend_service.check_safemodeauditlogs_status(application=application.value)
                prerequisite_details: str = f"getsafemodes[{application.value}] active = {getsafemodes[application.value]} & {backend_details}"

                if backend_status:
                    logger.info(prerequisite_details)
                else:
                    logger.warning(prerequisite_details)
                    run_status.mbol_status = None

                await run_status.run_logs_service.update_check(handler_name, backend_status, details=prerequisite_details)