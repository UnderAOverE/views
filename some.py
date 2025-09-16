import httpx
import asyncio
import json # For pretty printing JSON responses

async def make_httpx_request(
    method: str,
    url: str,
    proxy_url: str = None,
    headers: dict = None,
    data: dict = None, # For POST requests
    params: dict = None, # For GET requests
    ssl_verify: bool = True # Control SSL verification
):
    """
    Performs an asynchronous HTTP request (GET or POST) using httpx.
    Includes proxy, custom headers, and error handling.
    """
    print(f"\n--- Making {method.upper()} request to {url} ---")
    print(f"  Proxy: {proxy_url if proxy_url else 'None'}")
    print(f"  Headers: {headers}")
    if data:
        print(f"  Data: {data}")
    if params:
        print(f"  Params: {params}")
    print(f"  SSL Verify: {ssl_verify}")


    # Configure httpx client
    # The 'proxies' argument can be a dict or a string.
    # If a string, it applies to both http and https.
    # For more granular control: proxies={"http://": "http://proxy.example.com", "https://": "https://proxy.example.com"}
    client_config = {
        "proxies": proxy_url,
        "verify": ssl_verify # Controls SSL certificate verification
    }

    async with httpx.AsyncClient(**client_config) as client:
        try:
            if method.lower() == "get":
                response = await client.get(url, headers=headers, params=params)
            elif method.lower() == "post":
                response = await client.post(url, headers=headers, json=data) # Use 'json' for dicts, 'data' for form-encoded
            else:
                print(f"Unsupported method: {method}")
                return

            response.raise_for_status()  # Raise an exception for 4xx/5xx responses

            print(f"Status Code: {response.status_code}")
            print(f"Headers: {response.headers}")

            # Try to parse as JSON if possible, otherwise print text
            try:
                print("Response Body (JSON):")
                print(json.dumps(response.json(), indent=2))
            except json.JSONDecodeError:
                print("Response Body (Text):")
                print(response.text[:500] + "..." if len(response.text) > 500 else response.text)

            return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text

        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
        except httpx.HTTPStatusError as exc:
            print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
        except Exception as e:
            print(f"An unexpected error occurred: {type(e).__name__}: {e}")

async def main():
    # --- Configuration ---
    # Replace with your actual proxy.
    # For HTTP proxy: "http://user:pass@host:port"
    # For SOCKS5 proxy: "socks5://user:pass@host:port" (requires 'python-socks' library: pip install python-socks)
    PROXY_URL = "http://your.proxy.server:8080" # Example, replace if needed
    # PROXY_URL = None # Uncomment to test without a proxy

    # --- Test GET Request ---
    print("===== GET Request =====")
    get_url = "https://httpbin.org/get" # A simple echo service for GET requests
    get_headers = {
        "User-Agent": "MyCustomAsyncApp/1.0",
        "Accept": "application/json"
    }
    get_params = {
        "query_param_1": "value1",
        "query_param_2": "value2"
    }

    await make_httpx_request(
        method="GET",
        url=get_url,
        proxy_url=PROXY_URL,
        headers=get_headers,
        params=get_params,
        ssl_verify=False # Set to True in production if your proxy/certs are fine
    )

    # --- Test POST Request ---
    print("\n===== POST Request =====")
    post_url = "https://httpbin.org/post" # A simple echo service for POST requests
    post_headers = {
        "Content-Type": "application/json",
        "X-Request-ID": "abcdef12345"
    }
    post_data = {
        "name": "Async User",
        "age": 30,
        "is_active": True
    }

    await make_httpx_request(
        method="POST",
        url=post_url,
        proxy_url=PROXY_URL,
        headers=post_headers,
        data=post_data,
        ssl_verify=False # Set to True in production
    )

    # --- Test a failure scenario (e.g., 404 Not Found) ---
    print("\n===== Failure Scenario (404) =====")
    await make_httpx_request(
        method="GET",
        url="https://httpbin.org/status/404",
        proxy_url=PROXY_URL,
        ssl_verify=False
    )

if __name__ == "__main__":
    asyncio.run(main())
