from pydantic import BaseModel

class GenerateBatchDescriptionRequest(BaseModel):
    directory_path: str