from pathlib import Path
import pandas as pd
import asyncio
import os
from typing import List, Dict, Any
from src.app.config.settings import settings
from src.app.models.schemas.desc_gen_schemas import QueryRequest
from src.app.usecases.generate_description_usecases.generate_description_usecase import GenerateDescriptionUsecase
from src.app.services.api_service import ApiService
from fastapi import Depends
from src.app.utils.logging_utils import loggers


class Helper:
    def __init__(self, 
                 generate_desc_usecase: GenerateDescriptionUsecase = Depends(GenerateDescriptionUsecase),
                 api_service: ApiService = Depends(ApiService)):
        self.generate_desc_usecase = generate_desc_usecase
        self.api_service = api_service

    def get_tsv_files(self, directory_path: str):
        dir_path = Path(directory_path)
        
        if not dir_path.exists():
            loggers["error"].error(f"Directory '{directory_path}' does not exist")
            return f"Error: Directory '{directory_path}' does not exist"
        if not dir_path.is_dir():
            loggers["error"].error(f"'{directory_path}' is not a directory")
            return f"Error: '{directory_path}' is not a directory"
        
        tsv_files = list(dir_path.glob("*.tsv"))
        loggers["description"].info(f"Found {len(tsv_files)} TSV files in directory: {directory_path}")
        return tsv_files

    def create_batches(self, df: pd.DataFrame, batch_size: int = None) -> List[pd.DataFrame]:
        """Split DataFrame into batches of specified size."""
        if batch_size is None:
            batch_size = settings.BATCH_SIZE
            
        batches = []
        total_rows = len(df)
        
        for i in range(0, total_rows, batch_size):
            batch = df.iloc[i:i + batch_size].copy()
            batches.append(batch)
            
        return batches

    async def process_single_url(self, url: str, shared_client=None) -> Dict[str, Any]:
        """Process a single URL and return description and keywords with graceful error handling."""
        try:
            request = QueryRequest(url=url)
            result = await self.generate_desc_usecase.execute(request, shared_client)
            
            # Check if result indicates an error
            if result.get("status") == "error":
                loggers["error"].error(f"Error processing URL {url}: {result.get('error', 'Unknown error')}")
                return {
                    "description": "",
                    "keywords": [],
                    "status": "error",
                    "error": result.get("error", "Unknown error")
                }
            
            return {
                "description": result.get("description", ""),
                "keywords": result.get("keywords", []),
                "status": "success"
            }
        except Exception as e:
            loggers["error"].error(f"Error processing URL {url}: {str(e)}")
            return {
                "description": "",
                "keywords": [],
                "status": "error",
                "error": str(e)
            }

    async def process_batch_parallel(self, batch_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Process a batch of URLs in parallel using sub-batching and shared HTTP client connection pool."""
        urls = batch_df['photo_image_url'].tolist()
        
        # Create shared HTTP client with connection pooling to prevent resource exhaustion
        shared_client = self.api_service.create_shared_client()
        
        try:
            loggers["description"].info(f"Processing batch of {len(urls)} URLs with shared connection pool and sub-batching")
            
            # Process URLs in smaller sub-batches to prevent overwhelming the connection pool
            sub_batch_size = 100  # Process 100 URLs at a time
            all_results = []
            
            for i in range(0, len(urls), sub_batch_size):
                sub_batch_urls = urls[i:i + sub_batch_size]
                loggers["description"].info(f"Processing sub-batch {i//sub_batch_size + 1}/{(len(urls)-1)//sub_batch_size + 1} with {len(sub_batch_urls)} URLs")
                
                # Create tasks for this sub-batch
                tasks = [self.process_single_url(url, shared_client) for url in sub_batch_urls]
                
                # Execute sub-batch in parallel
                sub_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process sub-batch results
                for result in sub_results:
                    if isinstance(result, Exception):
                        all_results.append({
                            "description": "",
                            "keywords": [],
                            "status": "error",
                            "error": str(result)
                        })
                    else:
                        all_results.append(result)
                
                # Small delay between sub-batches to allow connection pool to recover
                if i + sub_batch_size < len(urls):
                    await asyncio.sleep(0.1)
                    
            return all_results
            
        finally:
            # Always clean up the shared client
            await shared_client.aclose()
            loggers["description"].info(f"Closed shared HTTP client after processing batch with sub-batching")

    def update_dataframe_with_results(self, batch_df: pd.DataFrame, results: List[Dict[str, Any]]) -> pd.DataFrame:
        """Update the batch DataFrame with description and keywords results."""
        batch_df = batch_df.copy()
        
        # Add new columns if they don't exist
        if 'description' not in batch_df.columns:
            batch_df['description'] = ""
        if 'keywords' not in batch_df.columns:
            batch_df['keywords'] = ""
            
        # Update the DataFrame with results
        for i, result in enumerate(results):
            if i < len(batch_df):
                batch_df.iloc[i, batch_df.columns.get_loc('description')] = result['description']
                # Convert keywords list to string for TSV storage
                keywords_str = ", ".join(result['keywords']) if result['keywords'] else ""
                batch_df.iloc[i, batch_df.columns.get_loc('keywords')] = keywords_str
                
        return batch_df

    def save_tsv_file(self, df: pd.DataFrame, file_path) -> None:
        """Save DataFrame back to TSV file."""
        df.to_csv(file_path, sep='\t', index=False)
    
    def list_temp_files(self) -> List[str]:
        """List all temporary TSV files in intermediate_outputs directory."""
        temp_dir = Path("intermediate_outputs")
        if not temp_dir.exists():
            return []
        
        temp_files = list(temp_dir.glob("temp_*.tsv"))
        return [str(f) for f in temp_files]
    
    def cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up old temporary files and return summary."""
        temp_files = self.list_temp_files()
        
        if not temp_files:
            return {"status": "no_temp_files", "message": "No temporary files found"}
        
        cleanup_results = {
            "status": "success",
            "temp_files_found": len(temp_files),
            "files_cleaned": 0,
            "errors": []
        }
        
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
                cleanup_results["files_cleaned"] += 1
                loggers["description"].info(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                cleanup_results["errors"].append({
                    "file": temp_file,
                    "error": str(e)
                })
                loggers["error"].error(f"Failed to cleanup temp file {temp_file}: {e}")
        
        return cleanup_results