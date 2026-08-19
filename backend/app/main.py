from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.routers import notes

app = FastAPI(
    title="AI Lecture-to-Notes System API",
    description="Backend API for transcript fetching, partitioning, note generation, and PDF export.",
    version="1.0.0"
)

# Set up CORS middleware for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(notes.router)

@app.get("/")
async def root():
    return {
        "message": "AI Lecture-to-Notes API is online.",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
