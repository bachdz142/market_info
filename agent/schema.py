from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SignalType = Literal[
    "price_change",
    "demand_shift",
    "competitor_activity",
    "availability",
    "other",
]

Confidence = Literal["low", "medium", "high"]


class MarketSignal(BaseModel):
    signal_type: SignalType = Field(description="Category of the raw factual signal observed.")
    summary: str = Field(description="A single factual statement — no interpretation or recommendation.")
    source_url: Optional[str] = Field(default=None, description="URL of the source the signal was drawn from, if available.")
    observed_at: str = Field(description="Date/time the underlying event occurred or was reported, or 'unknown'.")
    confidence: Confidence = Field(description="How well-supported the signal is by the source material.")


class MarketSignalBatch(BaseModel):
    query: str
    signals: List[MarketSignal]
    generated_at: str
