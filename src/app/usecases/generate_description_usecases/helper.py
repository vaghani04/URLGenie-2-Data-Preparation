from src.app.models.schemas.desc_gen_schemas import QueryRequest
from PIL import Image
import httpx
from io import BytesIO

class Helper:
    def __init__(self):
        pass

    def get_token_usage(self, response):
        usage_metadata = response.usage_metadata
        token_usage = {
            "prompt_token_count": usage_metadata.prompt_token_count,
            "candidates_token_count": usage_metadata.candidates_token_count,
            "total_token_count": usage_metadata.total_token_count,
            "cached_content_token_count": usage_metadata.cached_content_token_count,
        }
        return token_usage
    
    async def get_image(self, request: QueryRequest):
        if request.url:
            return await self.get_image_from_url(request.url)
        elif request.file_path:
            return await self.get_image_from_file(request.file_path)
        else:
            raise ValueError("No image source provided")

    async def get_image_from_url(self, url: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            image_bytes = response.content
        
        # Convert to PIL Image
        image = Image.open(BytesIO(image_bytes))
        return image
    
    async def get_image_from_file(self, file_path: str):
        image = Image.open(file_path)
        return image
