import time
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from src.app.models.schemas.prepare_jsonal_schemas import (
    PrepareJsonalRequest
)
from src.app.controllers.prepare_jsonal_controller import PrepareJsonalController
from src.app.utils.error_handler import handle_exceptions


router = APIRouter()


@router.post("/prepare-jsonal/gemini-api", status_code=status.HTTP_200_OK)
@handle_exceptions
async def prepare_jsonal(
    request: PrepareJsonalRequest,
    prepare_jsonal_controller: PrepareJsonalController = Depends(PrepareJsonalController),
):
    """
    Prepare JSONAL file for Gemini API for batch processing.
    
    Args:
        request: PrepareJsonalRequest containing the input file path
        
    Returns:
        JSONResponse with JSONAL file path
    """
    start_time = time.time()
    response = await prepare_jsonal_controller.prepare_jsonal(request)
    end_time = time.time()
    duration = end_time - start_time

    return JSONResponse(
        content={
            "data": response,
            "status_code": status.HTTP_200_OK,
            "detail": "JSONAL file prepared successfully",
            "processing_time": round(duration, 4),
        },
        status_code=status.HTTP_200_OK,
    )