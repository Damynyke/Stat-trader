# Football Trading Platform - Real-Money Player Share Marketplace

A real-time player trading platform built with FastAPI, SQLModel, Stripe, and WebSockets. Users buy and sell fractional shares of football (soccer) players based on live performance data.

## Features

### MVP Features (Completed ✅)
- Real-time player price updates based on StatsBomb live event data  
- Dynamic pricing engine (goals +100, assists +50, minutes +0.1, injury ×0.7)  
- WebSocket live price feed for all connected clients  
- In-memory simulator for development/testing  
- Comprehensive pytest test suite (12 passing tests)  

### Production Features (Implemented ✅)
- **PostgreSQL Database** - Persistent storage for players, wallets, trades, transactions  
- **SQLModel ORM** - Type-safe database models with Pydantic validation  
- **Stripe Integration** - Real-money deposit/withdrawal processing  
- **KYC Verification** - Know Your Customer (KYC) compliance system with tiers  
- **AML Monitoring** - Anti-Money Laundering detection and flagging  
- **User Wallets** - Manage balance, positions, trading history  
- **Position Tracking** - Maintain player share holdings and profit/loss calculations  

## Architecture

```
backend/
├── app/
│   ├── main_production.py     # FastAPI app with all features
│   ├── models.py              # Pydantic models (deprecated, replaced by SQLModel)
│   ├── database.py            # SQLModel database definitions
│   ├── db.py                  # Database connection & sessions
│   ├── pricing_engine.py      # Dynamic price calculation engine
│   ├── payment.py             # Stripe payment processing
│   ├── compliance.py          # KYC/AML compliance layer
│   ├── data_provider.py       # Live data adapter (StatsBomb, etc.)
│   ├── simulator.py           # Development simulator
│   └── main.py                # Original MVP app (deprecated)
│
├── tests/
│   └── test_integration.py    # Pytest suite (12 tests)
│
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
└── README.md
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **API Framework** | FastAPI + Uvicorn |
| **Database** | PostgreSQL + SQLModel (SQLAlchemy ORM) |
| **Real-time** | WebSockets |
| **Payments** | Stripe API |
| **Live Data** | StatsBomb API |
| **Testing** | pytest + pytest-asyncio |
| **Python** | 3.14+ |

## Installation

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Initialize Database
```bash
python -c "from app.db import init_db; init_db()"
```

### 4. Run Server
```bash
# Development (SQLite)
python -m uvicorn app.main_production:app --reload

# Production (PostgreSQL)
python -m uvicorn app.main_production:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health & Players
```
GET    /health                 - Health check
GET    /players                - List all players
GET    /player/{player_id}     - Get player details
WS     /ws/prices              - Real-time price updates
```

### Authentication & Compliance
```
POST   /auth/register          - Register user (initiate KYC)
POST   /kyc/submit             - Submit KYC information
GET    /kyc/status/{user_id}   - Get KYC/AML status
GET    /compliance/tier-limits/{tier} - Get trading limits
```

### Payments
```
POST   /payments/create-deposit-intent      - Create Stripe payment
POST   /payments/confirm-deposit            - Confirm & process deposit
POST   /payments/webhook                    - Stripe webhook handler
```

### Wallet & Trading
```
POST   /wallet/create          - Create wallet
GET    /wallet/{user_id}       - Get wallet info
POST   /wallet/deposit         - Deposit funds
POST   /wallet/withdraw        - Withdraw funds
POST   /trade/buy              - Buy player shares
POST   /trade/sell             - Sell player shares
GET    /wallet/{user_id}/positions - View holdings
```

## Testing

### Run Pytest Suite (12 tests)
```bash
pytest tests/test_integration.py -v

# All 12 tests pass:
# ✅ TestStatsBombParser (4 tests)
# ✅ TestPricingEngine (7 tests)
# ✅ TestIntegration (1 test)
```

## Pricing Model

Dynamic pricing based on live performance:
```
price_delta = (goals × 100) + (assists × 50) + (minutes × 0.1)
if injured: final_price = base_price × 0.7
else: final_price = base_price + price_delta
```

## KYC/AML Compliance

### Account Tiers
| Tier | Daily Deposit | Daily Withdrawal |
|------|---------------|------------------|
| Bronze | $1,000 | $500 |
| Silver | $10,000 | $5,000 |
| Gold | $100,000 | $50,000 |
| Platinum | $1,000,000 | $500,000 |

### Verification Flow
1. User registers → `kyc_status = pending`
2. Submits documents → Verified or Rejected
3. On approval → Assigned to tier
4. AML monitoring on every transaction

## Database Models

- **PlayerDB** - Players with dynamic pricing
- **WalletDB** - User share holdings
- **TradeDB** - Buy/sell transaction history
- **TransactionDB** - Deposit/withdrawal records
- **UserProfileDB** - User profiles with KYC/AML status
- **PriceHistoryDB** - Historical price tracking

## Deployment

### Environment Variables
```
DATABASE_URL=postgresql://user:password@localhost/trading_platform
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
LIVE_PROVIDER=statsbomb
ENV=production
```

## Security
✅ CORS middleware  
✅ Stripe PCI compliance  
✅ KYC/AML checks on all transactions  
✅ SQL injection prevention (SQLModel)  
✅ Environment-based secrets  
✅ HTTPS in production  

## What's Next

- [ ] Docker containerization
- [ ] Alembic schema migrations
- [ ] Advanced analytics dashboard
- [ ] Mobile app
- [ ] Options/futures trading
- [ ] Community tournaments
