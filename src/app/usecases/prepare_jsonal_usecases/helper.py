from pathlib import Path
import pandas as pd
import asyncio
import json
import base64
import os
from typing import List, Dict, Any, Tuple, Optional
from src.app.config.settings import settings
from src.app.services.api_service import ApiService
from fastapi import Depends
from src.app.utils.logging_utils import loggers
from datetime import datetime
from src.app.prompts.generate_description_prompts import DESC_GEN_USER_PROMPT


class Helper:
    def __init__(self, api_service: ApiService = Depends(ApiService)):
        self.api_service = api_service

    def read_tsv_file(self, file_path: str) -> pd.DataFrame:
        """Read TSV file and return DataFrame."""
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                loggers["error"].error(f"File '{file_path}' does not exist")
                raise FileNotFoundError(f"File '{file_path}' does not exist")
                
            if not file_path_obj.suffix.lower() == '.tsv':
                loggers["error"].error(f"File '{file_path}' is not a TSV file")
                raise ValueError(f"File '{file_path}' is not a TSV file")
            
            df = pd.read_csv(file_path, sep='\t')
            loggers["description"].info(f"Successfully read TSV file with {len(df)} rows: {file_path}")
            
            # Validate required columns
            required_columns = ['photo_id', 'photo_image_url']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Remove empty rows
            df = df.dropna(subset=['photo_id', 'photo_image_url'])
            loggers["description"].info(f"After removing empty rows: {len(df)} rows remaining")
            
            return df
            
        except Exception as e:
            loggers["error"].error(f"Error reading TSV file '{file_path}': {str(e)}")
            raise

    def create_batches(self, df: pd.DataFrame, batch_size: int = None) -> List[pd.DataFrame]:
        """Split DataFrame into batches of specified size."""
        if batch_size is None:
            batch_size = settings.JSONL_BATCH_SIZE
            
        batches = []
        total_rows = len(df)
        
        for i in range(0, total_rows, batch_size):
            batch = df.iloc[i:i + batch_size].copy()
            batches.append(batch)
            
        loggers["description"].info(f"Created {len(batches)} batches with batch size {batch_size}")
        return batches

    async def fetch_image_base64(self, client, photo_id: str, image_url: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Fetch image and convert to base64.
        Returns tuple of (photo_id, base64_data, error_message)
        """
        try:
            image_bytes, error_msg = await self.api_service.get_image_bytes_with_client(client, image_url)
            
            if image_bytes is None:
                loggers["error"].error(f"Failed to fetch image for {photo_id}: {error_msg}")
                return photo_id, None, error_msg
            
            # Convert to base64
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
            return photo_id, base64_data, None
            
        except Exception as e:
            error_msg = f"Error processing image {photo_id}: {str(e)}"
            loggers["error"].error(error_msg)
            return photo_id, None, error_msg

    async def process_batch_parallel(self, batch_df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        """
        Process a batch of URLs in parallel to fetch base64 data.
        Returns tuple of (successful_requests, error_messages)
        """
        successful_requests = []
        error_messages = []
        
        # Create shared HTTP client for the batch
        async with self.api_service.create_shared_client() as client:
            # Create tasks for parallel processing
            tasks = []
            for _, row in batch_df.iterrows():
                photo_id = str(row['photo_id'])
                image_url = str(row['photo_image_url'])
                task = self.fetch_image_base64(client, photo_id, image_url)
                tasks.append(task)
            
            # Process all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    error_msg = f"Task failed with exception: {str(result)}"
                    error_messages.append(error_msg)
                    continue
                
                photo_id, base64_data, error_msg = result
                
                if base64_data is not None:
                    # Create JSONL request format for Gemini Batch API
                    request_data = {
                        "key": photo_id,
                        "request": {
                            "contents": [
                                {
                                    "parts": [
                                        {
                                            "text": DESC_GEN_USER_PROMPT
                                        },
                                        {
                                            "inline_data": {
                                                "mime_type": "image/jpeg",
                                                "data": base64_data
                                            }
                                        }
                                    ]
                                }
                            ],
                            "generation_config": {
                                "temperature": 0.7,
                                "max_output_tokens": 1000
                            }
                        }
                    }
                    successful_requests.append(request_data)
                else:
                    error_messages.append(f"Failed to fetch image for {photo_id}: {error_msg}")
        
        return successful_requests, error_messages

    async def process_batch_parallel_vertexai(self, batch_df: pd.DataFrame) -> Tuple[List[Dict], List[str]]:
        """
        Process a batch of URLs for VertexAI Batch API (no base64 fetching required).
        Returns tuple of (successful_requests, error_messages)
        """
        successful_requests = []
        error_messages = []
        
        try:
            # Process each row to create VertexAI format requests
            for _, row in batch_df.iterrows():
                photo_id = str(row['photo_id'])
                image_url = str(row['photo_image_url'])
                
                # Create JSONL request format for VertexAI Batch API
                request_data = {
                    "request": {
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "text": DESC_GEN_USER_PROMPT
                                    },
                                    {
                                        "file_data": {
                                            "file_uri": image_url,
                                            "mime_type": "image/jpeg"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
                successful_requests.append(request_data)
            
            loggers["description"].info(f"Created {len(successful_requests)} VertexAI batch requests")
            
        except Exception as e:
            error_msg = f"Error processing VertexAI batch: {str(e)}"
            loggers["error"].error(error_msg)
            error_messages.append(error_msg)
        
        return successful_requests, error_messages

    def save_jsonl_file(self, batch_index: int, requests_data: List[Dict], input_file_name: str, is_vertexai: bool = False) -> str:
        """Save JSONL data to file."""
        try:
            # Ensure output directory exists
            output_dir = Path(settings.JSONAL_OUTPUT_DIRECOTRY_PATH)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename with appropriate prefix based on API type
            if is_vertexai:
                filename = f"vertexai_{input_file_name}_batch_{batch_index}.jsonl"
            else:
                filename = f"{input_file_name}_batch_{batch_index}.jsonl"
            file_path = output_dir / filename
            
            # Write JSONL file
            with open(file_path, 'w', encoding='utf-8') as f:
                for request in requests_data:
                    f.write(json.dumps(request, ensure_ascii=False) + '\n')
            
            loggers["description"].info(f"Saved JSONL file: {file_path} with {len(requests_data)} requests")
            return str(file_path)
            
        except Exception as e:
            error_msg = f"Error saving JSONL file for batch {batch_index}: {str(e)}"
            loggers["error"].error(error_msg)
            raise

    def validate_jsonl_file(self, file_path: str) -> bool:
        """Validate that the JSONL file is properly formatted."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = 0
                for line in f:
                    line = line.strip()
                    if line:
                        json.loads(line)  # This will raise an exception if invalid JSON
                        line_count += 1
                
                loggers["description"].info(f"JSONL file validation successful: {file_path} ({line_count} lines)")
                return True
                
        except Exception as e:
            loggers["error"].error(f"JSONL file validation failed for {file_path}: {str(e)}")
            return False
