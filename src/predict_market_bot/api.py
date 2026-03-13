import asyncio
import json
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from predict_market_bot.orchestrator import PipelineOrchestrator

app = FastAPI(title="Polymarket Prediction Bot API")

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessRequest(BaseModel):
    url: str

def extract_slug(url: str) -> Optional[str]:
    """Extract event slug from Polymarket URL."""
    # Example: https://polymarket.com/event/will-the-fed-cut-rates-in-march
    if "polymarket.com/event/" in url:
        return url.split("/event/")[1].split("?")[0].rstrip("/")
    return None

@app.get("/")
async def root():
    return {"status": "ok", "message": "Polymarket Prediction Bot API is running"}

@app.get("/process")
async def process_market(url: str):
    slug = extract_slug(url)
    if not slug:
        return {"error": "Invalid Polymarket URL. Must be an /event/ URL."}

    orchestrator = PipelineOrchestrator()

    async def event_generator():
        queue = asyncio.Queue()

        async def callback(payload):
            await queue.put(payload)

        # Run orchestrator in a background task
        task = asyncio.create_task(orchestrator.run(slug=slug, callback=callback))

        while not task.done() or not queue.empty():
            try:
                # Wait for progress updates with a timeout
                payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"data: {json.dumps(payload)}\n\n"
            except asyncio.TimeoutError:
                if task.done():
                    break
                continue

        if task.exception():
            yield f"data: {json.dumps({'stage': 'ERROR', 'data': {'message': str(task.exception())}})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
