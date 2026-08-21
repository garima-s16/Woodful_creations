from pydantic import BaseModel
from typing import Optional


class LookupBase(BaseModel):
    name: str
    description: Optional[str] = None


class LookupCreate(LookupBase):
    pass


class LookupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class LookupResponse(LookupBase):
    id: int

    class Config:
        from_attributes = True
