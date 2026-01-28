async def extract_csi_inv_ci_names(self, service_names: list[str,]) -> list[str,] | None:

    unique_application_ids: set[str] = set()
    total_processed = 0
    batch_count = 0

    try:
        async for batch in self.drift_csi_inv_repository.find_csi_by_service_name_regex(
            service_names=service_names,
        ):
            batch_count += 1
            batch_size = len(batch)

            try:
                for document in batch:
                    if hasattr(document, "CSI") and document.ApplicationIds:
                        application_ids = document.ApplicationIds
                        if isinstance(application_ids, str) and application_ids.strip():
                            individual_ids = application_ids.split(",")
                            for single_id in individual_ids:
                                stripped_id = single_id.strip()
                                if stripped_id:
                                    unique_application_ids.add(stripped_id)

                total_processed += batch_size
                logger.debug(
                    f"extract_csi_inv_ci_names processed batch {batch_count} "
                    f"with {batch_size} documents"
                )

            except Exception as batch_error:
                print(
                    f"extract_csi_inv_ci_names error processing batch "
                    f"{batch_count}: {batch_error}"
                )
                # Continue with next batch instead of failing completely
                continue

        # endAsyncFor

    # endTryExcept