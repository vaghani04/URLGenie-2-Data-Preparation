import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status

from src.app.config.database import mongodb_database


class ErrorRepo:
    def __init__(
        self,
        collection=Depends(mongodb_database.get_error_collection),
    ):
        self.collection = collection

    async def log_error(
        self,
        error: Exception,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an error with essential context"""
        try:
            error_id = str(uuid.uuid4())

            error_log = {
                "error_id": error_id,
                "timestamp": datetime.now(),
                "error_message": str(error),
                "error_type": error.__class__.__name__,
                "stack_trace": traceback.format_exc(),
                "additional_context": additional_context or {},
            }

            await self.collection.insert_one(error_log)
            return error_id
        except Exception as e:
            
            error_id = str(uuid.uuid4())
            
            error_log = {
                "error_id": error_id,
                "timestamp": datetime.now(),
                "error_message": str(e),
                "error_type": e.__class__.__name__,
                "stack_trace": traceback.format_exc(),
            }
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to log error: {str(e)} Error while logging error in error_repository.py in log_error()",
            )


error_repo = ErrorRepo()
