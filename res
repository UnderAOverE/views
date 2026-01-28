async def _stream_and_extract_ids(
    self, 
    stream, 
    field_name: str, 
    caller: str, 
    unique_ids: set[str]
) -> None:
    """
    Generic helper to iterate over async batches of Pydantic models.
    """
    batch_idx = 0
    try:
        async for batch in stream:
            batch_idx += 1
            try:
                for model in batch:
                    # Access the Pydantic field dynamically
                    value = getattr(model, field_name, None)

                    if isinstance(value, str):
                        # Split by comma, strip whitespace, and filter out empty strings
                        # update() adds multiple items to a set at once
                        unique_ids.update(
                            part.strip() for part in value.split(",") if part.strip()
                        )
                
                print(f"{caller} processed batch {batch_idx} ({len(batch)} docs)")
            
            except Exception as e:
                print(f"{caller} error in batch {batch_idx}: {e}")
                continue  # Keep going with next batch
    except Exception as e:
        print(f"{caller} critical streaming error: {e}")


async def extract_csi_inv_ci_names(self, service_names: list[str]) -> list[str] | None:
    unique_ids: set[str] = set()
    repo = self.drift_csi_inv_repository

    # We call the helper twice for the two different search types
    await self._stream_and_extract_ids(
        stream=repo.find_csi_by_service_name_regex(service_names),
        field_name="CSI",
        caller="csi_inv_by_name",
        unique_ids=unique_ids
    )

    await self._stream_and_extract_ids(
        stream=repo.find_csi_by_service_offering_name_regex(service_names),
        field_name="CSI",
        caller="csi_inv_by_offering",
        unique_ids=unique_ids
    )

    return list(unique_ids) if unique_ids else None


async def extract_cmdb_ci_names(self, device_names: list[str]) -> list[str] | None:
    unique_ids: set[str] = set()

    await self._stream_and_extract_ids(
        stream=self.drift_cmdb_repository.find_csi_by_device_names(device_names),
        field_name="ApplicationIds", # Different field name for this model
        caller="cmdb_ci_names",
        unique_ids=unique_ids
    )

    return list(unique_ids) if unique_ids else None
