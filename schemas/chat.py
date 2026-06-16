from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int
    message: str = Field(..., min_length=1, max_length=500)
    use_cache: bool = Field(default=True)
    save_history: bool = Field(default=True)


class QuickReplyRequest(BaseModel):
    message: str
