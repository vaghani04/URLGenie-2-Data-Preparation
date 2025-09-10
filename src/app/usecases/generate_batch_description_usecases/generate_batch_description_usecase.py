from fastapi import Depends
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from src.app.usecases.generate_batch_description_usecases.helper import Helper
from src.app.config.settings import settings
from src.app.utils.logging_utils import loggers
import os
import shutil
from datetime import datetime


class GenerateBatchDescriptionUsecase:
    def __init__(self, helper: Helper = Depends(Helper)):
        self.helper = helper

    async def execute(self, directory_path: str) -> Dict[str, Any]:
        """
        Process all TSV files in the directory.
        Files are processed sequentially, batches within files are processed sequentially,
        but URLs within each batch are processed in parallel.
        """
        try:
            # Get all TSV files from directory
            tsv_files = self.helper.get_tsv_files(directory_path)
            
            if isinstance(tsv_files, str):  # Error case
                return {"status": "error", "message": tsv_files}
            
            if not tsv_files:
                return {"status": "error", "message": f"No TSV files found in directory: {directory_path}"}
            
            results = {
                "status": "success",
                "files_processed": 0,
                "total_files": len(tsv_files),
                "processed_files": [],
                "errors": []
            }
            
            # Process each TSV file sequentially
            for tsv_file in tsv_files:
                file_result = await self.process_single_tsv_file(tsv_file)
                results["processed_files"].append(file_result)
                
                if file_result["status"] == "success":
                    results["files_processed"] += 1
                else:
                    results["errors"].append({
                        "file": str(tsv_file),
                        "error": file_result.get("message", "Unknown error")
                    })
                    
                loggers["description"].info(f"Processed file: {tsv_file} - Status: {file_result['status']}")
            
            return results
            
        except Exception as e:
            loggers["error"].error(f"Error in batch processing: {str(e)}")
            return {"status": "error", "message": f"Batch processing failed: {str(e)}"}

    async def process_single_tsv_file(self, tsv_file: Path) -> Dict[str, Any]:
        """Process a single TSV file by batching and parallel processing with temporary file backup."""
        temp_file_path = None
        try:
            loggers["description"].info(f"Starting processing of file: {tsv_file}")
            
            # Read the TSV file
            df = pd.read_csv(tsv_file, sep="\t")
            original_row_count = len(df)
            
            loggers["description"].info(f"File {tsv_file} has {original_row_count} rows")
            
            # Validate required columns
            if 'photo_image_url' not in df.columns:
                return {
                    "status": "error",
                    "file": str(tsv_file),
                    "message": "Required column 'photo_image_url' not found"
                }
            
            # Create temporary file in intermediate_outputs directory
            os.makedirs("intermediate_outputs", exist_ok=True)
            timestamp = datetime.now().strftime("%d_%m_%H_%M")
            temp_file_name = f"temp_{tsv_file.stem}_{timestamp}.tsv"
            temp_file_path = os.path.join("intermediate_outputs", temp_file_name)
            
            # Initialize temp file with headers (add description and keywords columns if not present)
            temp_df = df.copy()
            if 'description' not in temp_df.columns:
                temp_df['description'] = ""
            if 'keywords' not in temp_df.columns:
                temp_df['keywords'] = ""
            
            # Save header to temp file
            header_df = pd.DataFrame(columns=temp_df.columns)
            header_df.to_csv(temp_file_path, sep='\t', index=False)
            
            loggers["description"].info(f"Created temporary file: {temp_file_path}")
            
            # Create batches
            batches = self.helper.create_batches(df)
            total_batches = len(batches)
            
            loggers["description"].info(f"Created {total_batches} batches for file: {tsv_file}")
            
            # Process each batch sequentially and append to temp file
            processed_rows = 0
            for batch_index, batch_df in enumerate(batches):
                loggers["description"].info(f"Processing batch {batch_index + 1}/{total_batches} with {len(batch_df)} URLs")
                
                # Process batch with parallel API calls
                results = await self.helper.process_batch_parallel(batch_df)
                
                # Update the batch DataFrame with results
                updated_batch_df = self.helper.update_dataframe_with_results(batch_df, results)
                
                # Append this batch to the temporary file immediately
                updated_batch_df.to_csv(temp_file_path, sep='\t', index=False, mode='a', header=False)
                processed_rows += len(updated_batch_df)
                
                loggers["description"].info(f"Completed and saved batch {batch_index + 1}/{total_batches} to temp file. Total processed: {processed_rows}")
            
            # Prepare final output file path
            output_file_path = settings.OUTPUT_DIRECTORY_PATH
            file_name = tsv_file.name
            final_output_path = os.path.join(output_file_path, file_name)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

            # Move temporary file to final destination
            shutil.move(temp_file_path, final_output_path)
            temp_file_path = None  # Reset so cleanup doesn't try to delete it
            
            loggers["description"].info(f"Successfully moved temp file to final destination: {final_output_path}")
            
            return {
                "status": "success",
                "file": str(tsv_file),
                "original_rows": original_row_count,
                "processed_rows": processed_rows,
                "batches_processed": total_batches,
                "batch_size": settings.BATCH_SIZE,
                "output_file": final_output_path
            }
            
        except Exception as e:
            loggers["error"].error(f"Error processing file {tsv_file}: {str(e)}")
            
            # Cleanup: Remove temporary file if it exists and wasn't moved
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    loggers["description"].info(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as cleanup_error:
                    loggers["error"].error(f"Failed to cleanup temp file {temp_file_path}: {cleanup_error}")
            
            return {
                "status": "error",
                "file": str(tsv_file),
                "message": f"Failed to process file: {str(e)}"
            }