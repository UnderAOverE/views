import httpx
from typing import Dict, Any, Optional, Union, List

# A semaphore to limit concurrent asynchronous requests
CONCURRENCY_LIMIT = 100
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

class RequestService:
    def __init__(self):
        """Initializes the RequestService. httpx handles session management internally."""
        pass
    
    def _prepare_request_args(
        self,
        headers: Optional[Dict[str, str]],
        bearer_token: Optional[str]
    ) -> Dict[str, Any]:
        """Prepares headers, including adding a bearer token."""
        if headers is None:
            headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        return {"headers": headers}

    def fetch_sync(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        bearer_token: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        timeout: int = 30,
        ssl: bool = True,
        proxies: Optional[str] = None,
        expected_status: int = 200,
        expected_content_type: Optional[str] = None
    ) -> Optional[Union[Dict, str]]:
        """
        Synchronously fetches a URL with configurable options.
        
        :param url: The URL to fetch.
        ... other params ...
        :return: The response data as a dict (for JSON) or str, or None on failure.
        """
        try:
            with httpx.Client(
                proxies=proxies,
                timeout=timeout,
                verify=ssl
            ) as client:
                print(f"Sync fetching {method} {url}")
                request_args = self._prepare_request_args(headers, bearer_token)
                
                response = client.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json,
                    **request_args
                )
                
                if response.status_code != expected_status:
                    print(f"Error: {url} returned status {response.status_code}, expected {expected_status}.")
                    return None
                    
                content_type = response.headers.get("Content-Type", "")
                if expected_content_type and expected_content_type not in content_type:
                    print(f"Error: {url} returned content type '{content_type}', expected '{expected_content_type}'.")
                    return None
                
                if "application/json" in content_type:
                    return response.json()
                else:
                    return response.text
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP error for {e.request.url}: {e}")
        except httpx.RequestError as e:
            print(f"An error occurred while requesting {e.request.url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        return None

    async def fetch_async(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        bearer_token: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        timeout: int = 30,
        ssl: bool = True,
        proxies: Optional[str] = None,
        expected_status: int = 200,
        expected_content_type: Optional[str] = None
    ) -> Optional[Union[Dict, str]]:
        """
        Asynchronously fetches a URL with configurable options.
        
        :param url: The URL to fetch.
        ... other params ...
        :return: The response data as a dict (for JSON) or str, or None on failure.
        """
        async with semaphore:
            try:
                async with httpx.AsyncClient(
                    proxies=proxies,
                    timeout=timeout,
                    verify=ssl
                ) as client:
                    print(f"Async fetching {method} {url}")
                    request_args = self._prepare_request_args(headers, bearer_token)
                    
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        data=data,
                        json=json,
                        **request_args
                    )
                    
                    if response.status_code != expected_status:
                        print(f"Error: {url} returned status {response.status_code}, expected {expected_status}.")
                        return None
                        
                    content_type = response.headers.get("Content-Type", "")
                    if expected_content_type and expected_content_type not in content_type:
                        print(f"Error: {url} returned content type '{content_type}', expected '{expected_content_type}'.")
                        return None
                    
                    if "application/json" in content_type:
                        return response.json()
                    else:
                        return response.text
            
            except httpx.HTTPStatusError as e:
                print(f"HTTP error for {e.request.url}: {e}")
            except httpx.RequestError as e:
                print(f"An error occurred while requesting {e.request.url}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
            return None

# ================================
# Example Usage
# ================================
async def main_async():
    service = RequestService()
    
    urls = [
        f"http://httpbin.org/status/200",
        f"http://httpbin.org/status/404",
        f"http://httpbin.org/json",
        f"http://httpbin.org/text"
    ]
    
    tasks = [
        service.fetch_async(urls[2], expected_content_type="application/json"),
        service.fetch_async(urls[3], expected_content_type="text/plain"),
        service.fetch_async(urls[1]),
        service.fetch_async(urls[0], expected_content_type="application/json")
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, res in enumerate(results):
        print(f"\nAsync result {i}: {res}")

def main_sync():
    service = RequestService()
    
    urls = [
        f"http://httpbin.org/status/200",
        f"http://httpbin.org/json",
        f"http://httpbin.org/text"
    ]
    
    # Note: No concurrency here, as it's a synchronous call
    res_json = service.fetch_sync(urls[1], expected_content_type="application/json")
    print(f"\nSync JSON result: {res_json['slideshow']['author']}")
    
    res_text = service.fetch_sync(urls[2], expected_content_type="text/plain")
    print(f"\nSync Text result: {res_text}")

if __name__ == "__main__":
    # You can choose to run either the sync or async example
    # For sync:
    # main_sync()
    
    # For async:
    asyncio.run(main_async())
