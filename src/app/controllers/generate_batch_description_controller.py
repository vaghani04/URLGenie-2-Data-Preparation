from fastapi import Depends
from src.app.usecases.generate_batch_description_usecases.generate_batch_description_usecase import GenerateBatchDescriptionUsecase

class GenerateBatchDescriptionController:
    def __init__(self, generate_batch_description_usecase: GenerateBatchDescriptionUsecase = Depends(GenerateBatchDescriptionUsecase)):
        self.generate_batch_description_usecase = generate_batch_description_usecase

    async def generate_batch_description(self, directory_path: str):
        return await self.generate_batch_description_usecase.execute(directory_path)