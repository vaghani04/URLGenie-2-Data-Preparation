import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from google.oauth2 import service_account
from google import genai
from google.genai.types import HttpOptions, GenerateContentConfig
from fastapi import Depends
from PIL import Image

from src.app.config.settings import settings
from src.app.repositories.error_repository import ErrorRepo
from src.app.repositories.llm_usage_repository import LLMUsageRepository


class GeminiService:
    def __init__(
        self,
        error_repo: ErrorRepo = Depends(ErrorRepo),
        llm_usage_repository: LLMUsageRepository = Depends(LLMUsageRepository)
    ):
        self.error_repo = error_repo
        self.llm_usage_repository = llm_usage_repository
        self.client = None
        self.model_name = settings.GEMINI_MODEL
        self.vertex_ai_enabled = settings.VERTEX_AI_ENABLED
        if self.vertex_ai_enabled:
            self._initialize_vertex_ai_client()

    def _initialize_vertex_ai_client(self):
        """Initialize the Vertex AI Gemini client."""
        try:
            # Parse service account JSON from settings
            service_account_json = json.loads(settings.VERTEX_SERVICE_ACCOUNT_JSON)
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                service_account_json,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            
            # Refresh credentials to get access token
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            
            # Initialize the Google Gen AI client with Vertex AI
            self.client = genai.Client(
                vertexai=True,
                project=settings.VERTEX_SERVICE_PROJECT_ID,
                location=settings.VERTEX_SERVICE_REGION,
                credentials=credentials,
                http_options=HttpOptions(api_version="v1")
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid Vertex AI service account JSON: {str(e)}"
            self._log_error(error_msg, "json_decode", {"original_error": str(e)})
            raise ValueError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to initialize Vertex AI Gemini client: {str(e)}"
            self._log_error(error_msg, "client_initialization", {"original_error": str(e)})
            raise RuntimeError(error_msg)
    
    def _get_client(self):
        """Get the appropriate client based on VERTEX_AI_ENABLED setting."""
        if self.vertex_ai_enabled:
            if not self.client:
                raise RuntimeError("Vertex AI client not initialized")
            return self.client
        else:
            return genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_content(
        self,
        contents: Union[str, List[Union[str, Image.Image]]],
        max_tokens: Optional[int] = 1000,
        temperature: Optional[float] = 0.2
    ) -> Dict[str, Any]:
        """
        Generate content using appropriate client (Vertex AI or Gemini API).
        
        Args:
            contents: The content to send to the model (text, image, or combination)
            max_tokens: Maximum number of output tokens
            temperature: Sampling temperature
            
        Returns:
            Dictionary containing response text, token usage, and duration
        """
        try:
            start_time = time.time()
            client = self._get_client()
            provider = "google_vertex_ai" if self.vertex_ai_enabled else "google_gemini_api"
            
            # Generate content using the appropriate client
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=GenerateContentConfig(
                    max_output_tokens=max_tokens or 1000,
                    temperature=temperature or 0.0,
                )
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Extract response text
            response_text = response.text if response and response.text else ""
            
            # Extract token usage and create LLM usage record
            token_usage = self._extract_token_usage(response)
            llm_usage = self._create_llm_usage_record(token_usage, duration, provider=provider)
            
            # Log usage to repository
            await self.llm_usage_repository.add_llm_usage(llm_usage)
            
            return {
                "text": response_text,
                "token_usage": token_usage,
                "duration": duration,
                "raw_response": response
            }
            
        except Exception as e:
            provider = "google_vertex_ai" if self.vertex_ai_enabled else "google_gemini_api"
            error_msg = f"Error generating content with {provider}: {str(e)}"
            await self._log_error(error_msg, "generate_content", {
                "model": self.model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "provider": provider,
                "original_error": str(e)
            })
            raise

    
    async def generate_content_with_api(
        self,
        contents: Union[str, List[Union[str, Image.Image]]],
        max_tokens: Optional[int] = 1000,
        temperature: Optional[float] = 0.2
    ) -> Dict[str, Any]:
        """
        Generate content using Vertex AI Gemini.
        
        Args:
            contents: The content to send to the model (text, image, or combination)
            max_tokens: Maximum number of output tokens
            temperature: Sampling temperature
            
        Returns:
            Dictionary containing response text, token usage, and duration
        """
        # if not self.client:
        #     raise RuntimeError("Gemini client not initialized")
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        try:
            start_time = time.time()
            
            # Generate content using the Gemini API
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=GenerateContentConfig(
                    max_output_tokens=max_tokens or 1000,
                    temperature=temperature or 0.0,
                )
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Extract response text
            response_text = response.text if response and response.text else ""
            
            # Extract token usage and create LLM usage record
            token_usage = self._extract_token_usage(response)
            llm_usage = self._create_llm_usage_record(token_usage, duration, provider="google_gemini_api")
            
            # Log usage to repository
            await self.llm_usage_repository.add_llm_usage(llm_usage)
            
            return {
                "text": response_text,
                "token_usage": token_usage,
                "duration": duration,
                "raw_response": response
            }
            
        except Exception as e:
            error_msg = f"Error generating content with Vertex AI Gemini: {str(e)}"
            await self._log_error(error_msg, "generate_content", {
                "model": self.model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "original_error": str(e)
            })
            raise        

    def _extract_token_usage(self, response) -> Dict[str, int]:
        """
        Extract token usage from response.
        
        Args:
            response: The response from Gemini API
            
        Returns:
            Dictionary containing token usage information
        """
        token_usage = {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "total_token_count": 0,
            "cached_content_token_count": 0,
        }
        
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                
                token_usage["prompt_token_count"] = getattr(usage, 'prompt_token_count', 0)
                token_usage["candidates_token_count"] = getattr(usage, 'candidates_token_count', 0)
                token_usage["total_token_count"] = getattr(usage, 'total_token_count', 0)
                token_usage["cached_content_token_count"] = getattr(usage, 'cached_content_token_count', 0)
                
        except Exception as e:
            # Log warning but don't fail the request
            self._log_warning(f"Error extracting token usage: {str(e)}", {
                "operation": "extract_token_usage",
                "original_error": str(e)
            })
        
        return token_usage

    def _create_llm_usage_record(self, token_usage: Dict[str, int], duration: float, provider: str = "google_vertex_ai") -> Dict[str, Any]:
        """
        Create LLM usage record for logging.
        
        Args:
            token_usage: Token usage information
            duration: Request duration in seconds
            
        Returns:
            Dictionary containing complete LLM usage information
        """
        return {
            **token_usage,
            "duration": duration,
            "provider": provider,
            "model": self.model_name,
            "created_at": datetime.now().isoformat()
        }

    async def _log_error(self, message: str, error_type: str, additional_context: Dict[str, Any] = None):
        """Log error to error repository."""
        try:
            context = {
                "file": "gemini_service.py",
                "service": "GeminiService",
                "error_type": error_type,
                "operation": "gemini_service"
            }
            if additional_context:
                context.update(additional_context)
                
            await self.error_repo.log_error(
                error=message,
                additional_context=context
            )
        except Exception:
            # Don't let logging errors break the main flow
            pass

    def _log_warning(self, message: str, additional_context: Dict[str, Any] = None):
        """Log warning (synchronous helper for token usage extraction)."""
        try:
            # For now, just pass - could implement async warning logging if needed
            pass
        except Exception:
            # Don't let logging errors break the main flow
            pass

    async def count_tokens(self, contents: Union[str, List[Union[str, Image.Image]]]) -> int:
        """
        Count tokens for given content.
        
        Args:
            contents: The content to count tokens for
            
        Returns:
            Number of tokens
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized")
            
        try:
            response = await self.client.aio.models.count_tokens(
                model=self.model_name,
                contents=contents
            )
            return response.total_tokens
            
        except Exception as e:
            error_msg = f"Error counting tokens: {str(e)}"
            await self._log_error(error_msg, "count_tokens", {
                "model": self.model_name,
                "original_error": str(e)
            })
            # Return 0 as fallback
            return 0