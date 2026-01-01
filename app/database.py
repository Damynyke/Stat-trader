"""Database models using SQLModel for persistence."""
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


class PlayerDB(SQLModel, table=True):
    """Persistent player record in database."""
    __tablename__ = "players"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: str = Field(unique=True, index=True)  # StatsBomb player ID
    name: str
    base_price: float = 1000.0
    current_price: float = 1000.0
    goals: int = 0
    assists: int = 0
    minutes_played: int = 0
    is_injured: bool = False
    
    # Relationships
    wallets: List["WalletDB"] = Relationship(back_populates="player")
    trades: List["TradeDB"] = Relationship(back_populates="player")
    price_history: List["PriceHistoryDB"] = Relationship(back_populates="player")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WalletDB(SQLModel, table=True):
    """User wallet for holding player shares."""
    __tablename__ = "wallets"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    player_id: int = Field(foreign_key="players.id", index=True)
    shares_held: int = 0
    total_invested: float = 0.0
    
    # Relationship
    player: PlayerDB = Relationship(back_populates="wallets")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TradeDB(SQLModel, table=True):
    """Record of trades (buy/sell transactions)."""
    __tablename__ = "trades"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    player_id: int = Field(foreign_key="players.id", index=True)
    trade_type: str  # "buy" or "sell"
    shares: int
    price_per_share: float
    total_value: float
    
    # Relationship
    player: PlayerDB = Relationship(back_populates="trades")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionDB(SQLModel, table=True):
    """Financial transaction record."""
    __tablename__ = "transactions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    transaction_type: str  # "deposit", "withdrawal", "trade_fee"
    amount: float
    status: str = "pending"  # "pending", "completed", "failed"
    stripe_id: Optional[str] = Field(default=None, index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PriceHistoryDB(SQLModel, table=True):
    """Track price changes over time."""
    __tablename__ = "price_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id", index=True)
    price: float
    goals_delta: int = 0
    assists_delta: int = 0
    minutes_delta: int = 0
    injury_impact: bool = False
    
    # Relationship
    player: PlayerDB = Relationship(back_populates="price_history")
    
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfileDB(SQLModel, table=True):
    """User profile with KYC/AML status."""
    __tablename__ = "user_profiles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    kyc_status: str = "pending"  # "pending", "verified", "rejected"
    aml_status: str = "pending"  # "pending", "cleared", "flagged"
    total_balance: float = 0.0
    account_tier: str = "silver"  # "bronze", "silver", "gold", "platinum"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
