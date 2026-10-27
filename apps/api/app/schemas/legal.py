from pydantic import BaseModel


class LegalVersionsResponse(BaseModel):
    terms: str
    privacy_notice: str
