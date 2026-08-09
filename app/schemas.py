from typing import Literal

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    messages: list[str]


class Candidate(BaseModel):
    sku: str
    confidence: float = Field(ge=0.0, le=1.0)


class MatchResult(BaseModel):
    message: str
    status: Literal["matched", "ambiguous", "not_found"]
    candidates: list[Candidate]


class MatchResponse(BaseModel):
    results: list[MatchResult]
