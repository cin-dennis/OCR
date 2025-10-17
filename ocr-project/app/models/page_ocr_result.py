from pydantic import BaseModel, Field


class PageOCRResult(BaseModel):
    page_number: int = Field(..., description="Page number in the document")
    text: str = Field(
        default="",
        description="Extracted OCR text from the page",
    )

    class Config:
        frozen = True
