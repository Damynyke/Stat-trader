"""
StatsBomb API Client for live match data
Fetches real player performance data and converts to price updates
"""
import os
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# StatsBomb API configuration
STATSBOMB_API_URL = os.getenv("STATSBOMB_API_URL", "https://data.statsbomb.com/api/v4")
STATSBOMB_USER = os.getenv("STATSBOMB_USER", "")
STATSBOMB_PASSWORD = os.getenv("STATSBOMB_PASSWORD", "")

# For demo/development, use StatsBomb's free open data
STATSBOMB_OPEN_DATA_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"


class PlayerStats(BaseModel):
    player_id: str
    player_name: str
    goals: int = 0
    assists: int = 0
    minutes: int = 0
    shots: int = 0
    passes: int = 0
    tackles: int = 0
    interceptions: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0


class MatchEvent(BaseModel):
    event_id: str
    event_type: str
    player_id: Optional[str]
    player_name: Optional[str]
    minute: int
    second: int
    team: str


class StatsBombClient:
    """Client for fetching StatsBomb data"""
    
    def __init__(self, use_open_data: bool = True):
        self.use_open_data = use_open_data
        self.base_url = STATSBOMB_OPEN_DATA_URL if use_open_data else STATSBOMB_API_URL
        self.auth = (STATSBOMB_USER, STATSBOMB_PASSWORD) if not use_open_data else None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get_competitions(self) -> List[Dict]:
        """Fetch available competitions"""
        client = await self._get_client()
        if self.use_open_data:
            url = f"{self.base_url}/competitions.json"
            resp = await client.get(url)
        else:
            url = f"{self.base_url}/competitions"
            resp = await client.get(url, auth=self.auth)
        
        resp.raise_for_status()
        return resp.json()
    
    async def get_matches(self, competition_id: int, season_id: int) -> List[Dict]:
        """Fetch matches for a competition/season"""
        client = await self._get_client()
        if self.use_open_data:
            url = f"{self.base_url}/matches/{competition_id}/{season_id}.json"
        else:
            url = f"{self.base_url}/competitions/{competition_id}/seasons/{season_id}/matches"
        
        resp = await client.get(url, auth=self.auth if not self.use_open_data else None)
        resp.raise_for_status()
        return resp.json()
    
    async def get_match_events(self, match_id: int) -> List[Dict]:
        """Fetch events for a specific match"""
        client = await self._get_client()
        if self.use_open_data:
            url = f"{self.base_url}/events/{match_id}.json"
        else:
            url = f"{self.base_url}/matches/{match_id}/events"
        
        resp = await client.get(url, auth=self.auth if not self.use_open_data else None)
        resp.raise_for_status()
        return resp.json()
    
    async def get_lineups(self, match_id: int) -> List[Dict]:
        """Fetch lineups for a match"""
        client = await self._get_client()
        if self.use_open_data:
            url = f"{self.base_url}/lineups/{match_id}.json"
        else:
            url = f"{self.base_url}/matches/{match_id}/lineups"
        
        resp = await client.get(url, auth=self.auth if not self.use_open_data else None)
        resp.raise_for_status()
        return resp.json()
    
    def parse_events_to_stats(self, events: List[Dict]) -> Dict[str, PlayerStats]:
        """Parse raw events into player statistics"""
        player_stats: Dict[str, PlayerStats] = {}
        
        for event in events:
            player = event.get("player")
            if not player:
                continue
            
            player_id = str(player.get("id"))
            player_name = player.get("name", "Unknown")
            
            if player_id not in player_stats:
                player_stats[player_id] = PlayerStats(
                    player_id=player_id,
                    player_name=player_name
                )
            
            stats = player_stats[player_id]
            event_type = event.get("type", {}).get("name", "")
            
            # Update stats based on event type
            if event_type == "Shot":
                stats.shots += 1
                shot_outcome = event.get("shot", {}).get("outcome", {}).get("name", "")
                if shot_outcome == "Goal":
                    stats.goals += 1
            
            elif event_type == "Pass":
                stats.passes += 1
                # Check if it was an assist
                if event.get("pass", {}).get("goal_assist"):
                    stats.assists += 1
            
            elif event_type == "Tackle":
                stats.tackles += 1
            
            elif event_type == "Interception":
                stats.interceptions += 1
            
            elif event_type == "Foul Committed":
                stats.fouls += 1
            
            elif event_type == "Bad Behaviour":
                card = event.get("bad_behaviour", {}).get("card", {}).get("name", "")
                if "Yellow" in card:
                    stats.yellow_cards += 1
                elif "Red" in card:
                    stats.red_cards += 1
            
            # Track minutes (approximate from event timestamp)
            minute = event.get("minute", 0)
            if minute > stats.minutes:
                stats.minutes = minute
        
        return player_stats


