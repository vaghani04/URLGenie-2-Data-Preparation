from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None