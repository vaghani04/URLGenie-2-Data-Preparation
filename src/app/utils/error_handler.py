from functools import wraps

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from src.app.repositories.error_repository import error_repo


def handle_exceptions(func):
    """A decorator to catch exceptions and return a consistent JSON error response with proper error logging."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            # If it's already a response, don't wrap it again
            if isinstance(e, HTTPException):
                raise e

            # Log the error with context using ErrorRepo
            try:
                error_id = await error_repo.log_error(
                    e,
                    {
                        "function_name": func.__name__,
                        "module": func.__module__,
                        "operation": "route_handler",
                    },
                )

                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "data": {},
                        "statuscode": 500,
                        "detail": "An internal server error occurred.",
                        "error": str(e),
                        "error_id": error_id,
                    },
                )
            except Exception as log_error:
                # Fallback if error logging fails
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "data": {},
                        "statuscode": 500,
                        "detail": "An internal server error occurred.",
                        "error": str(e),
                        "error_id": None,
                    },
                )

    return wrapper
