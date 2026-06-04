"""
FastAPI backend — routes all agent requests.

Endpoints:
  POST /agent/rfp          -> RFP & Discovery Prep agent
  POST /agent/competitive  -> Competitive Intelligence agent
  POST /feedback           -> Capture user rating + edit flags
  GET  /health             -> health check
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import traceback

from app.agents import rfp_agent, competitive_intel_agent

app = FastAPI(
    title="Zyter Internal Agent Sandbox",
    description="Sprint 1 prototype — local RAG pipeline over Zyter knowledge base",
    version="0.1.0",
)


# ── Request / Response models ─────────────────────────────────────────────────

class RFPRequest(BaseModel):
    rfp_text: str
    user_id: str = "anonymous"


class CompetitiveRequest(BaseModel):
    competitor_name: str
    deal_context: Optional[str] = ""
    user_id: str = "anonymous"


class FeedbackRequest(BaseModel):
    user_id: str
    agent: str                  # "rfp_agent" | "ci_agent"
    rating: int                 # 1-5
    edited_sections: list[str] = []


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/agent/rfp")
def run_rfp_agent(req: RFPRequest):
    try:
        result = rfp_agent.run({
            "rfp_text": req.rfp_text,
            "user_id": req.user_id,
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {traceback.format_exc()}")


@app.post("/agent/competitive")
def run_ci_agent(req: CompetitiveRequest):
    try:
        result = competitive_intel_agent.run({
            "competitor_name": req.competitor_name,
            "deal_context": req.deal_context,
            "user_id": req.user_id,
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {traceback.format_exc()}")


@app.post("/feedback")
def capture_feedback(req: FeedbackRequest):
    try:
        rfp_agent.capture_feedback(req.user_id, req.rating, req.edited_sections)
        return {"status": "recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
