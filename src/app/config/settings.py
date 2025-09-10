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
    OUTPUT_DIRECTORY_PATH: str = "/Users/maunikvaghani/Developer/DhiWise/URLGenie/data/Unsplash_full_dataset/URLGenie_2/final_data/"
    
    # Batch API settings
    # BATCH_SIZE_FOR_BATCH_API: int = 200  # Batch size for Gemini Batch API processing
    VERTEX_AI_ENABLED: bool = False  # Use Vertex AI if True, Gemini API if False

    # JSONAL settings
    JSONAL_OUTPUT_DIRECOTRY_PATH: str = "/Users/maunikvaghani/Developer/DhiWise/URLGenie/data/Unsplash_full_dataset/URLGenie_2/final_data/jsonal_files/photos_1_50"
    JSONL_BATCH_SIZE: int = 700  # Batch size for JSONL files creation (200-800 range)

    class Config:
        env_file = ".env"


settings = Settings()
