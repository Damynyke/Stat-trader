from typing import Optional
from pydantic import BaseModel


class Player(BaseModel):
    id: str
    name: str
    position: Optional[str] = None
    team: Optional[str] = None
    price: float = 1.0


class StatUpdate(BaseModel):
    player_id: str
    goals: int = 0
    assists: int = 0
    minutes: int = 0
    injury: bool = False


class TradeRequest(BaseModel):
    user_id: str
    player_id: str
    quantity: int


class Wallet(BaseModel):
    user_id: str
    balance: float = 0.0
