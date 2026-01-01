"""FastAPI application with database persistence."""
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from .models import Player, StatUpdate, Wallet, TradeRequest
from .pricing_engine import PricingEngine
from .simulator import Simulator
from .data_provider import LiveDataProvider
from .database import PlayerDB, WalletDB, TradeDB, TransactionDB, UserProfileDB, PriceHistoryDB
from .db import get_session, init_db
from typing import Dict, List

app = FastAPI(title="Football Trading Platform - MVP with Database")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory WebSocket clients
clients: List[WebSocket] = []
pricing_engine: PricingEngine = None
sim = None
provider = None


async def broadcast(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    to_remove = []
    for ws in clients:
        try:
            await ws.send_json(message)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        clients.remove(ws)


async def pricing_callback(stat: StatUpdate):
    """Callback to update prices and broadcast to clients."""
    global pricing_engine
    if pricing_engine:
        await pricing_engine.apply_stat(stat)
        # Broadcast updated prices to all WebSocket clients
        await broadcast({
            "type": "price_update",
            "player_id": stat.player_id,
            "price": pricing_engine.prices.get(str(stat.player_id), 1000.0),
            "goals": stat.goals,
            "assists": stat.assists,
            "minutes": stat.minutes,
            "injury": stat.injury,
        })


def seed_initial_players(session: Session):
    """Initialize database with sample players."""
    sample_players = [
        ("40890", "K. Mbappé", 1000.0),
        ("20055", "L. Messi", 1000.0),
        ("40091", "K. De Bruyne", 1000.0),
        ("5203", "V. van Dijk", 1000.0),
    ]
    
    for player_id, name, base_price in sample_players:
        # Check if player already exists
        statement = select(PlayerDB).where(PlayerDB.player_id == player_id)
        existing = session.exec(statement).first()
        if not existing:
            db_player = PlayerDB(
                player_id=player_id,
                name=name,
                base_price=base_price,
                current_price=base_price
            )
            session.add(db_player)
    
    session.commit()


@app.on_event("startup")
async def startup():
    """Initialize database and start data provider."""
    global pricing_engine, provider, sim
    
    # Initialize database
    init_db()
    
    # Seed initial players
    from .db import SessionLocal
    with SessionLocal() as session:
        seed_initial_players(session)
    
    # Initialize pricing engine
    pricing_engine = PricingEngine()
    
    # Determine which data provider to use
    live_url = os.getenv("LIVE_PROVIDER_URL")
    live_provider = os.getenv("LIVE_PROVIDER")
    live_key = os.getenv("LIVE_PROVIDER_KEY")

    if live_url or (live_provider and live_key):
        provider = LiveDataProvider(pricing_callback, poll_interval=float(os.getenv("POLL_INTERVAL", 5)))
        await provider.start()
    else:
        # Fall back to simulator for development
        sim = Simulator([], pricing_callback)
        await sim.start()


@app.on_event("shutdown")
async def shutdown():
    """Stop data providers on shutdown."""
    if provider:
        await provider.stop()
    elif sim:
        await sim.stop()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/players")
async def list_players(session: Session = Depends(get_session)):
    """List all players from database."""
    statement = select(PlayerDB)
    players = session.exec(statement).all()
    return [
        {
            "id": p.player_id,
            "name": p.name,
            "price": p.current_price,
            "goals": p.goals,
            "assists": p.assists,
            "minutes": p.minutes_played,
            "injured": p.is_injured,
        }
        for p in players
    ]


@app.get("/player/{player_id}")
async def get_player(player_id: str, session: Session = Depends(get_session)):
    """Get specific player details."""
    statement = select(PlayerDB).where(PlayerDB.player_id == player_id)
    player = session.exec(statement).first()
    if not player:
        return {"error": "player not found"}
    return {
        "id": player.player_id,
        "name": player.name,
        "price": player.current_price,
        "goals": player.goals,
        "assists": player.assists,
        "minutes": player.minutes_played,
        "injured": player.is_injured,
    }


@app.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    """WebSocket endpoint for real-time price updates."""
    await ws.accept()
    clients.append(ws)
    try:
        # Get initial player snapshot
        from .db import SessionLocal
        with SessionLocal() as session:
            statement = select(PlayerDB)
            players = session.exec(statement).all()
        
        # Send initial snapshot
        await ws.send_json({
            "type": "snapshot",
            "players": [
                {
                    "id": p.player_id,
                    "name": p.name,
                    "price": p.current_price,
                    "goals": p.goals,
                    "assists": p.assists,
                }
                for p in players
            ]
        })
        
        # Keep connection alive
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)


@app.post("/wallet/create")
async def create_wallet(user_id: str, session: Session = Depends(get_session)):
    """Create a new wallet for a user."""
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    existing = session.exec(statement).first()
    if existing:
        return {"error": "wallet already exists"}
    
    profile = UserProfileDB(user_id=user_id, email=f"{user_id}@example.com")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    return {
        "user_id": profile.user_id,
        "balance": profile.total_balance,
        "kyc_status": profile.kyc_status,
    }


