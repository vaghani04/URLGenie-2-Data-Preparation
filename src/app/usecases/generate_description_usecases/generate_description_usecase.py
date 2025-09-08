from src.app.prompts.generate_description_prompts import DESC_GEN_USER_PROMPT
from google import genai
from src.app.config.settings import settings
from src.app.utils.response_parser import parse_response
from src.app.services.api_service import ApiService
from fastapi import Depends 
from src.app.usecases.generate_description_usecases.helper import Helper
from src.app.models.schemas.desc_gen_schemas import QueryRequest
from src.app.repositories.llm_usage_repository import LLMUsageRepository
import time
import httpx

class GenerateDescriptionUsecase:
    def __init__(self,
        api_service: ApiService = Depends(ApiService),
        helper: Helper = Depends(Helper),
        llm_usage_repository: LLMUsageRepository = Depends(LLMUsageRepository)
    ):
        self.llm = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.api_service = api_service
        self.helper = helper
        self.llm_usage_repository = llm_usage_repository

    async def execute(self, request: QueryRequest, http_client: httpx.AsyncClient = None):
        result = await self.generate_description(request, http_client)
        return result

    async def generate_description(self, request: QueryRequest, http_client: httpx.AsyncClient = None):
        image = await self.helper.get_image(request, http_client)
        
        # Handle case where image failed to load
        if image is None:
            return {
                "description": "",
                "keywords": [],
                "status": "error",
                "error": "Failed to load image"
            }
        
        try:
            start_time = time.time()
            response = await self.llm.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[image, DESC_GEN_USER_PROMPT]
            )
            end_time = time.time()
            duration = end_time - start_time
            llm_usage = self.helper.get_llm_usage(response)
            llm_usage["duration"] = duration

            await self.llm_usage_repository.add_llm_usage(llm_usage)
            generated_text = response.text
            
            # Parse response with error handling
            try:
                parsed_text = parse_response(generated_text)
                
                # Handle case where parse_response returns None or fails
                if parsed_text is None:
                    if request.url:
                        await self.helper.log_failed_url(request.url, "JSON parsing failed - returned None")
                    return {
                        "description": "",
                        "keywords": [],
                        "status": "error",
                        "error": "Failed to parse response JSON"
                    }
                    
                return {
                    "description": parsed_text.get("description", ""),
                    "keywords": parsed_text.get("keywords", [])
                }
                
            except Exception as parse_error:
                # Log parsing error and failed URL
                if request.url:
                    await self.helper.log_failed_url(request.url, f"JSON parsing exception: {str(parse_error)}")
                    
                return {
                    "description": "",
                    "keywords": [],
                    "status": "error",
                    "error": f"JSON parsing failed: {str(parse_error)}"
                }
        except Exception as e:
            # Get more specific error details
            error_details = self._get_detailed_error_message(e)
            
            # Log failed URL if it's a URL-based request
            if request.url:
                await self.helper.log_failed_url(request.url, f"Gemini API error: {error_details}")
            
            return {
                "description": "",
                "keywords": [],
                "status": "error", 
                "error": f"Generation failed: {error_details}"
            }
    
    def _get_detailed_error_message(self, exception: Exception) -> str:
        """Extract detailed error message from exception."""
        try:
            # Handle different types of exceptions
            error_msg = str(exception).strip()
            
            # If main error message is empty, try to get more details
            if not error_msg:
                error_msg = f"{type(exception).__name__}"
                
                # Try to get additional context from exception attributes
                if hasattr(exception, 'response'):
                    try:
                        response = exception.response
                        if hasattr(response, 'status_code'):
                            error_msg += f" (HTTP {response.status_code})"
                        if hasattr(response, 'text') and response.text:
                            error_msg += f": {response.text[:200]}"
                    except:
                        pass
                
                if hasattr(exception, 'message') and exception.message:
                    error_msg += f": {exception.message}"
                    
                if hasattr(exception, 'args') and exception.args:
                    args_str = ', '.join(str(arg) for arg in exception.args if str(arg).strip())
                    if args_str:
                        error_msg += f" ({args_str})"
            
            # Handle specific Google API errors
            if 'PERMISSION_DENIED' in error_msg:
                error_msg += " - API key blocked or insufficient permissions"
            elif 'QUOTA_EXCEEDED' in error_msg:
                error_msg += " - API quota exceeded"
            elif 'RESOURCE_EXHAUSTED' in error_msg:
                error_msg += " - Rate limit exceeded" 
            elif 'INTERNAL' in error_msg:
                error_msg += " - Google API internal error"
                
            return error_msg if error_msg else "Unknown API error"
            
        except Exception:
            return f"{type(exception).__name__}: Unknown error details"