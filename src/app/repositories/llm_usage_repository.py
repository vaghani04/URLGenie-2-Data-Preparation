from fastapi import Depends

from src.app.config.database import mongodb_database


class LLMUsageRepository:
    def __init__(
        self, collection=Depends(mongodb_database.get_llm_usage_collection)
    ):
        self.collection = collection

    async def add_llm_usage(self, llm_usage: dict):
        """
        Add LLM usage record to the database.

        Args:
            llm_usage: Dictionary containing LLM usage information
        """
        # Make a copy to avoid modifying the original dict (which would add ObjectId)
        llm_usage_copy = llm_usage.copy()

        await self.collection.insert_one(llm_usage_copy)


llm_usage_repository = LLMUsageRepository()
