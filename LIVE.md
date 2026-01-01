Local Live-Data Testing

This file explains how to test the LiveData integration locally using the included mock provider.

1) Configure environment
- Copy `.env.example` to `.env` or set env vars in your shell. Example key values:

```text
POLL_INTERVAL=2
LIVE_PROVIDER_URL=http://localhost:8001/feed
```

2) Start the mock provider (serves `/feed`):

```bash
uvicorn backend.mock_provider:app --port 8001 --reload
```

3) Start the backend (port 8000):

```bash
uvicorn backend.app.main:app --reload
```

4) Open the demo frontend
- Open `frontend/index.html` in your browser. If the frontend is served from the same host:port as the backend, it will connect automatically; otherwise open the HTML file and the page will connect to the backend websocket for price updates.

Notes
- The mock provider returns randomized stat updates for sample players. The backend's `LiveDataProvider` polls `LIVE_PROVIDER_URL` and maps returned objects to `StatUpdate` entries used by the pricing engine.
- To integrate a real provider replace or extend `backend/app/data_provider.py` with provider-specific parsing and authentication.

Sportradar
- To use Sportradar set the following environment variables before starting the backend:

```text
LIVE_PROVIDER=sportradar
SPORTRADAR_API_KEY=your_sportradar_key_here
SPORTRADAR_ENDPOINT=https://api.sportradar.com/<service>/<version>/<resource>?api_key=YOUR_KEY
```

- The built-in adapter will attempt to map common player-stat arrays to the MVP's
	`StatUpdate` shape, but you should update `backend/app/data_provider.py` when
	integrating specific Sportradar resources for accurate field mapping and to
	obey rate limits.

StatsBomb
- To use StatsBomb set the following environment variables before starting the backend:

```text
LIVE_PROVIDER=statsbomb
STATSBOMB_API_KEY=your_statsbomb_key_here
STATSBOMB_ENDPOINT=https://api.statsbomb.com/<service>/<version>/<resource>
```

- The adapter aggregates `events` where possible to compute simple per-player stats
	(goals, assists, minutes seen in events, and injury-like events). For reliable
	production behavior adapt `backend/app/data_provider.py` to the exact StatsBomb
	resource you use and add rate-limit handling.
