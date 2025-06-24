    # Call the getsafemodes API to get the latest safemode status for the application and set the run_status for application.
    getsafemodes_return, getsafemodes = await run_status.safemode_api_service.get_safemodes()

    if not getsafemodes_return:
        details: str = f"getsafemodes API call failed with response: {getsafemodes_return}"
        logger.error(details)
        await run_status.run_logs_service.update_check(handler_name, False, details=details)
        run_status.is_stopped = True

        log_datetime: str = datetime.now(timezone.utc).strftime("%m %d %Y %H:%M:%S %Z")
        exception_details = {
            "run_id": run_status.run_id,
            "error": f"getsafemodes API call failed with response: {getsafemodes_return}",
        }
        run_status.notification_service.send_email_to_developers(table_details=exception_details, table_title=f"Error Details ({log_datetime})")

        return await super().handle(run_status)
