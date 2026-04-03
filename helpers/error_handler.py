def create_error_response(code, message, retryable=False, details=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "details": details
        }
    }