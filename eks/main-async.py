# --- Main Orchestration ---

async def main():
    # 1. Initialize Dependencies
    http_client = MockHttpClient(logger=logging.getLogger("HttpClient"))
    db_client = MockDatabaseClient(logger=logging.getLogger("DatabaseClient"))

    # 2. Initialize Rate Limiters (Semaphores)
    a_limiter = RateLimiter(MAX_CONCURRENT_A, "FuncA_Limiter")
    b_limiter = RateLimiter(MAX_CONCURRENT_B, "FuncB_Limiter")
    c_limiter = RateLimiter(MAX_CONCURRENT_C, "FuncC_Limiter")
    d_limiter = RateLimiter(MAX_CONCURRENT_D, "FuncD_Limiter")
    e_limiter = RateLimiter(MAX_CONCURRENT_E, "FuncE_Limiter")

    # 3. Define initial tasks to process
    initial_item_ids = list(range(10)) # Process 10 initial items

    all_results = []
    start_time = time.time()
    logger.info(f"Starting main processing for {len(initial_item_ids)} items.")

    # 4. Use TaskGroup for the top-level funcA calls
    try:
        async with asyncio.TaskGroup() as tg:
            for item_id in initial_item_ids:
                task = tg.create_task(
                    funcA(item_id, http_client, db_client,
                          a_limiter, b_limiter, c_limiter, d_limiter, e_limiter, logger),
                    name=f"funcA_task_{item_id}"
                )
                all_results.append(task)

        # All tasks in the TaskGroup have completed or one has failed and been propagated
        final_processed_results = [t.result() for t in all_results]
        successful_tasks = [res for res in final_processed_results if res and res.get('status') == 'completed']
        failed_tasks = [res for res in final_processed_results if res and res.get('status') != 'completed']

        logger.info(f"\n--- Processing Summary ---")
        logger.info(f"Total initial items: {len(initial_item_ids)}")
        logger.info(f"Successfully processed: {len(successful_tasks)}")
        logger.info(f"Failed or partially failed: {len(failed_tasks)}")
        logger.info(f"Total time taken: {time.time() - start_time:.2f} seconds.")

        # Optional: Print out failed results for inspection
        if failed_tasks:
            logger.warning("Details of failed tasks:")
            for fail in failed_tasks:
                logger.warning(f"  {fail.get('id', 'N/A')}: Status: {fail.get('status')}, Error: {fail.get('error', 'N/A')}")

    except Exception as e:
        logger.critical(f"Main TaskGroup encountered an unhandled exception: {type(e).__name__} - {e}", exc_info=True)
        logger.info(f"Main processing halted. Total time taken: {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    # To see more debug output, change logging level to DEBUG
    # logger.setLevel(logging.DEBUG)
    asyncio.run(main())
