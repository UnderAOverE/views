class MongoError(Exception):
    def __init__(self, message):
        super().__init__(message)  # <------------------ not covered

class DocumentNotFoundError(MongoError):
    pass

class DuplicateKeyError(MongoError):
    def __init__(self, message, duplicate_key=None):
        super().__init__(message)  # <------------------ not covered
        self.duplicate_key = duplicate_key  # <------------------ not covered

    def __str__(self):
        return f"{super().__str__()} (Duplicate Key: {self.duplicate_key})" if self.duplicate_key else super().__str__()  # <------------------ not covered

class HttpClientError(Exception):
    def __init__(self, message, status_code=None, response_content=None):
        super().__init__(message)  # <------------------ not covered
        self.status_code = status_code  # <------------------ not covered
        self.response_content = response_content  # <------------------ not covered
