from fastapi import Depends
from src.app.usecases.prepare_jsonal_usecases.prepare_jsonal_usecase import PrepareJsonalUsecase
from src.app.models.schemas.prepare_jsonal_schemas import PrepareJsonalRequest
from src.app.utils.logging_utils import loggers


class PrepareJsonalController:
    def __init__(self, prepare_jsonal_usecase: PrepareJsonalUsecase = Depends(PrepareJsonalUsecase)):
        self.prepare_jsonal_usecase = prepare_jsonal_usecase

    async def prepare_jsonal(self, request: PrepareJsonalRequest):
        """
        Controller method to handle JSONL preparation requests.
        
        Args:
            request: PrepareJsonalRequest containing input file path and optional batch size
            
        Returns:
            Result from the usecase execution
        """
        loggers["requests"].info(f"Received JSONL preparation request for file: {request.input_file_path}")
        
        if request.batch_size:
            loggers["requests"].info(f"Using custom batch size: {request.batch_size}")
        
        return await self.prepare_jsonal_usecase.execute(
            file_path=request.input_file_path,
            batch_size=request.batch_size
        )