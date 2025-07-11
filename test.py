import pytest
from unittest.mock import MagicMock, AsyncMock

# To make the example self-contained, we define dummy classes and exceptions
# that the service depends on. In a real scenario, you would import these.

class HttpClientConfig:
    def __init__(self, base_url, default_headers):
        pass

class AsyncHttpClient:
    def __init__(self, config):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def post(self, endpoint, json):
        pass

class HttpClientError(Exception):
    pass

# --- The class to be tested (copied from the user prompt) ---

# Assume DRAINSTATUS_API_CONFIGS is defined in the same module as the class
DRAINSTATUS_API_CONFIGS = {}

class DrainStatusAPIService:
    def __init__(self) -> None:
        self.http_client_config = HttpClientConfig(
            base_url=DRAINSTATUS_API_CONFIGS.get("base_url", "http://localhost"),
            default_headers=DRAINSTATUS_API_CONFIGS.get("swdc").get("headers"),
        )

    async def get_datacenter_status(self) -> tuple[bool, dict[str, str]]:
        get_status: dict[str, str] = {}
        final_status: bool = True

        async with AsyncHttpClient(self.http_client_config) as client:
            try:
                gtdc_response = await client.post(
                    endpoint=DRAINSTATUS_API_CONFIGS.get("gtdc").get("slug"),
                    json=DRAINSTATUS_API_CONFIGS.get("gtdc").get("body"),
                )
                swdc_response = await client.post(
                    endpoint=DRAINSTATUS_API_CONFIGS.get("swdc").get("slug"),
                    json=DRAINSTATUS_API_CONFIGS.get("gtdc").get("body"),
                )
                gtdc_response.raise_for_status()
                swdc_response.raise_for_status()

                if gtdc_response.status_code != 200:
                    get_status["gtdc"] = f"{gtdc_response.status_code}: {gtdc_response.reason}"
                    final_status = False

                if swdc_response.status_code != 200:
                    get_status["swdc"] = f"{swdc_response.status_code}: {swdc_response.reason}"
                    final_status = False

                get_status["gtdc"] = gtdc_response.json()[0].get("status", None)
                get_status["swdc"] = swdc_response.json()[0].get("status", None)

            except HttpClientError as http_client_error:
                get_status["gtdc"] = str(http_client_error)
                get_status["swdc"] = str(http_client_error)
                final_status = False

        return final_status, get_status


# --- Pytest Code Starts Here ---

# A fixture to provide a consistent mock configuration for all tests
@pytest.fixture
def mock_api_configs(mocker):
    """Mocks the DRAINSTATUS_API_CONFIGS global dictionary."""
    configs = {
        "base_url": "https://fake-api.com",
        "gtdc": {
            "slug": "/gtdc/status",
            "body": {"query": "gtdc"},
        },
        "swdc": {
            "slug": "/swdc/status",
            "headers": {"X-API-Key": "swdc-key"},
        },
    }
    # Use mocker to patch the dictionary in the context of the module where the class is defined
    mocker.patch(f"{__name__}.DRAINSTATUS_API_CONFIGS", configs)
    return configs