@app.get("/wallet/{user_id}")
async def get_wallet(user_id: str, session: Session = Depends(get_session)):
    """Get user wallet information."""
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    return {
        "user_id": profile.user_id,
        "balance": profile.total_balance,
        "kyc_status": profile.kyc_status,
        "account_tier": profile.account_tier,
    }


@app.post("/wallet/deposit")
async def deposit(user_id: str, amount: float, session: Session = Depends(get_session)):
    """Deposit funds to wallet."""
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    # Create transaction record
    transaction = TransactionDB(
        user_id=user_id,
        transaction_type="deposit",
        amount=amount,
        status="completed"
    )
    session.add(transaction)
    
    # Update balance
    profile.total_balance += amount
    session.add(profile)
    session.commit()
    
    return {
        "status": "ok",
        "user_id": user_id,
        "new_balance": profile.total_balance,
    }


@app.post("/trade/buy")
async def buy_shares(user_id: str, player_id: str, shares: int, session: Session = Depends(get_session)):
    """Buy shares of a player."""
    # Get user wallet
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    # Get player
    statement = select(PlayerDB).where(PlayerDB.player_id == player_id)
    player = session.exec(statement).first()
    if not player:
        return {"error": "player not found"}
    
    # Calculate cost
    cost = player.current_price * shares
    if profile.total_balance < cost:
        return {"error": "insufficient funds", "required": cost, "available": profile.total_balance}
    
    # Create trade record
    trade = TradeDB(
        user_id=user_id,
        player_id=player.id,
        trade_type="buy",
        shares=shares,
        price_per_share=player.current_price,
        total_value=cost
    )
    session.add(trade)
    
    # Update user wallet
    wallet_statement = select(WalletDB).where(
        (WalletDB.user_id == user_id) & (WalletDB.player_id == player.id)
    )
    wallet = session.exec(wallet_statement).first()
    
    if wallet:
        wallet.shares_held += shares
        wallet.total_invested += cost
    else:
        wallet = WalletDB(
            user_id=user_id,
            player_id=player.id,
            shares_held=shares,
            total_invested=cost
        )
        session.add(wallet)
    
    # Deduct from balance
    profile.total_balance -= cost
    session.add(profile)
    session.commit()
    
    return {
        "status": "ok",
        "trade_type": "buy",
        "shares": shares,
        "price_per_share": player.current_price,
        "total_spent": cost,
        "remaining_balance": profile.total_balance,
    }


@app.post("/trade/sell")
async def sell_shares(user_id: str, player_id: str, shares: int, session: Session = Depends(get_session)):
    """Sell shares of a player."""
    # Get user wallet
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    # Get player
    statement = select(PlayerDB).where(PlayerDB.player_id == player_id)
    player = session.exec(statement).first()
    if not player:
        return {"error": "player not found"}
    
    # Check if user has sufficient shares
    wallet_statement = select(WalletDB).where(
        (WalletDB.user_id == user_id) & (WalletDB.player_id == player.id)
    )
    wallet = session.exec(wallet_statement).first()
    
    if not wallet or wallet.shares_held < shares:
        return {
            "error": "insufficient shares",
            "held": wallet.shares_held if wallet else 0,
            "requested": shares
        }
    
    # Calculate proceeds
    proceeds = player.current_price * shares
    
    # Create trade record
    trade = TradeDB(
        user_id=user_id,
        player_id=player.id,
        trade_type="sell",
        shares=shares,
        price_per_share=player.current_price,
        total_value=proceeds
    )
    session.add(trade)
    
    # Update wallet
    wallet.shares_held -= shares
    session.add(wallet)
    
    # Add to balance
    profile.total_balance += proceeds
    session.add(profile)
    session.commit()
    
    return {
        "status": "ok",
        "trade_type": "sell",
        "shares": shares,
        "price_per_share": player.current_price,
        "proceeds": proceeds,
        "new_balance": profile.total_balance,
    }


@app.get("/wallet/{user_id}/positions")
async def get_positions(user_id: str, session: Session = Depends(get_session)):
    """Get all player positions held by user."""
    statement = select(WalletDB).where(WalletDB.user_id == user_id)
    wallets = session.exec(statement).all()
    
    positions = []
    for w in wallets:
        player = session.get(PlayerDB, w.player_id)
        if player:
            current_value = player.current_price * w.shares_held
            positions.append({
                "player_id": player.player_id,
                "player_name": player.name,
                "shares": w.shares_held,
                "avg_buy_price": w.total_invested / w.shares_held if w.shares_held > 0 else 0,
                "current_price": player.current_price,
                "current_value": current_value,
                "unrealized_pnl": current_value - w.total_invested,
            })
    
    return {
        "user_id": user_id,
        "positions": positions,
        "total_value": sum(p["current_value"] for p in positions),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
