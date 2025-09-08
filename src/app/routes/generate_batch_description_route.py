import time
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from src.app.models.schemas.generate_batch_description_schemas import GenerateBatchDescriptionRequest
from src.app.controllers.generate_batch_description_controller import GenerateBatchDescriptionController
from src.app.utils.error_handler import handle_exceptions


router = APIRouter()

@router.post("/generate-batch-description", status_code=status.HTTP_200_OK)
@handle_exceptions
async def generate_batch_description(
    request: GenerateBatchDescriptionRequest,
    generate_batch_description_controller: GenerateBatchDescriptionController = Depends(
        GenerateBatchDescriptionController
    ),
):
    start_time = time.time()
    response = await generate_batch_description_controller.generate_batch_description(request.directory_path)
    end_time = time.time()
    duration = end_time - start_time

    return JSONResponse(
        content={
            "data": response,
            "status_code": status.HTTP_200_OK,
            "detail": "Batch description generated successfully",
            "processing_time": round(duration, 4),
        },
        status_code=status.HTTP_200_OK,
    )
