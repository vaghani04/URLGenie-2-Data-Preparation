from fastapi import Depends
from src.app.models.schemas.desc_gen_schemas import QueryRequest
from src.app.usecases.generate_description_usecases.generate_description_usecase import GenerateDescriptionUsecase

class GenerateDescriptionController:
    def __init__(self,
        generate_description_usecase: GenerateDescriptionUsecase = Depends(GenerateDescriptionUsecase),
        ):
        self.generate_description_usecase = generate_description_usecase

    async def generate_description(self, request: QueryRequest):
        return await self.generate_description_usecase.execute(request)