import pytest
from my_exceptions import (
    MongoError,
    DocumentNotFoundError,
    DuplicateKeyError,
    HttpClientError
)

# Test for MongoError
def test_mongo_error_initialization():
    """
    Covers: `MongoError.__init__`
    How: Instantiates the class, which calls `super().__init__`.
    """
    message = "A generic Mongo error"
    with pytest.raises(MongoError) as excinfo:
        raise MongoError(message)
    
    # Assert that the message was correctly passed to the parent Exception class
    assert str(excinfo.value) == message

# Test for DocumentNotFoundError (also confirms inheritance)
def test_document_not_found_error_is_a_mongo_error():
    """
    Covers: `DocumentNotFoundError` class definition.
    How: Ensures it can be raised and is an instance of its parent.
    """
    message = "Document 123 was not found"
    with pytest.raises(DocumentNotFoundError) as excinfo:
        raise DocumentNotFoundError(message)

    assert str(excinfo.value) == message
    # Verify that it correctly inherits from MongoError
    assert isinstance(excinfo.value, MongoError)

# Tests for DuplicateKeyError (requires two tests for __str__)
def test_duplicate_key_error_with_key_provided():
    """
    Covers: 
    1. `DuplicateKeyError.__init__` (including `self.duplicate_key` assignment)
    2. The `if self.duplicate_key` part of `__str__`
    """
    message = "E11000 duplicate key error"
    key = {"username": "testuser"}
    
    with pytest.raises(DuplicateKeyError) as excinfo:
        raise DuplicateKeyError(message, duplicate_key=key)

    # Assert that the custom attribute was set correctly
    assert excinfo.value.duplicate_key == key
    
    # Assert that the custom __str__ method works as expected
    expected_str = f"{message} (Duplicate Key: {key})"
    assert str(excinfo.value) == expected_str

def test_duplicate_key_error_without_key_provided():
    """
    Covers: The `else super().__str__()` part of `__str__`
    How: Instantiates the class without the optional `duplicate_key`.
    """
    message = "E11000 duplicate key error"
    
    with pytest.raises(DuplicateKeyError) as excinfo:
        # Call without the duplicate_key argument
        raise DuplicateKeyError(message)

    # Assert that the attribute is None as expected
    assert excinfo.value.duplicate_key is None
    
    # Assert that the __str__ method falls back to the default behavior
    assert str(excinfo.value) == message

# Test for HttpClientError
def test_http_client_error_initialization_with_all_args():
    """
    Covers: All lines in `HttpClientError.__init__`
    How: Instantiates the class with all optional arguments.
    """
    message = "Not Found"
    status = 404
    content = {"detail": "The requested resource does not exist."}
    
    with pytest.raises(HttpClientError) as excinfo:
        raise HttpClientError(message, status_code=status, response_content=content)

    # Assert that all attributes are set correctly
    assert excinfo.value.status_code == status
    assert excinfo.value.response_content == content
    assert str(excinfo.value) == message
