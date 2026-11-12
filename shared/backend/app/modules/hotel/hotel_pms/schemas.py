"""Pydantic schemas for Hotel PMS."""
from pydantic import BaseModel


class RoomCreate(BaseModel):
    room_number: str
    room_type: str = "غرفة قياسية Standard"
    floor: str = "الدور الأول"
    bed_type: str = "King Size"
    max_guests: int = 2
    base_rate: float = 1800.0
    status: str = "vacant_clean"
    amenities: str = "إطلالة على النيل / المدينة، واي فاي سريع، ميني بار"


class RoomStatusUpdate(BaseModel):
    status: str


class ReservationCreate(BaseModel):
    guest_name: str
    guest_phone: str
    guest_passport: str
    room_number: str
    check_in_date: str
    check_out_date: str
    nights: int = 1
    room_rate: float
    paid_amount: float = 0.0


class CheckinRequest(BaseModel):
    initial_deposit: float = 0.0


class CheckoutRequest(BaseModel):
    settle_all: bool = True
