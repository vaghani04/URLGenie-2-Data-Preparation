import httpx
from fastapi import Depends, HTTPException, status

from src.app.repositories.error_repository import ErrorRepo


class ApiService:
    def __init__(self, error_repo: ErrorRepo = Depends(ErrorRepo)) -> None:
        self.timeout = httpx.Timeout(
            connect=120,  # Time to establish a connection
            read=240,  # Time to read the response
            write=240,  # Time to send data 
            pool=120,  # Time to wait for a connection from the pool
        )
        self.error_repo = error_repo

    async def get(
        self, url: str, headers: dict = None, data: dict = None
    ) -> httpx.Response:
        """
        Sends an asynchronous GET request with a timeout.
        :param url: The URL to send the request to.
        :param headers: Optional HTTP headers.
        :param data: Optional query parameters.
        :return: The HTTP response.
        """
        try:

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=data)
                response.raise_for_status()
                try:
                    return response.json()
                except:
                    return response.text
        except httpx.RequestError as exc:
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET",
                    "url": str(exc.request.url),
                    "operation": "api_service.get",
                },
            )
            error_msg = (
                f"An error occurred while requesting {exc.request.url!r}."
            )
            raise HTTPException(status_code=500, detail=error_msg)
        except httpx.HTTPStatusError as exc:
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET",
                    "url": str(exc.request.url),
                    "status_code": exc.response.status_code,
                    "response_text": (
                        exc.response.text
                        if hasattr(exc.response, "text")
                        else None
                    ),
                    "operation": "api_service.get",
                },
            )
            error_msg = f"Error response {exc.response.status_code} while requesting {exc.request.url!r}."
            raise HTTPException(
                status_code=exc.response.status_code, detail=error_msg
            )

    async def post(
        self,
        url: str,
        headers: dict = None,
        data: dict = None,
        files: dict = None,
    ) -> httpx.Response:
        """
        Sends an asynchronous POST request with a timeout.
        :param url: The URL to send the request to.
        :param headers: Optional HTTP headers.
        :param data: The payload to send in JSON format.
        :return: The HTTP response.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, verify=False
            ) as client:
                if files:
                    response = await client.post(
                        url, headers=headers, data=data, files=files
                    )
                else:
                    response = await client.post(
                        url, headers=headers, json=data
                    )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as exc:
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "POST",
                    "url": str(exc.request.url),
                    "operation": "api_service.post",
                },
            )
            error_msg = (
                f"An error occurred while requesting {exc.request.url!r}."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg,
            )
        except httpx.HTTPStatusError as exc:
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "POST",
                    "url": str(exc.request.url),
                    "status_code": exc.response.status_code,
                    "response_text": (
                        exc.response.text
                        if hasattr(exc.response, "text")
                        else None
                    ),
                    "operation": "api_service.post",
                },
            )
            error_msg = f"Error response {exc.response.status_code} while requesting {exc.request.url!r}."

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg,
            )
        except Exception as exc:
            error_msg = f"Error has occurred in api_service.post: {str(exc)}"
            await self.error_repo.log_error(
                error=error_msg,
                additional_context={
                    "file": "api_service.py",
                    "method": "POST",
                    "url": url,
                    "operation": "api_service.post",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg,
            )