class LiveDataFeed:
    """
    Simulates live data feed by streaming events from a completed match
    In production, this would connect to StatsBomb's live data API
    """
    
    def __init__(self, statsbomb_client: StatsBombClient, pricing_engine, broadcast_callback):
        self.client = statsbomb_client
        self.pricing_engine = pricing_engine
        self.broadcast_callback = broadcast_callback
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.current_match_id: Optional[int] = None
        self.event_index = 0
        self.events: List[Dict] = []
    
    async def load_match(self, match_id: int):
        """Load events for a match"""
        self.events = await self.client.get_match_events(match_id)
        self.current_match_id = match_id
        self.event_index = 0
        logger.info(f"Loaded {len(self.events)} events for match {match_id}")
    
    async def start(self, match_id: Optional[int] = None):
        """Start streaming events"""
        if match_id:
            await self.load_match(match_id)
        
        if not self.events:
            logger.warning("No events loaded, using demo match")
            # Load a demo match from open data (2018 World Cup Final)
            try:
                await self.load_match(8658)
            except Exception as e:
                logger.error(f"Failed to load demo match: {e}")
                return
        
        self._running = True
        self._task = asyncio.create_task(self._stream_events())
        logger.info("Live data feed started")
    
    async def stop(self):
        """Stop streaming"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Live data feed stopped")
    
    async def _stream_events(self):
        """Stream events one by one with delay to simulate live data"""
        while self._running and self.event_index < len(self.events):
            event = self.events[self.event_index]
            self.event_index += 1
            
            # Process event
            await self._process_event(event)
            
            # Delay between events (faster for demo, adjust for production)
            await asyncio.sleep(0.5)  # 0.5 second per event for demo
        
        if self._running:
            logger.info("Finished streaming all events, restarting...")
            self.event_index = 0
            self._task = asyncio.create_task(self._stream_events())
    
    async def _process_event(self, event: Dict):
        """Process a single event and update prices"""
        player = event.get("player")
        if not player:
            return
        
        player_id = str(player.get("id"))
        player_name = player.get("name", "Unknown")
        event_type = event.get("type", {}).get("name", "")
        minute = event.get("minute", 0)
        
        # Determine stat changes based on event
        goals = 0
        assists = 0
        
        if event_type == "Shot":
            shot_outcome = event.get("shot", {}).get("outcome", {}).get("name", "")
            if shot_outcome == "Goal":
                goals = 1
                logger.info(f"GOAL! {player_name} scores at minute {minute}")
        
        elif event_type == "Pass":
            if event.get("pass", {}).get("goal_assist"):
                assists = 1
                logger.info(f"ASSIST! {player_name} assists at minute {minute}")
        
        # Only broadcast significant events
        if goals > 0 or assists > 0:
            # Update pricing engine
            from app.models import StatUpdate
            stat = StatUpdate(
                player_id=player_id,
                goals=goals,
                assists=assists,
                minutes=minute,
                injured=False
            )
            
            new_price = self.pricing_engine.apply_stat(stat)
            
            # Broadcast update
            update = {
                "type": "update",
                "player_id": player_id,
                "player_name": player_name,
                "new_price": new_price,
                "goals": goals,
                "assists": assists,
                "minutes": minute,
                "event": event_type
            }
            await self.broadcast_callback(update)


# Singleton instance
_statsbomb_client: Optional[StatsBombClient] = None


def get_statsbomb_client() -> StatsBombClient:
    global _statsbomb_client
    if _statsbomb_client is None:
        _statsbomb_client = StatsBombClient(use_open_data=True)
    return _statsbomb_client
