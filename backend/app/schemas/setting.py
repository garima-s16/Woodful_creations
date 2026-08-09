from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SettingBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectStatusCreate(SettingBase):
    display_order: Optional[int] = 0

class ProjectStatusResponse(SettingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PriorityCreate(SettingBase):
    pass

class PriorityResponse(SettingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaymentModeCreate(SettingBase):
    pass

class PaymentModeResponse(SettingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LeadSourceCreate(SettingBase):
    pass

class LeadSourceResponse(SettingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProjectTypeCreate(SettingBase):
    pass

class ProjectTypeResponse(SettingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ExpenseCategoryCreate(SettingBase):
    pass

class ExpenseCategoryResponse(SettingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
