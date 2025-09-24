import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional, Union

class RequestService:
    def __init__(self, concurrency_limit: int = 100):
        """
        Initializes the RequestService with a concurrency limit.
        
        :param concurrency_limit: The maximum number of concurrent requests.
        """
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.session = None

    async def __aenter__(self):
        """
        A context manager method to be used with 'async with'.
        Initializes the aiohttp.ClientSession.
        """
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        A context manager method to close the aiohttp.ClientSession.
        """
        await self.session.close()

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        bearer_token: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Any] = None,
        timeout: int = 30,
        ssl: bool = True,
        proxies: Optional[str] = None,
        expected_status: int = 200,
        expected_content_type: Optional[str] = None
    ) -> Optional[Union[Dict, str]]:
        """
        Fetches a URL with configurable options and validates the response.
        
        :param url: The URL to fetch.
        :param method: The HTTP method (e.g., 'GET', 'POST').
        :param headers: A dictionary of headers.
        :param bearer_token: A Bearer token for authorization.
        :param params: A dictionary of query parameters.
        :param data: Request body for POST/PUT.
        :param json_data: JSON data for the request body.
        :param timeout: Request timeout in seconds.
        :param ssl: Whether to perform SSL verification.
        :param proxies: The proxy URL.
        :param expected_status: The expected HTTP status code. Defaults to 200.
        :param expected_content_type: The expected Content-Type header.
        :return: The response data as a dict (for JSON) or str, or None on failure.
        """
        async with self.semaphore:
            if not self.session:
                raise RuntimeError("ClientSession not initialized. Use 'async with RequestService(...)'.")
            
            if bearer_token:
                if headers is None:
                    headers = {}
                headers["Authorization"] = f"Bearer {bearer_token}"

            try:
                print(f"Fetching {method} {url}")
                async with self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json_data,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=ssl,
                    proxy=proxies
                ) as response:
                    # Validate the status code
                    if response.status != expected_status:
                        print(f"Error: {url} returned status {response.status}, expected {expected_status}.")
                        return None
                    
                    # Validate the content type
                    content_type = response.headers.get("Content-Type", "")
                    if expected_content_type and expected_content_type not in content_type:
                        print(f"Error: {url} returned content type '{content_type}', expected '{expected_content_type}'.")
                        return None

                    # Return data based on content type
                    if "application/json" in content_type:
                        return await response.json()
                    else:
                        return await response.text()
            
            except aiohttp.ClientError as e:
                print(f"aiohttp error fetching {url}: {e}")
            except asyncio.TimeoutError:
                print(f"Request to {url} timed out after {timeout} seconds.")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
            
            return None

async def main():
    # Example usage of the RequestService class
    urls = [f"http://httpbin.org/status/200",
            f"http://httpbin.org/status/404",
            f"http://httpbin.org/json",
            f"http://httpbin.org/text"]

    start_time = time.monotonic()
    
    async with RequestService(concurrency_limit=5) as service:
        tasks = [
            # Successful JSON request, default status 200 is fine
            service.fetch(urls[2], expected_content_type="application/json"),
            
            # Successful text request, with explicit status and content type
            service.fetch(urls[3], expected_content_type="text/plain"),
            
            # Request that will fail due to 404 status
            service.fetch(urls[1]),
            
            # Request that will fail due to content type mismatch
            service.fetch(urls[0], expected_content_type="application/json")
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
    end_time = time.monotonic()
    print(f"\nAll tasks completed in {end_time - start_time:.2f} seconds.")

    # Process the responses
    for i, res in enumerate(responses):
        print(f"\nResult for task {i}:")
        if res is None:
            print("Request failed or validation check failed.")
        elif isinstance(res, dict):
            print(f"Received JSON data: {res['slideshow']['author']}")
        elif isinstance(res, str):
            print(f"Received text data: {res}")
        else:
            print(f"Task failed with an exception: {res}")

if __name__ == "__main__":
    asyncio.run(main())
