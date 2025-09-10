from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class PrepareJsonalRequest(BaseModel):
    input_file_path: str = Field(..., description="Path to the input TSV file")
    batch_size: Optional[int] = Field(None, description="Batch size for processing (200-800 range)", ge=200, le=800)


class BatchProcessingResult(BaseModel):
    batch_index: int
    file_path: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    errors: List[str] = []


class PrepareJsonalResponse(BaseModel):
    status: str
    message: str
    total_batches: int
    batch_results: List[BatchProcessingResult]
    output_directory: str
    total_processing_time: float
    