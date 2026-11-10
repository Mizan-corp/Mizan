from pydantic import BaseModel, ConfigDict

class CostCenterCreate(BaseModel):
    code: str
    name: str
    center_type: str = "cost_center"
    budget: float = 0.0

class CostCenterResponse(CostCenterCreate):
    id: int
    actual_spent: float
    model_config = ConfigDict(from_attributes=True)
