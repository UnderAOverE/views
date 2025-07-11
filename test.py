import pytest
from unittest.mock import MagicMock, AsyncMock

# You need to import the class you are testing
# from path.to.your.service_module import DrainStatusAPIService, HttpClientError

# For this example to be self-running, I'll define dummy versions here.
# In your code, you would delete these and use your real imports.
class HttpClientConfig: pass
class HttpClientError(Exception): pass
DRAINSTATUS_API_CONFIGS = {}
class AsyncHttpClient:
    async def __aenter__(self): return self
    async def __aexit__(self, t, v, tb): pass
    async def post(self, **kwargs): pass
class DrainStatusAPIService:
    def __init__(self) -> None:
        self.http_client_config = HttpClientConfig() # Simplified for example
    async def get_datacenter_status(self) -> tuple[bool, dict[str, str]]:
        # The user's code is assumed to be here
        pass # The rest of the original code goes here...


# --- The Actual Pytest Code ---

# IMPORTANT: Replace this with the real path to your file.
# e.g., if your file is at `src/my_app/drain_service.py`,
# the module path is `src.my_app.drain_service`.
MODULE_PATH = "path.to.your.service_module"


@pytest.mark.asyncio
async def test_get_datacenter_status_success(mocker):
    """
    Tests the "happy path" where both API calls succeed with 200 status.
    """
    # 1. Arrange: Mock all external dependencies
    mock_configs = {
        "gtdc": {"slug": "/gtdc", "body": {"q": "gtdc"}},
        "swdc": {"slug": "/swdc", "headers": {}},
    }
    mocker.patch(f"{MODULE_PATH}.DRAINSTATUS_API_CONFIGS", mock_configs)
    mocker.patch(f"{MODULE_PATH}.HttpClientConfig")
    
    # Mock the AsyncHttpClient class and its context manager
    mock_async_http_client_class = mocker.patch(f"{MODULE_PATH}.AsyncHttpClient")
    mock_client_instance = AsyncMock()
    mock_async_http_client_class.return_value.__aenter__.return_value = mock_client_instance

    # Create two successful mock responses
    mock_gtdc_response = MagicMock(status_code=200, reason="OK")
    mock_gtdc_response.json.return_value = [{"status": "ACTIVE"}]
    
    mock_swdc_response = MagicMock(status_code=200, reason="OK")
    mock_swdc_response.json.return_value = [{"status": "DRAINED"}]

    # Configure the mock client's `post` method to return our responses in order
    mock_client_instance.post.side_effect = [mock_gtdc_response, mock_swdc_response]

    # Import the class *after* mocks are in place and instantiate it
    from your_module.your_file import DrainStatusAPIService
    service = DrainStatusAPIService()

    # 2. Act: Call the method
    final_status, get_status = await service.get_datacenter_status()

    # 3. Assert: Check the results
    assert final_status is True
    assert get_status == {"gtdc": "ACTIVE", "swdc": "DRAINED"}
    assert mock_client_instance.post.call_count == 2
    mock_gtdc_response.raise_for_status.assert_called_once()
    mock_swdc_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_datacenter_status_with_http_client_error(mocker):
    """
    Tests the `except HttpClientError` block when the client fails.
    """
    # 1. Arrange: Mock dependencies
    mocker.patch(f"{MODULE_PATH}.DRAINSTATUS_API_CONFIGS", {"gtdc": {}, "swdc": {}})
    mocker.patch(f"{MODULE_PATH}.HttpClientConfig")
    
    # IMPORTANT: We patch the exception in the module where it is `caught`.
    mocker.patch(f"{MODULE_PATH}.HttpClientError", new=HttpClientError)

    mock_async_http_client_class = mocker.patch(f"{MODULE_PATH}.AsyncHttpClient")
    mock_client_instance = AsyncMock()
    mock_async_http_client_class.return_value.__aenter__.return_value = mock_client_instance
    
    # Configure the `post` method to raise an error
    error_message = "Connection Failed"
    mock_client_instance.post.side_effect = HttpClientError(error_message)

    from your_module.your_file import DrainStatusAPIService
    service = DrainStatusAPIService()

    # 2. Act
    final_status, get_status = await service.get_datacenter_status()

    # 3. Assert
    assert final_status is False
    assert get_status == {"gtdc": error_message, "swdc": error_message}
    # Ensure we failed on the first call and never made the second one
    mock_client_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_get_datacenter_status_with_non_200_response(mocker):
    """
    Tests the logic for handling a non-200 status code from an API.
    """
    # 1. Arrange
    mocker.patch(f"{MODULE_PATH}.DRAINSTATUS_API_CONFIGS", {"gtdc": {}, "swdc": {}})
    mocker.patch(f"{MODULE_PATH}.HttpClientConfig")
    
    mock_async_http_client_class = mocker.patch(f"{MODULE_PATH}.AsyncHttpClient")
    mock_client_instance = AsyncMock()
    mock_async_http_client_class.return_value.__aenter__.return_value = mock_client_instance

    # Create one successful response and one failed response
    mock_gtdc_response = MagicMock(status_code=200, reason="OK")
    mock_gtdc_response.json.return_value = [{"status": "ACTIVE"}]
    
    mock_swdc_response = MagicMock(status_code=500, reason="Internal Server Error")
    # This next line is key to covering all lines: the code tries to call .json()
    # even on a failed response. We mock it to return an empty dict.
    mock_swdc_response.json.return_value = [{}] # No "status" key

    mock_client_instance.post.side_effect = [mock_gtdc_response, mock_swdc_response]
    
    from your_module.your_file import DrainStatusAPIService
    service = DrainStatusAPIService()

    # 2. Act
    final_status, get_status = await service.get_datacenter_status()

    # 3. Assert
    assert final_status is False
    # The code sets the error message, but then overwrites it with the .json() result
    assert get_status == {"gtdc": "ACTIVE", "swdc": None} 
    mock_gtdc_response.raise_for_status.assert_called_once()
    mock_swdc_response.raise_for_status.assert_called_once()
