from pydantic import BaseModel, ConfigDict

class SupplyItemCreate(BaseModel):
    item_code: str
    name: str
    category: str = "consumable"
    unit: str = "piece"
    stock_qty: int = 0
    min_alert_qty: int = 10
    cost_price: float = 0.0

class SupplyItemResponse(SupplyItemCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)
