from typing import Any, Callable, Dict, List, Union, Awaitable
import asyncio
import json
import sys
from pydantic import BaseModel


class StatUpdate(BaseModel):
    player_id: str
    goals: int = 0
    assists: int = 0
    minutes: int = 0
    injury: bool = False


async def process_statsbomb(data: Any, callback: Callable[[StatUpdate], Awaitable[None]]):
    """Process StatsBomb match `events` payload and call `callback` for each aggregated StatUpdate.

    - `data` may be a dict with an `events` key or a raw list of events.
    - `callback` is an async function accepting a `StatUpdate`.
    """
    events: List[Any] = []
    if isinstance(data, dict):
        events = data.get("events") or data.get("event") or []
    elif isinstance(data, list):
        events = data

    by_player: Dict[str, Dict[str, Any]] = {}

    def _ensure(pid: Union[str, int]):
        if pid is None:
            return None
        pid_s = str(pid)
        return by_player.setdefault(pid_s, {"goals": 0, "assists": 0, "minutes": 0, "injury": False})

    for ev in events:
        if not isinstance(ev, dict):
            continue

        # minute (defensive)
        try:
            minute = int(ev.get("minute") or ev.get("min") or 0)
        except Exception:
            minute = 0

        # normalize type name
        t = ev.get("type") or {}
        tname = ""
        if isinstance(t, dict):
            tname = (t.get("name") or "").lower()
        else:
            tname = str(t).lower() if t else ""

        # main player
        player_obj = ev.get("player") or ev.get("player_id") or ev.get("playerId")
        pid = None
        if isinstance(player_obj, dict):
            pid = player_obj.get("id") or player_obj.get("player_id")
        else:
            pid = player_obj

        rec = _ensure(pid)

        # goal detection
        if "goal" in tname or "shot - goal" in tname or tname.startswith("goal"):
            if rec is not None:
                rec["goals"] += 1
                rec["minutes"] = max(rec["minutes"], minute)

        # injury detection
        if "injur" in tname or "injury" in tname or "injured" in tname:
            if rec is not None:
                rec["injury"] = True

        # related players (assists etc)
        related = ev.get("related_players") or ev.get("relatedPlayers") or ev.get("related") or []
        if isinstance(related, list):
            for r in related:
                if not isinstance(r, dict):
                    continue
                role = (r.get("role") or r.get("type") or "").lower()
                rplayer = r.get("player") or r.get("player_id") or r.get("id")
                rid = None
                if isinstance(rplayer, dict):
                    rid = rplayer.get("id") or rplayer.get("player_id")
                else:
                    rid = rplayer
                rrec = _ensure(rid)
                if rrec is None:
                    continue
                if "assist" in role or "assister" in role:
                    rrec["assists"] += 1
                    rrec["minutes"] = max(rrec["minutes"], minute)

    # emit StatUpdate
    for pid, stats in by_player.items():
        stat = StatUpdate(
            player_id=str(pid),
            goals=int(stats.get("goals", 0)),
            assists=int(stats.get("assists", 0)),
            minutes=int(stats.get("minutes", 0)),
            injury=bool(stats.get("injury", False)),
        )
        await callback(stat)


# simple CLI tester
async def _print_cb(stat: StatUpdate):
    # Use model_dump_json for Pydantic v2 compatibility
    try:
        print(stat.model_dump_json())
    except Exception:
        # fallback for older pydantic versions
        print(stat.json())


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/app/data_provider.py <statsbomb_match.json>")
        sys.exit(2)
    path = sys.argv[1]
    payload = _load_json(path)
    asyncio.run(process_statsbomb(payload, _print_cb))


class LiveDataProvider:
    """Live data provider for polling external sources."""
    
    def __init__(self, callback, poll_interval: int = 5):
        """Initialize live data provider.
        
        Args:
            callback: Async callback function to handle StatUpdate
            poll_interval: Seconds between polls
        """
        self.callback = callback
        self.poll_interval = poll_interval
        self.running = False
        self.task = None
    
    async def start(self):
        """Start polling for live data."""
        self.running = True
        self.task = asyncio.create_task(self._poll_loop())
    
    async def stop(self):
        """Stop polling for live data."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
    
    async def _poll_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                await asyncio.sleep(self.poll_interval)
                # In production, fetch from external API here
                # For now, this is a placeholder
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in poll loop: {e}")
                await asyncio.sleep(self.poll_interval)


