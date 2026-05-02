from pydantic import BaseModel


class PageText(BaseModel):
    page: int
    text: str


class DocumentChunk(BaseModel):
    chunk_id: str
    paper_id: str
    title: str | None = None
    page: int
    text: str
