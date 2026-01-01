"""FastAPI application with database, payments, and compliance."""
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from .models import Player, StatUpdate, Wallet, TradeRequest
from .pricing_engine import PricingEngine
from .simulator import Simulator
from .data_provider import LiveDataProvider
from .database import PlayerDB, WalletDB, TradeDB, TransactionDB, UserProfileDB, PriceHistoryDB
from .db import get_session, init_db
from .payment import PaystackPaymentService, PaystackWebhookHandler
from .compliance import KYCService, AMLService, ComplianceMiddleware
from typing import Dict, List

app = FastAPI(title="Football Trading Platform - Production Ready")

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
        from .db import SessionLocal
        with SessionLocal() as session:
            statement = select(PlayerDB)
            players = session.exec(statement).all()
        
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
        
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)


# ============ KYC/AML Endpoints ============

@app.post("/auth/register")
async def register(user_id: str, email: str, session: Session = Depends(get_session)):
    """Register new user and initiate KYC."""
    result = KYCService.verify_user(user_id, email, session)
    return result


@app.post("/kyc/submit")
async def submit_kyc(user_id: str, kyc_data: dict, session: Session = Depends(get_session)):
    """Submit KYC information."""
    result = KYCService.submit_kyc_info(user_id, kyc_data, session)
    return result


@app.get("/kyc/status/{user_id}")
async def get_kyc_status(user_id: str, session: Session = Depends(get_session)):
    """Get KYC and AML status."""
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "User not found"}
    return {
        "user_id": user_id,
        "kyc_status": profile.kyc_status,
        "aml_status": profile.aml_status,
        "account_tier": profile.account_tier,
    }


@app.get("/compliance/tier-limits/{account_tier}")
async def get_tier_limits(account_tier: str):
    """Get trading limits for account tier."""
    return KYCService.get_tier_limits(account_tier)


# ============ Payment Endpoints ============

@app.post("/payments/create-deposit-intent")
async def create_deposit_intent(user_id: str, amount: float, email: str, session: Session = Depends(get_session)):
    """Initialize a Paystack payment for deposit."""
    # Check compliance first
    compliance_check = ComplianceMiddleware.verify_transaction(user_id, amount, "deposit", session)
    if not compliance_check["allowed"]:
        return {"error": compliance_check["reason"], "status": "blocked"}
    
    return PaystackPaymentService.initialize_payment(user_id, amount, email)


@app.post("/payments/confirm-deposit")
async def confirm_deposit(user_id: str, reference: str, session: Session = Depends(get_session)):
    """Confirm Paystack payment and deposit funds."""
    result = PaystackPaymentService.process_deposit(user_id, reference, session)
    return result


@app.post("/payments/webhook")
async def paystack_webhook(request: Request, session: Session = Depends(get_session)):
    """Handle Paystack webhook events."""
    payload = await request.body()
    signature = request.headers.get("x-paystack-signature")
    
    # Verify signature
    is_valid = PaystackWebhookHandler.verify_signature(payload, signature)
    if not is_valid:
        return {"error": "Invalid signature"}
    
    import json
    event = json.loads(payload)
    event_type = event.get("event")
    
    # Route event
    if event_type == "charge.success":
        return PaystackWebhookHandler.handle_charge_success(event, session)
    elif event_type == "charge.failed":
        return PaystackWebhookHandler.handle_charge_failed(event, session)
    elif event_type == "transfer.success":
        return PaystackWebhookHandler.handle_transfer_success(event, session)
    elif event_type == "transfer.failed":
        return PaystackWebhookHandler.handle_transfer_failed(event, session)
    
    return {"success": False, "error": f"Unhandled event: {event_type}"}


# ============ Wallet & Trading Endpoints ============

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
    # Compliance check
    compliance_check = ComplianceMiddleware.verify_transaction(user_id, amount, "deposit", session)
    if not compliance_check["allowed"]:
        return {"error": compliance_check["reason"], "status": "blocked"}
    
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    transaction = TransactionDB(
        user_id=user_id,
        transaction_type="deposit",
        amount=amount,
        status="completed"
    )
    session.add(transaction)
    
    profile.total_balance += amount
    session.add(profile)
    session.commit()
    
    return {
        "status": "ok",
        "user_id": user_id,
        "new_balance": profile.total_balance,
    }


@app.post("/wallet/withdraw")
async def withdraw(user_id: str, amount: float, session: Session = Depends(get_session)):
    """Withdraw funds from wallet."""
    # Compliance check
    compliance_check = ComplianceMiddleware.verify_transaction(user_id, amount, "withdrawal", session)
    if not compliance_check["allowed"]:
        return {"error": compliance_check["reason"], "status": "blocked"}
    
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    if profile.total_balance < amount:
        return {"error": "insufficient funds"}
    
    transaction = TransactionDB(
        user_id=user_id,
        transaction_type="withdrawal",
        amount=amount,
        status="completed"
    )
    session.add(transaction)
    
    profile.total_balance -= amount
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
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    statement = select(PlayerDB).where(PlayerDB.player_id == player_id)
    player = session.exec(statement).first()
    if not player:
        return {"error": "player not found"}
    
    cost = player.current_price * shares
    
    # Compliance check
    compliance_check = ComplianceMiddleware.verify_transaction(user_id, cost, "trade", session)
    if not compliance_check["allowed"]:
        return {"error": compliance_check["reason"], "status": "blocked"}
    
    if profile.total_balance < cost:
        return {"error": "insufficient funds", "required": cost, "available": profile.total_balance}
    
    trade = TradeDB(
        user_id=user_id,
        player_id=player.id,
        trade_type="buy",
        shares=shares,
        price_per_share=player.current_price,
        total_value=cost
    )
    session.add(trade)
    
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
    statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
    profile = session.exec(statement).first()
    if not profile:
        return {"error": "wallet not found"}
    
    statement = select(PlayerDB).where(PlayerDB.player_id == player_id)
    player = session.exec(statement).first()
    if not player:
        return {"error": "player not found"}
    
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
    
    proceeds = player.current_price * shares
    
    trade = TradeDB(
        user_id=user_id,
        player_id=player.id,
        trade_type="sell",
        shares=shares,
        price_per_share=player.current_price,
        total_value=proceeds
    )
    session.add(trade)
    
    wallet.shares_held -= shares
    session.add(wallet)
    
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