# A fixture to create mock HTTP responses
@pytest.fixture
def mock_response_factory():
    """Factory to create mock HTTP responses."""
    def _create_mock_response(
        status_code: int,
        reason: str,
        json_payload: list | None = None,
        raise_for_status_error: Exception | None = None
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.reason = reason
        
        if json_payload is not None:
            mock_resp.json.return_value = json_payload
        else:
            # If there's no payload, calling .json() should fail.
            # This is crucial for testing the non-200 status code path correctly.
            mock_resp.json.side_effect = ValueError("No JSON in response")
            
        if raise_for_status_error:
            mock_resp.raise_for_status.side_effect = raise_for_status_error
        else:
            mock_resp.raise_for_status.return_value = None
            
        return mock_resp

    return _create_mock_response


@pytest.mark.asyncio
async def test_get_datacenter_status_success(mocker, mock_api_configs, mock_response_factory):
    """
    Tests the happy path where both API calls return 200 OK.
    """
    # Arrange
    mock_async_http_client = mocker.patch(f"{__name__}.AsyncHttpClient")
    mocker.patch(f"{__name__}.HttpClientConfig") # Mock config class as well

    # Create mock client instance that the 'async with' will return
    mock_client_instance = AsyncMock()
    mock_async_http_client.return_value.__aenter__.return_value = mock_client_instance

    # Create successful responses for both datacenters
    gtdc_success_response = mock_response_factory(200, "OK", [{"status": "ACTIVE"}])
    swdc_success_response = mock_response_factory(200, "OK", [{"status": "DRAINED"}])

    # Configure the mock 'post' method to return responses in order
    mock_client_instance.post.side_effect = [gtdc_success_response, swdc_success_response]
    
    service = DrainStatusAPIService()

    # Act
    final_status, get_status = await service.get_datacenter_status()

    # Assert
    assert final_status is True
    assert get_status == {"gtdc": "ACTIVE", "swdc": "DRAINED"}

    # Verify that post was called twice with the correct arguments
    assert mock_client_instance.post.call_count == 2
    mock_client_instance.post.assert_any_call(
        endpoint=mock_api_configs["gtdc"]["slug"],
        json=mock_api_configs["gtdc"]["body"]
    )
    mock_client_instance.post.assert_any_call(
        endpoint=mock_api_configs["swdc"]["slug"],
        json=mock_api_configs["gtdc"]["body"] # Note: source code uses gtdc body for both
    )

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_dc",
    ["gtdc", "swdc"]
)
async def test_get_datacenter_status_one_dc_fails_non_200(
    mocker, mock_api_configs, mock_response_factory, failed_dc
):
    """
    Tests failure when one of the DCs returns a non-200 status code.
    This test also correctly covers the `if response.status_code != 200` block.
    """
    # Arrange
    mocker.patch(f"{__name__}.HttpClientConfig")
    mock_async_http_client = mocker.patch(f"{__name__}.AsyncHttpClient")
    mock_client_instance = AsyncMock()
    mock_async_http_client.return_value.__aenter__.return_value = mock_client_instance

    # Create one success and one failure response
    success_response = mock_response_factory(200, "OK", [{"status": "OK_STATUS"}])
    fail_response = mock_response_factory(500, "Internal Server Error", json_payload=None)

    # Set the side_effect based on which DC should fail
    if failed_dc == "gtdc":
        mock_client_instance.post.side_effect = [fail_response, success_response]
        expected_result = {
            "gtdc": "500: Internal Server Error",
            "swdc": "OK_STATUS"
        }
    else: # swdc fails
        mock_client_instance.post.side_effect = [success_response, fail_response]
        expected_result = {
            "gtdc": "OK_STATUS",
            "swdc": "500: Internal Server Error"
        }

    service = DrainStatusAPIService()

    # Act
    final_status, get_status = await service.get_datacenter_status()

    # Assert
    assert final_status is False
    assert get_status == expected_result
    # Check that raise_for_status was still called on both responses
    success_response.raise_for_status.assert_called_once()
    fail_response.raise_for_status.assert_called_once()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_source",
    ["on_post", "on_raise_for_status"]
)
async def test_get_datacenter_status_http_client_error(
    mocker, mock_api_configs, mock_response_factory, error_source
):
    """
    Tests the `except HttpClientError` block, triggered either by the post
    call itself or by response.raise_for_status().
    """
    # Arrange
    mocker.patch(f"{__name__}.HttpClientConfig")
    mock_async_http_client = mocker.patch(f"{__name__}.AsyncHttpClient")
    mock_client_instance = AsyncMock()
    mock_async_http_client.return_value.__aenter__.return_value = mock_client_instance
    
    # We must patch the exception in the module where it's *used*
    mocker.patch(f"{__name__}.HttpClientError", HttpClientError)
    
    error_message = "Connection timeout"
    http_error = HttpClientError(error_message)

    if error_source == "on_post":
        # The first call to `post` will raise the exception
        mock_client_instance.post.side_effect = http_error
    else: # on_raise_for_status
        # The post call succeeds, but raise_for_status() fails
        gtdc_fail_response = mock_response_factory(
            status_code=401,
            reason="Unauthorized",
            raise_for_status_error=http_error
        )
        mock_client_instance.post.return_value = gtdc_fail_response

    service = DrainStatusAPIService()

    # Act
    final_status, get_status = await service.get_datacenter_status()

    # Assert
    assert final_status is False
    assert get_status == {
        "gtdc": error_message,
        "swdc": error_message
    }
