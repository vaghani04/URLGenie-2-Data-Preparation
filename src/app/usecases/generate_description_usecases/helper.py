from src.app.models.schemas.desc_gen_schemas import QueryRequest
from PIL import Image
from io import BytesIO
from src.app.config.settings import settings
from datetime import datetime
from src.app.services.api_service import ApiService
from fastapi import Depends
import json
import os
from typing import Optional

class Helper:
    def __init__(self, api_service: ApiService = Depends(ApiService)):
        self.api_service = api_service
    
    def get_llm_usage(self, response):
        token_usage = self.get_token_usage(response)
        llm_usage = {
            **token_usage,
            "duration": 0,
            "provider": "google",
            "model": settings.GEMINI_MODEL,
            "created_at": datetime.now().isoformat()
        }
        return llm_usage

    def get_token_usage(self, response):
        usage_metadata = response.usage_metadata
        token_usage = {
                "prompt_token_count": usage_metadata.prompt_token_count,
                "candidates_token_count": usage_metadata.candidates_token_count,
                "total_token_count": usage_metadata.total_token_count,
                "cached_content_token_count": usage_metadata.cached_content_token_count,
            }
        return token_usage
    
    async def log_failed_url(self, url: str, error: str) -> None:
        """Log failed image URL to JSON file."""
        failed_urls_file = "intermediate_outputs/failed_image_urls.json"
        os.makedirs("intermediate_outputs", exist_ok=True)
        
        # Load existing failed URLs
        failed_data = {"failed_urls": []}
        if os.path.exists(failed_urls_file):
            try:
                with open(failed_urls_file, 'r') as f:
                    failed_data = json.load(f)
            except:
                pass
        
        # Add new failed URL
        failed_entry = {
            "url": url,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        failed_data["failed_urls"].append(failed_entry)
        
        # Save back to file
        with open(failed_urls_file, 'w') as f:
            json.dump(failed_data, f, indent=2)
    
    async def get_image(self, request: QueryRequest, http_client=None) -> Optional[Image.Image]:
        """Get image with graceful error handling."""
        if request.url:
            # Use shared client if provided (for batch processing), otherwise use single request method
            if http_client is not None:
                return await self.get_image_from_url_with_client(http_client, request.url)
            else:
                return await self.get_image_from_url(request.url)
        elif request.file_path:
            return await self.get_image_from_file(request.file_path)
        else:
            await self.log_failed_url("", "No image source provided")
            return None

    async def get_image_from_url_with_client(self, client, url: str) -> Optional[Image.Image]:
        """Get image from URL using shared HTTP client for batch processing."""
        try:
            # Use api_service with shared client for HTTP request
            image_bytes, fetch_error = await self.api_service.get_image_bytes_with_client(client, url)
            
            if image_bytes is None:
                # Use specific error message from api_service
                error_msg = fetch_error if fetch_error else "Unknown error fetching image"
                await self.log_failed_url(url, f"HTTP fetch failed: {error_msg}")
                return None
                
            # Convert to PIL Image
            image = Image.open(BytesIO(image_bytes))
            return image
            
        except Exception as e:
            error_msg = f"Image processing error: {str(e)}"
            await self.log_failed_url(url, error_msg)
            return None

    async def get_image_from_url(self, url: str) -> Optional[Image.Image]:
        """Get image from URL using api_service with graceful error handling (single request)."""
        try:
            # Use api_service for HTTP request with proper timeouts and error details
            image_bytes, fetch_error = await self.api_service.get_image_bytes(url)
            
            if image_bytes is None:
                # Use specific error message from api_service
                error_msg = fetch_error if fetch_error else "Unknown error fetching image"
                await self.log_failed_url(url, f"HTTP fetch failed: {error_msg}")
                return None
                
            # Convert to PIL Image
            image = Image.open(BytesIO(image_bytes))
            return image
            
        except Exception as e:
            error_msg = f"Image processing error: {str(e)}"
            await self.log_failed_url(url, error_msg)
            return None
    
    async def get_image_from_file(self, file_path: str):
        image = Image.open(file_path)
        return image
