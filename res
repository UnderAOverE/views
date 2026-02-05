# For start operations, determine target replicas
if lifecycle_request.replicas is not None:
    # User provided replicas, but check MongoDB first for last successful stop
    try:
        stop_record = await self.audit_service.get_last_successful_stop_operation_by_client(client)

        if stop_record and hasattr(stop_record, "details") and hasattr(stop_record.details, "replicas_before"):
            if (
                stop_record.object_name != lifecycle_request.object_name
                and stop_record.namespace != lifecycle_request.namespace
                and stop_record.cluster_name != lifecycle_request.cluster_name
            ):
                logger.warning(
                    "No MongoDB stop record found that matches the current operation context. "
                    "Ignoring MongoDB record and using payload replicas."
                )
                target_replicas = int(lifecycle_request.replicas)
                operation_messages.append(
                    f"No MongoDB stop record found that matches the current operation context, "
                    f"using payload replicas: target replicas = {target_replicas}"
                )
            else:
                target_replicas = int(stop_record.details.replicas_before)
                operation_messages.append(
                    f"Using MongoDB record: target replicas = {target_replicas}"
                )
        else:
            target_replicas = int(lifecycle_request.replicas)
            operation_messages.append(
                f"Using payload replicas: target replicas = {target_replicas}"
            )

    except Exception as mongo_exception:
        logger.warning(f"Failed to lookup MongoDB stop record: {str(mongo_exception)}")
        target_replicas = int(lifecycle_request.replicas)
        operation_messages.append(
            f"MongoDB lookup failed, using payload replicas: target replicas = {target_replicas}"
        )

else:
    # No replicas provided, must use MongoDB lookup
    stop_record = await self.audit_service.get_last_successful_stop_operation_by_client(client)

    if stop_record and hasattr(stop_record, "details") and hasattr(stop_record.details, "replicas_before"):
        if (
            stop_record.object_name != lifecycle_request.object_name
            and stop_record.namespace != lifecycle_request.namespace
            and stop_record.cluster_name != lifecycle_request.cluster_name
        ):
            logger.warning(
                "No MongoDB stop record found that matches the current operation context. "
                "Cannot determine target replicas for start operation."
            )
            raise ValueError(
                "No replicas specified in payload and no MongoDB record found that matches "
                "the current operation context to determine target replicas for start operation."
            )

        target_replicas = int(stop_record.details.replicas_before)
        operation_messages.append(
            f"Using MongoDB record: target replicas = {target_replicas}"
        )
    else:
        raise ValueError(
            "No replicas specified in payload and no previous stop operation found in database"
        )