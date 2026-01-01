import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .models import Player, StatUpdate, Wallet, TradeRequest
from .pricing_engine import PricingEngine
from .simulator import Simulator
from .data_provider import LiveDataProvider
from typing import Dict, List

app = FastAPI(title="Football Trading Platform - MVP Sandbox")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores for MVP
players: Dict[str, Player] = {}
wallets: Dict[str, Wallet] = {}
clients: List[WebSocket] = []
pricing_engine: PricingEngine = None


async def broadcast(message: dict):
    to_remove = []
    for ws in clients:
        try:
            await ws.send_json(message)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        clients.remove(ws)


async def pricing_callback(stat: StatUpdate):
    """Callback to update prices via PricingEngine and broadcast."""
    global pricing_engine
    if pricing_engine:
        await pricing_engine.apply_stat(stat)
        # Broadcast updated prices to all WebSocket clients
        await broadcast({
            "type": "price_update",
            "player_id": stat.player_id,
            "price": pricing_engine.prices.get(str(stat.player_id), 1000.0)
        })


def seed_players():
    sample = [
        ("p1", "K. Mbappé", "FW", "PSG"),
        ("p2", "L. Messi", "FW", "Inter Miami"),
        ("p3", "K. De Bruyne", "MF", "Man City"),
        ("p4", "V. van Dijk", "DF", "Liverpool"),
    ]
    for pid, name, pos, team in sample:
        players[pid] = Player(id=pid, name=name, position=pos, team=team, price=1.0)


seed_players()

pricing_engine = PricingEngine()
sim = Simulator(list(players.values()), pricing_callback)
provider = None


@app.on_event("startup")
async def startup():
    # If LIVE_PROVIDER_URL or LIVE_PROVIDER/LIVE_PROVIDER_KEY are configured,
    # start the LiveDataProvider. Otherwise fall back to simulator.
    global provider
    live_url = os.getenv("LIVE_PROVIDER_URL")
    live_provider = os.getenv("LIVE_PROVIDER")
    live_key = os.getenv("LIVE_PROVIDER_KEY")

    if live_url or (live_provider and live_key):
        provider = LiveDataProvider(pricing_callback, poll_interval=float(os.getenv("POLL_INTERVAL", 5)))
        await provider.start()
    else:
        await sim.start()


@app.on_event("shutdown")
async def shutdown():
    if provider:
        await provider.stop()
    else:
        await sim.stop()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/players")
async def list_players():
    return [p.dict() for p in players.values()]


@app.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        # send initial snapshot
        await ws.send_json({"type": "snapshot", "players": [p.dict() for p in players.values()]})
        while True:
            # keep connection alive; no client messages expected for now
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)


@app.post("/wallet/deposit")
async def deposit(wallet: Wallet):
    w = wallets.get(wallet.user_id) or Wallet(user_id=wallet.user_id, balance=0.0)
    w.balance += wallet.balance
    wallets[wallet.user_id] = w
    return w


@app.get("/wallet/{user_id}")
async def get_wallet(user_id: str):
    return wallets.get(user_id) or Wallet(user_id=user_id, balance=0.0)


@app.post("/trade/buy")
async def buy(tr: TradeRequest):
    player = players.get(tr.player_id)
    if not player:
        return {"error": "player not found"}
    w = wallets.get(tr.user_id) or Wallet(user_id=tr.user_id, balance=0.0)
    cost = player.price * tr.quantity
    if w.balance < cost:
        return {"error": "insufficient funds"}
    w.balance -= cost
    wallets[tr.user_id] = w
    # For MVP we do not track positions; assume trade succeeds
    return {"status": "ok", "spent": cost, "balance": w.balance}


@app.post("/trade/sell")
async def sell(tr: TradeRequest):
    player = players.get(tr.player_id)
    if not player:
        return {"error": "player not found"}
    w = wallets.get(tr.user_id) or Wallet(user_id=tr.user_id, balance=0.0)
    proceeds = player.price * tr.quantity
    w.balance += proceeds
    wallets[tr.user_id] = w
    return {"status": "ok", "proceeds": proceeds, "balance": w.balance}
