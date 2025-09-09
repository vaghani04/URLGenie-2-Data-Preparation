from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "url-genie-2-test"
    ERROR_COLLECTION_NAME: str = "errors"
    LLM_USAGE_COLLECTION_NAME: str = "llm_usage"

    # Gemini settings
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    
    # Vertex AI settings
    VERTEX_SERVICE_ACCOUNT_JSON: str
    VERTEX_SERVICE_PROJECT_ID: str
    VERTEX_SERVICE_REGION: str = "global"
    
    # Batch processing settings
    BATCH_SIZE: int = 500
    MAX_CONCURRENT_REQUESTS: int = 500  # Maximum concurrent HTTP requests
    OUTPUT_DIRECTORY_PATH: str = "/Users/maunikvaghani/Developer/DhiWise/URLGenie/data/Unsplash_full_dataset/URLGenie_2/final_data"

    class Config:
        env_file = ".env"


settings = Settings()
