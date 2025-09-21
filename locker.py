import asyncio
import aiohttp
import time

# A semaphore to limit concurrent requests
CONCURRENCY_LIMIT = 100
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def fetch_url(url):
    # Acquire a slot before starting the request
    async with semaphore:
        async with aiohttp.ClientSession() as session:
            try:
                print(f"Fetching {url}")
                async with session.get(url) as response:
                    # Do something with the response
                    await response.text()
                    print(f"Done with {url}")
            except Exception as e:
                print(f"Error fetching {url}: {e}")

async def main():
    # Example: A list of thousands of URLs
    urls = [f"http://httpbin.org/delay/{i % 5}" for i in range(2000)]
    
    # Create a list of tasks
    tasks = [fetch_url(url) for url in urls]
    
    start_time = time.monotonic()
    
    # Run all tasks, with concurrency limited by the semaphore
    await asyncio.gather(*tasks)
    
    end_time = time.monotonic()
    print(f"All tasks completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(main())

