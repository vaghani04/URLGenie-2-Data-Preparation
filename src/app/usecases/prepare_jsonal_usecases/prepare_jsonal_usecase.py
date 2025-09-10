
from fastapi import Depends
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional
from src.app.usecases.prepare_jsonal_usecases.helper import Helper
from src.app.config.settings import settings
from src.app.models.schemas.prepare_jsonal_schemas import PrepareJsonalResponse, BatchProcessingResult
from src.app.utils.logging_utils import loggers


class PrepareJsonalUsecase:
    def __init__(self, helper: Helper = Depends(Helper)):
        self.helper = helper

    async def execute(self, file_path: str, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Main execution method to process TSV file and create JSONL files for Gemini Batch API.
        
        Args:
            file_path: Path to the input TSV file
            batch_size: Optional batch size override (200-800 range)
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        
        try:
            # Use provided batch size or default from settings
            effective_batch_size = batch_size if batch_size is not None else settings.JSONL_BATCH_SIZE
            
            # Validate batch size range
            # if not (200 <= effective_batch_size <= 800):
            #     raise ValueError(f"Batch size must be between 200 and 800, got: {effective_batch_size}")
            
            api_type = "VertexAI" if settings.VERTEX_AI_ENABLED else "Gemini"
            loggers["description"].info(f"Starting JSONL preparation for {api_type} API - file: {file_path} with batch size: {effective_batch_size}")
            
            # Read TSV file
            df = self.helper.read_tsv_file(file_path)
            
            # Extract input file name (without extension) for output file naming
            input_file_name = Path(file_path).stem
            
            if df.empty:
                return {
                    "status": "error",
                    "message": "TSV file is empty or has no valid data",
                    "total_batches": 0,
                    "batch_results": [],
                    "output_directory": settings.JSONAL_OUTPUT_DIRECOTRY_PATH,
                    "total_processing_time": time.time() - start_time
                }
            
            # Create batches
            batches = self.helper.create_batches(df, effective_batch_size)
            
            # Process all batches in parallel
            batch_results = await self.process_all_batches_parallel(batches, input_file_name)
            
            # Calculate summary statistics
            total_successful = sum(result.successful_requests for result in batch_results)
            total_failed = sum(result.failed_requests for result in batch_results)
            total_processing_time = time.time() - start_time
            
            response_data = {
                "status": "success",
                "message": f"Successfully processed {total_successful} requests across {len(batches)} batches",
                "total_batches": len(batches),
                "batch_results": [result.dict() for result in batch_results],
                "output_directory": settings.JSONAL_OUTPUT_DIRECOTRY_PATH,
                "total_processing_time": round(total_processing_time, 4),
                "summary": {
                    "total_requests": total_successful + total_failed,
                    "successful_requests": total_successful,
                    "failed_requests": total_failed,
                    "success_rate": round((total_successful / (total_successful + total_failed)) * 100, 2) if (total_successful + total_failed) > 0 else 0
                }
            }
            
            loggers["description"].info(f"JSONL preparation completed. Success rate: {response_data['summary']['success_rate']}%")
            return response_data
            
        except Exception as e:
            error_msg = f"Error in JSONL preparation: {str(e)}"
            loggers["error"].error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "total_batches": 0,
                "batch_results": [],
                "output_directory": settings.JSONAL_OUTPUT_DIRECOTRY_PATH,
                "total_processing_time": time.time() - start_time
            }

    async def process_all_batches_parallel(self, batches, input_file_name: str) -> list[BatchProcessingResult]:
        """
        Process all batches in parallel for maximum performance.
        
        Args:
            batches: List of DataFrame batches
            input_file_name: Name of the input file (without extension) for output file naming
            
        Returns:
            List of BatchProcessingResult objects
        """
        # Create tasks for parallel batch processing
        tasks = []
        for batch_index, batch_df in enumerate(batches):
            task = self.process_single_batch(batch_index, batch_df, input_file_name)
            tasks.append(task)
        
        # Execute all batches in parallel
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions in batch processing
        final_results = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                error_result = BatchProcessingResult(
                    batch_index=i,
                    file_path="",
                    total_requests=len(batches[i]) if i < len(batches) else 0,
                    successful_requests=0,
                    failed_requests=len(batches[i]) if i < len(batches) else 0,
                    errors=[f"Batch processing failed: {str(result)}"]
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        return final_results

    async def process_single_batch(self, batch_index: int, batch_df, input_file_name: str) -> BatchProcessingResult:
        """
        Process a single batch: fetch images in parallel and save JSONL file.
        
        Args:
            batch_index: Index of the current batch
            batch_df: DataFrame containing the batch data
            input_file_name: Name of the input file (without extension) for output file naming
            
        Returns:
            BatchProcessingResult object
        """
        try:
            loggers["description"].info(f"Processing batch {batch_index} with {len(batch_df)} items")
            
            if settings.VERTEX_AI_ENABLED:
                # Process batch for VertexAI (no base64 fetching required)
                successful_requests, error_messages = await self.helper.process_batch_parallel_vertexai(batch_df)
            else:
                # Process batch in parallel to fetch base64 data
                successful_requests, error_messages = await self.helper.process_batch_parallel(batch_df)
            
            # Save JSONL file if we have successful requests
            file_path = ""
            if successful_requests:
                file_path = self.helper.save_jsonl_file(batch_index, successful_requests, input_file_name, settings.VERTEX_AI_ENABLED)
                
                # Validate the created file
                if not self.helper.validate_jsonl_file(file_path):
                    error_messages.append(f"JSONL file validation failed for batch {batch_index}")
            
            result = BatchProcessingResult(
                batch_index=batch_index,
                file_path=file_path,
                total_requests=len(batch_df),
                successful_requests=len(successful_requests),
                failed_requests=len(batch_df) - len(successful_requests),
                errors=error_messages
            )
            
            loggers["description"].info(f"Batch {batch_index} completed: {len(successful_requests)}/{len(batch_df)} successful")
            return result
            
        except Exception as e:
            error_msg = f"Error processing batch {batch_index}: {str(e)}"
            loggers["error"].error(error_msg)
            
            return BatchProcessingResult(
                batch_index=batch_index,
                file_path="",
                total_requests=len(batch_df),
                successful_requests=0,
                failed_requests=len(batch_df),
                errors=[error_msg]
            )