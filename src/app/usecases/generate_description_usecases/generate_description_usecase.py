from src.app.prompts.generate_description_prompts import DESC_GEN_USER_PROMPT
from google import genai
from src.app.config.settings import settings
from src.app.utils.response_parser import parse_response
from src.app.services.api_service import ApiService
from fastapi import Depends 
from src.app.usecases.generate_description_usecases.helper import Helper
from src.app.models.schemas.desc_gen_schemas import QueryRequest

class GenerateDescriptionUsecase:
    def __init__(self,
        api_service: ApiService = Depends(ApiService),
        helper: Helper = Depends(Helper)
    ):
        self.llm = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.api_service = api_service
        self.helper = helper

    async def execute(self, request: QueryRequest):
        result = await self.generate_description(request)
        return result

    async def generate_description(self, request: QueryRequest):
        image = await self.helper.get_image(request)
        print(settings.GEMINI_API_KEY)
        response = await self.llm.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[image, DESC_GEN_USER_PROMPT]
        )
        
        token_usage = self.helper.get_token_usage(response)
        generated_text = response.text
        
        parsed_text = parse_response(generated_text)
        
        return {
            "result": parsed_text,
            "token_usage": token_usage
        }