from pydantic import BaseModel, field_validator
from typing import List

MAX_TEXT_LENGTH = 50_000


class AnalyzeRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_must_be_meaningful(cls, v: str) -> str:
        stripped = v.strip() if v else ""
        if len(stripped) < 20:
            raise ValueError("Text must be at least 20 characters long.")
        if len(stripped) > MAX_TEXT_LENGTH:
            raise ValueError(f"Text must not exceed {MAX_TEXT_LENGTH:,} characters.")
        return stripped


class AnalyzeResponse(BaseModel):
    summary: str
    action_items: List[str]
    model: str
    input_length: int
