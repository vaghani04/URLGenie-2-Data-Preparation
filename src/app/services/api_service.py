import httpx
import asyncio
from fastapi import Depends, HTTPException, status
from typing import Tuple, Optional

from src.app.repositories.error_repository import ErrorRepo
from src.app.config.settings import settings


class ApiService:
    def __init__(self, error_repo: ErrorRepo = Depends(ErrorRepo)) -> None:
        self.timeout = httpx.Timeout(
            connect=30,  # Reduced connection timeout for faster failure detection
            read=120,   # Reduced read timeout - images should load faster
            write=60,   # Reduced write timeout
            pool=10,    # Much shorter pool wait - fail fast instead of waiting
        )
        # Connection limits optimized for high-concurrency batch processing
        # Scale with concurrent request limit for optimal performance
        self.limits = httpx.Limits(
            max_connections=settings.MAX_CONCURRENT_REQUESTS,
            max_keepalive_connections=min(100, settings.MAX_CONCURRENT_REQUESTS // 5),
        )
        # Semaphore to control concurrency and prevent pool exhaustion
        # Configurable via settings for optimal performance tuning
        self.concurrency_limit = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
        self.error_repo = error_repo

    def create_shared_client(self) -> httpx.AsyncClient:
        """Create a shared HTTP client with connection pooling for batch operations."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            limits=self.limits,
            follow_redirects=True
        )

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
    
    async def get_image_bytes_with_client(self, client: httpx.AsyncClient, url: str, max_retries: int = 2) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Get image bytes from URL using a shared HTTP client with concurrency control and retries.
        Returns tuple of (image_bytes, error_message). If successful, error_message is None.
        :param client: Shared HTTP client with connection pooling.
        :param url: The URL to fetch the image from.
        :param max_retries: Maximum number of retry attempts for pool timeouts.
        :return: Tuple of (image bytes or None, specific error message or None).
        """
        # Add proper headers to avoid being blocked by image hosts
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Use semaphore to limit concurrent connections and prevent pool exhaustion
                async with self.concurrency_limit:
                    response = await client.get(url, headers=headers, follow_redirects=True)
                    response.raise_for_status()
                    return response.content, None
                    
            except (httpx.PoolTimeout, httpx.ConnectTimeout) as exc:
                last_exception = exc
                if attempt < max_retries:
                    # Wait briefly before retry with exponential backoff
                    wait_time = 0.5 * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                # Final attempt failed - log and return error
                break
            except Exception as exc:
                # For non-timeout errors, don't retry
                last_exception = exc
                break
        
        # Handle the final exception
        if isinstance(last_exception, (httpx.PoolTimeout, httpx.ConnectTimeout)):
            error_msg = f"Connection pool timeout after {max_retries + 1} attempts: {str(last_exception)}"
            await self.error_repo.log_error(
                error=last_exception,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES_WITH_CLIENT",
                    "url": url,
                    "error_type": "pool_timeout",
                    "attempts": max_retries + 1,
                    "operation": "api_service.get_image_bytes_with_client",
                },
            )
            return None, error_msg
            
        elif isinstance(last_exception, httpx.HTTPStatusError):
            error_msg = f"HTTP {last_exception.response.status_code}: {last_exception.response.reason_phrase}"
            await self.error_repo.log_error(
                error=last_exception,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES_WITH_CLIENT",
                    "url": url,
                    "status_code": last_exception.response.status_code,
                    "error_type": "http_status",
                    "operation": "api_service.get_image_bytes_with_client",
                },
            )
            return None, error_msg
            
        elif isinstance(last_exception, httpx.RequestError):
            error_msg = f"Network error: {str(last_exception)}"
            await self.error_repo.log_error(
                error=last_exception,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES_WITH_CLIENT",
                    "url": url,
                    "error_type": "network",
                    "operation": "api_service.get_image_bytes_with_client",
                },
            )
            return None, error_msg
            
        else:
            error_msg = f"Unexpected error: {str(last_exception)}"
            await self.error_repo.log_error(
                error=last_exception,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES_WITH_CLIENT",
                    "url": url,
                    "error_type": "unexpected",
                    "operation": "api_service.get_image_bytes_with_client",
                },
            )
            return None, error_msg


    async def get_image_bytes(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Get image bytes from URL without raising HTTP exceptions (single request).
        For batch processing, prefer get_image_bytes_with_client() with shared client.
        Returns tuple of (image_bytes, error_message). If successful, error_message is None.
        :param url: The URL to fetch the image from.
        :return: Tuple of (image bytes or None, specific error message or None).
        """
        try:
            # Add proper headers to avoid being blocked by image hosts
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with httpx.AsyncClient(timeout=self.timeout, limits=self.limits) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                return response.content, None
                
        except httpx.TimeoutException as exc:
            error_msg = f"Request timeout: {str(exc)}"
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES",
                    "url": url,
                    "error_type": "timeout",
                    "operation": "api_service.get_image_bytes",
                },
            )
            return None, error_msg
            
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}"
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES",
                    "url": url,
                    "status_code": exc.response.status_code,
                    "error_type": "http_status",
                    "operation": "api_service.get_image_bytes",
                },
            )
            return None, error_msg
            
        except httpx.RequestError as exc:
            error_msg = f"Network error: {str(exc)}"
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES",
                    "url": url,
                    "error_type": "network",
                    "operation": "api_service.get_image_bytes",
                },
            )
            return None, error_msg
            
        except Exception as exc:
            error_msg = f"Unexpected error: {str(exc)}"
            await self.error_repo.log_error(
                error=exc,
                additional_context={
                    "file": "api_service.py",
                    "method": "GET_IMAGE_BYTES", 
                    "url": url,
                    "error_type": "unexpected",
                    "operation": "api_service.get_image_bytes",
                },
            )
            return None, error_msg