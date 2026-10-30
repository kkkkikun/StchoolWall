from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class VerificationReview(BaseModel):
    decision: Literal["approved", "rejected"]
    # Reviewer confirms the visible card, random code, school and entered number match.
    challenge_matches: bool = False
    school_matches: bool = False
    student_number_matches: bool = False
    validity_checked: bool = False
    card_valid_until: date | None = None
    student_id: str | None = Field(default=None, min_length=4, max_length=32)
    reason: str = Field(default="", max_length=500)


class VerificationRevoke(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
