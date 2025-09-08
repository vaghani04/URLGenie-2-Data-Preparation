from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from src.app.config.database import mongodb_database
from src.app.routes.generate_description_route import router as generate_description_router
from src.app.routes.generate_batch_description_route import router as generate_batch_description_router
import os

os.makedirs("intermediate_outputs", exist_ok=True)

@asynccontextmanager
async def db_lifespan(app: FastAPI):
    mongodb_database.connect()
    yield
    mongodb_database.disconnect()


app = FastAPI(
    title="API",
    description="API for URLGenie",
    version="1.0.0",
    lifespan=db_lifespan,
)


app.include_router(generate_description_router, prefix="/api/v1", tags=["generate-description"])
app.include_router(generate_batch_description_router, prefix="/api/v1", tags=["generate-batch-description"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["struct_logs/*", "intermediate_outputs/*"],
    )