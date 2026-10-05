from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.resume import ResumeDocument

Page = Literal["home", "scan", "builder", "jobs", "job", "admin", "resumes", "other"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class ChatContext(BaseModel):
    page: Page = "other"
    document: ResumeDocument | None = None
    # True only in the builder, where suggested edits can be applied.
    editable: bool = False
    job_description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20_000)] | None = None
    job_id: Annotated[str, StringConstraints(max_length=64)] | None = None


class ChatRequest(BaseModel):
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=40)]
    context: ChatContext = Field(default_factory=ChatContext)
    # Signed-out users' memories live in their browser and travel with each
    # message; signed-in users' come from the database and these are ignored.
    memories: Annotated[list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]],
                        Field(max_length=30)] = []

    @model_validator(mode="after")
    def _shape(self):
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be from the user.")
        if sum(len(m.content) for m in self.messages) > 60_000:
            raise ValueError("This conversation is too long. Start a new chat.")
        return self


class MemoryOut(BaseModel):
    id: str
    text: str
