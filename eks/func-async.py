# --- Core Asynchronous Functions ---

async def funcE(
    item_data: Dict[str, Any],
    db_client: MockDatabaseClient,
    e_limiter: RateLimiter,
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    task_id = f"E-{item_data.get('id', 'unknown')}"
    logger.debug(f"[{task_id}] Starting funcE...")
    try:
        async with e_limiter:
            success = await run_with_timeout_and_retries(
                db_client.save(item_data, timeout=TIMEOUT_E),
                timeout=TIMEOUT_E,
                retries=2,
                task_name=task_id,
                logger=logger
            )
            if success:
                logger.info(f"[{task_id}] Successfully saved final data.")
                return {"status": "saved", "item_id": item_data.get('id')}
            else:
                logger.error(f"[{task_id}] Failed to save data after retries.")
                return {"status": "failed_save", "item_id": item_data.get('id')}
    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"[{task_id}] funcE failed: {type(e).__name__} - {e}")
        return {"status": "error_e", "item_id": item_data.get('id'), "error": str(e)}


async def funcD(
    details: Dict[str, Any],
    http_client: MockHttpClient,
    d_limiter: RateLimiter,
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    task_id = f"D-{details.get('sub_id', 'unknown')}"
    logger.debug(f"[{task_id}] Starting funcD...")
    try:
        async with d_limiter:
            api_url = f"https://api.example.com/external/{details['data']['value']}"
            api_response = await run_with_timeout_and_retries(
                http_client.get(api_url, timeout=TIMEOUT_D),
                timeout=TIMEOUT_D,
                retries=3,
                task_name=task_id,
                logger=logger
            )
            logger.info(f"[{task_id}] Fetched external data for {details['sub_id']}: {api_response['data']['value']}")
            return {"id": details['sub_id'], "external_data": api_response['data']}
    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"[{task_id}] funcD failed: {type(e).__name__} - {e}")
        return {"status": "error_d", "sub_id": details.get('sub_id'), "error": str(e)}


async def funcC(
    sub_id: str,
    http_client: MockHttpClient,
    db_client: MockDatabaseClient, # Pass down for funcE
    c_limiter: RateLimiter,
    d_limiter: RateLimiter, # Pass down for funcD
    e_limiter: RateLimiter, # Pass down for funcE
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    task_id = f"C-{sub_id}"
    logger.debug(f"[{task_id}] Starting funcC...")
    try:
        async with c_limiter:
            details_url = f"https://api.example.com/details/{sub_id}"
            details_response = await run_with_timeout_and_retries(
                http_client.get(details_url, timeout=TIMEOUT_C),
                timeout=TIMEOUT_C,
                retries=3,
                task_name=task_id,
                logger=logger
            )
            logger.info(f"[{task_id}] Got details for {sub_id}")

            # Call funcD
            d_result = await funcD(details_response, http_client, d_limiter, logger)
            if d_result and d_result.get('status') != 'error_d':
                final_data = {**details_response, **d_result} # Merge data
                # Call funcE
                e_result = await funcE(final_data, db_client, e_limiter, logger)
                return {"status": "processed", "id": sub_id, "final_e_result": e_result}
            else:
                logger.warning(f"[{task_id}] funcD failed for {sub_id}, skipping funcE.")
                return {"status": "failed_d_propagate", "id": sub_id, "error": d_result.get('error')}

    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"[{task_id}] funcC failed: {type(e).__name__} - {e}")
        return {"status": "error_c", "id": sub_id, "error": str(e)}


async def funcB(
    main_id: int,
    sub_id_data: str, # e.g., "1-alpha"
    http_client: MockHttpClient,
    db_client: MockDatabaseClient,
    b_limiter: RateLimiter,
    c_limiter: RateLimiter,
    d_limiter: RateLimiter,
    e_limiter: RateLimiter,
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    task_id = f"B-{main_id}-{sub_id_data}"
    logger.debug(f"[{task_id}] Starting funcB...")
    results_c = []
    try:
        async with b_limiter:
            # Simulate some processing to get actual sub_ids
            await asyncio.sleep(random.uniform(0.05, 0.2))
            actual_sub_ids = [f"{sub_id_data}-{i}" for i in range(random.randint(1, 2))]
            logger.info(f"[{task_id}] Retrieved {len(actual_sub_ids)} actual sub-IDs for {sub_id_data}")

            # Concurrently call funcC for each actual_sub_id using TaskGroup
            async with asyncio.TaskGroup() as tg:
                for s_id in actual_sub_ids:
                    task = tg.create_task(
                        funcC(s_id, http_client, db_client, c_limiter, d_limiter, e_limiter, logger),
                        name=f"funcC_task_{s_id}"
                    )
                    results_c.append(task)
            # After TaskGroup, all tasks are done or an exception has propagated
            # We can now collect results, which are futures that have resolved
            collected_c_results = [t.result() for t in results_c]
            logger.info(f"[{task_id}] All funcC tasks completed for {sub_id_data}. Results: {len(collected_c_results)}")
            return {"status": "processed", "main_id": main_id, "sub_id": sub_id_data, "c_results": collected_c_results}

    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"[{task_id}] funcB failed: {type(e).__name__} - {e}")
        # Return a structured error result
        return {"status": "error_b", "main_id": main_id, "sub_id": sub_id_data, "error": str(e)}


async def funcA(
    initial_id: int,
    http_client: MockHttpClient,
    db_client: MockDatabaseClient,
    a_limiter: RateLimiter,
    b_limiter: RateLimiter,
    c_limiter: RateLimiter,
    d_limiter: RateLimiter,
    e_limiter: RateLimiter,
    logger: logging.Logger
) -> Optional[Dict[str, Any]]:
    task_id = f"A-{initial_id}"
    logger.debug(f"[{task_id}] Starting funcA...")
    results_b = []
    try:
        async with a_limiter:
            # Simulate fetching initial data
            fetch_url = f"https://api.example.com/initial/{initial_id}"
            initial_data = await run_with_timeout_and_retries(
                http_client.get(fetch_url, timeout=TIMEOUT_A),
                timeout=TIMEOUT_A,
                retries=3,
                task_name=task_id,
                logger=logger
            )
            sub_item_names = [f"{initial_id}-{chr(97+i)}" for i in range(random.randint(2, 4))]
            logger.info(f"[{task_id}] Fetched initial data for {initial_id}. Sub-items: {sub_item_names}")

            # Concurrently call funcB for each sub-item using TaskGroup
            async with asyncio.TaskGroup() as tg:
                for sub_name in sub_item_names:
                    task = tg.create_task(
                        funcB(initial_id, sub_name, http_client, db_client,
                              b_limiter, c_limiter, d_limiter, e_limiter, logger),
                        name=f"funcB_task_{initial_id}_{sub_name}"
                    )
                    results_b.append(task)
            # After TaskGroup, all tasks are done or an exception has propagated
            collected_b_results = [t.result() for t in results_b]
            logger.info(f"[{task_id}] All funcB tasks completed for {initial_id}. Results: {len(collected_b_results)}")
            return {"status": "completed", "id": initial_id, "b_results": collected_b_results}

    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"[{task_id}] funcA failed: {type(e).__name__} - {e}")
        return {"status": "error_a", "id": initial_id, "error": str(e)}
