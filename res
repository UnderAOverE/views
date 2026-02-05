# 1. Attempt to fetch the record once
try:
    stop_record = await self.audit_service.get_last_successful_stop_operation_by_client(client)
except Exception as e:
    logger.warning(f"Failed to lookup MongoDB stop record: {str(e)}")
    stop_record = None

# 2. Check if the record is a valid match for this specific request context
is_valid_match = False
if stop_record and hasattr(stop_record, "details") and hasattr(stop_record.details, "replicas_before"):
    is_valid_match = (
        stop_record.object_name == lifecycle_request.object_name and
        stop_record.namespace == lifecycle_request.namespace and
        stop_record.cluster_name == lifecycle_request.cluster_name
    )

# 3. Determine target replicas (Priority: DB Match > Payload > Error)
if is_valid_match:
    target_replicas = int(stop_record.details.replicas_before)
    operation_messages.append(f"Using MongoDB record: target replicas = {target_replicas}")

elif lifecycle_request.replicas is not None:
    # If there was a record but it didn't match, log the warning
    if stop_record:
        logger.warning("MongoDB record found but context mismatch. Using payload replicas.")
    
    target_replicas = int(lifecycle_request.replicas)
    operation_messages.append(f"Using payload replicas: target replicas = {target_replicas}")

else:
    # No valid DB record AND no payload replicas provided
    error_msg = (
        "No replicas specified in payload and no matching MongoDB stop record "
        "found to determine target replicas."
    )
    logger.error(error_msg)
    raise ValueError(error_msg)
