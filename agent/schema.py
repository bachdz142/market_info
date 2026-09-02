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

DataBasis = Literal["standalone", "consolidated", "not_applicable"]
ActualProxyForecast = Literal["actual", "proxy", "forecast"]
FactOrOpinion = Literal["fact", "opinion"]


class MarketSignal(BaseModel):
    signal_type: SignalType = Field(description="Category of the raw factual signal observed.")
    summary: str = Field(description="A single factual statement — no interpretation or recommendation.")
    source_url: Optional[str] = Field(default=None, description="URL of the source the signal was drawn from, if available.")
    observed_at: str = Field(description="Date/time the underlying event occurred or was reported, or 'unknown'.")
    confidence: Confidence = Field(description="How well-supported the signal is by the source material.")
    source_code: str = Field(description="Short code identifying the source, e.g. a bank ticker (TCB, VCB, BID, MBB, ACB) or SBV/IAV/VIETSTOCK.")
    reference_period: str = Field(description="The period the data itself covers, e.g. 'Q2 2026' — distinct from observed_at (when it was reported/pulled).")
    data_basis: DataBasis = Field(description="Whether the figure is standalone, consolidated, or not_applicable (e.g. for non-financial-statement data).")
    actual_proxy_forecast: ActualProxyForecast = Field(description="Whether the figure is an actual disclosed value, a proxy, or a forecast.")
    forecast_org: Optional[str] = Field(default=None, description="The organization that produced the forecast. Required when actual_proxy_forecast is 'forecast', otherwise omitted.")
    fact_or_opinion: FactOrOpinion = Field(description="Whether this signal is a directly disclosed/reported fact, or an analyst's opinion/interpretation (per source_plan_mvp0.md's Tier 2 rule R-F07). Signals from a Tier 1 (official-disclosure) source are forced to 'fact' downstream regardless of what's produced here.")


class MarketSignalBatch(BaseModel):
    query: str
    signals: List[MarketSignal]
    generated_at: str
