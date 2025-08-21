from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
import logging

# Example logger setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

completed_business_transactions = 0

# Define batch settings somewhere above
# batch_name, batch_environment, batch_sector, batch_region, batch_number, batch_interval = ...

with ProcessPoolExecutor(max_workers=concurrent_calls) as executor:
    futures_list = {
        executor.submit(
            execute_aternity_query,
            metadata_entry,
            batch_name,
            batch_environment,
            batch_sector,
            batch_region,
            batch_number
        ): metadata_entry
        for metadata_entry in metadata_entries
    }

    for future in as_completed(futures_list):
        args = futures_list[future]
        try:
            result = future.result(timeout=batch_interval * 30)
            logger.info(
                f"[program_name] execute_aternity_query() completed "
                f"for metadata={args} with result={result}!"
            )
            completed_business_transactions += 1
        except TimeoutError as timeout_error:
            logger.error(
                f"[program_name] execute_aternity_query() timed out "
                f"for metadata={args} with error={timeout_error}, "
                f"did not complete within {batch_interval * 30} seconds"
            )
        except Exception as future_error:
            logger.error(
                f"[program_name] execute_aternity_query() failed "
                f"for metadata={args} with error={future_error}"
            )
