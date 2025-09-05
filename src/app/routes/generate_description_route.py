import time
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from src.app.models.schemas.desc_gen_schemas import QueryRequest
from src.app.controllers.generate_description_controller import GenerateDescriptionController
from src.app.utils.error_handler import handle_exceptions


router = APIRouter()

@router.post("/generate-description", status_code=status.HTTP_200_OK)
@handle_exceptions
async def generate_description(
    request: QueryRequest,
    generate_description_controller: GenerateDescriptionController = Depends(
        GenerateDescriptionController
    ),
):
    start_time = time.time()
    response = await generate_description_controller.generate_description(request)
    end_time = time.time()
    duration = end_time - start_time

    return JSONResponse(
        content={
            "data": response,
            "status_code": status.HTTP_200_OK,
            "detail": "Description generated successfully",
            "processing_time": round(duration, 4),
        },
        status_code=status.HTTP_200_OK,
    )
