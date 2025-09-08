from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "url-genie-2"
    ERROR_COLLECTION_NAME: str = "errors"
    LLM_USAGE_COLLECTION_NAME: str = "llm_usage"

    # Gemini settings
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # Batch processing settings
    BATCH_SIZE: int = 1000
    OUTPUT_DIRECTORY_PATH: str = "/Users/maunikvaghani/Developer/DhiWise/URLGenie/data/Unsplash_full_dataset/URLGenie_2/final_data"

    class Config:
        env_file = ".env"


settings = Settings()
