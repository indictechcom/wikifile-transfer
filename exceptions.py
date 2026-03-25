from flask import jsonify
# error object which will be returned on failure of any operation, it will have a code, message and optional details

def error_object(code, message, details=None):
    payload = {
        "code": code,
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return payload


def validation_error(details=None):
    return error_object("VALIDATION_ERROR", "Invalid request data", details)


def download_error(details=None):
    return error_object("DOWNLOAD_ERROR", "Failed to download source file", details)


def file_handling_error(details=None):
    return error_object("FILE_HANDLING_ERROR", "File handling failed", details)


def upload_error(details=None):
    return error_object("UPLOAD_ERROR", "Upload failed", details)


def authentication_error(details=None):
    return error_object("AUTH_ERROR", "Authentication required", details)


def database_error(details=None):
    return error_object("DATABASE_ERROR", "Database operation failed", details)


def external_service_error(details=None):
    return error_object("EXTERNAL_SERVICE_ERROR", "External service error", details)


def success_response(data=None, status_code=200):
    return jsonify({
        "success": True,
        "data": data if data is not None else {},
        "errors": []
    }), status_code


def error_response(code, message, status_code=500, details=None):
    return jsonify({
        "success": False,
        "data": {},
        "errors": [error_object(code, message, details)]
    }), status_code


def error_response_from_error(error, status_code=500):
    code = error.get("code", "INTERNAL_SERVER_ERROR")
    message = error.get("message", "Unexpected error")
    details = error.get("details")
    return error_response(code, message, status_code=status_code, details=details)


def operation_success(data=None):
    return {
        "ok": True,
        "data": data if data is not None else {},
        "error": None
    }


def operation_failure(error):
    return {
        "ok": False,
        "data": {},
        "error": error
    }