"""API error type rendered as {code, message, request_id, details}."""

from fastapi import HTTPException


CODES = {
    400: "VALIDATION",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION",
    503: "UNAVAILABLE",
}


class ApiError(HTTPException):
    def __init__(self, status_code, message, details=None, code=None):
        super().__init__(status_code, message)
        self.code = code or CODES.get(status_code, "ERROR")
        self.details = details or {}
