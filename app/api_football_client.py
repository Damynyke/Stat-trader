"""
API-Football Integration (supports direct api-sports or RapidAPI)
Reads keys from .env so it can pick up values at runtime.
"""
import os
from dotenv import load_dotenv
import asyncio
import httpx
from dataclasses import dataclass
from typing import List, Dict, Callable

# Load env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.getenv('API_FOOTBALL_KEY')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST', 'api-football-v1.p.rapidapi.com')

# Default base urls
API_HOST_DIRECT = 'v3.football.api-sports.io'
API_HOST_RAPID = RAPIDAPI_HOST

@dataclass
class LiveMatch:
    fixture_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str
    elapsed: int
    league: str

@dataclass
class PlayerEvent:
    player_id: int
    player_name: str
    team: str
    event_type: str
    minute: int
    detail: str

class APIFootballClient:
    def __init__(self):
        # reload env each time to pick up any changes
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
        self.api_key = os.getenv('API_FOOTBALL_KEY')
        self.rapid_key = os.getenv('RAPIDAPI_KEY')
        self.rapid_host = os.getenv('RAPIDAPI_HOST', 'api-football-v1.p.rapidapi.com')

        if self.api_key:  # Prefer direct API key
            self.base_url = f'https://{API_HOST_DIRECT}'
            self.headers = {
                'x-apisports-key': self.api_key,
                
            }
        elif self.rapid_key:  # Fallback to RapidAPI
            self.base_url = f'https://{API_HOST_DIRECT}'
            self.headers = {
                'x-apisports-key': self.api_key,
            }
        else:
            raise RuntimeError('No API-Football key configured')

    async def _request(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{path}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, params=params or {}, timeout=30.0)
            resp.raise_for_status()
            return resp.json()

    async def get_live_fixtures(self) -> List[LiveMatch]:
        # path differs slightly between providers; attempt common endpoints
        # for RapidAPI the path is 'fixtures', for api-sports v3 also 'fixtures'
        data = await self._request('fixtures', {'live': 'all'})
        matches = []
        for fixture in data.get('response', []):
            f = fixture.get('fixture', {})
            teams = fixture.get('teams', {})
            goals = fixture.get('goals', {})
            league = fixture.get('league', {})
            matches.append(LiveMatch(
                fixture_id=f.get('id'),
                home_team=teams.get('home', {}).get('name'),
                away_team=teams.get('away', {}).get('name'),
                home_score=goals.get('home') or 0,
                away_score=goals.get('away') or 0,
                status=f.get('status', {}).get('short'),
                elapsed=f.get('status', {}).get('elapsed') or 0,
                league=league.get('name')
            ))
        return matches

    async def get_fixture_events(self, fixture_id: int) -> List[PlayerEvent]:
        data = await self._request('fixtures/events', {'fixture': fixture_id})
        events = []
        for e in data.get('response', []):
            player = e.get('player') or {}
            team = e.get('team') or {}
            minute = (e.get('time') or {}).get('elapsed') or 0
            events.append(PlayerEvent(
                player_id=player.get('id') or 0,
                player_name=player.get('name') or 'Unknown',
                team=team.get('name') or 'Unknown',
                event_type=e.get('type') or '',
                minute=minute,
                detail=e.get('detail') or ''
            ))
        return events

    async def get_fixture_statistics(self, fixture_id: int) -> Dict:
        data = await self._request('fixtures/players', {'fixture': fixture_id})
        stats = {}
        for team_data in data.get('response', []):
            for player_data in team_data.get('players', []):
                player = player_data.get('player', {})
                stat = player_data.get('statistics', [{}])[0]
                stats[player.get('id')] = {
                    'name': player.get('name'),
                    'team': team_data.get('team', {}).get('name'),
                    'minutes': (stat.get('games') or {}).get('minutes') or 0,
                    'goals': (stat.get('goals') or {}).get('total') or 0,
                    'assists': (stat.get('goals') or {}).get('assists') or 0,
                    'rating': (stat.get('games') or {}).get('rating') or '0'
                }
        return stats


    async def get_today_fixtures(self, league_id: int = None) -> List[dict]:
        """Get today's fixtures, optionally filtered by league"""
        from datetime import date
        params = {'date': date.today().isoformat()}
        if league_id:
            params['league'] = league_id
        data = await self._request('fixtures', params)
        return data.get('response', [])

    async def search_players(self, name: str) -> List[dict]:
        """Search for players by name"""
        data = await self._request('players', {'search': name, 'season': 2025})
        return data.get('response', [])

_client = None

def get_api_football_client() -> APIFootballClient:
    global _client
    # create a new client each call to pick up .env changes
    _client = APIFootballClient()
    return _client


class LiveMatchFeed:
    """Real-time match feed that polls API-Football for live updates"""
    def __init__(self, client: APIFootballClient, pricing_engine, broadcast_callback: Callable, poll_interval: float = 60.0):
        self.client = client
        self.pricing_engine = pricing_engine
        self.broadcast = broadcast_callback
        self.poll_interval = poll_interval
        self._running = False
        self._task = None
        self.processed_events = set()
        self.player_mapping = {}

    async def start(self, fixture_ids: List[int] = None):
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(fixture_ids))

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _poll_loop(self, fixture_ids: List[int] = None):
        while self._running:
            try:
                if fixture_ids:
                    for fid in fixture_ids:
                        await self._process_fixture(fid)
                else:
                    live_matches = await self.client.get_live_fixtures()
                    for match in live_matches:
                        await self._process_fixture(match.fixture_id)
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"Error in live feed: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _process_fixture(self, fixture_id: int):
        try:
            events = await self.client.get_fixture_events(fixture_id)
            for event in events:
                event_key = f"{fixture_id}_{event.player_id}_{event.event_type}_{event.minute}"
                if event_key in self.processed_events:
                    continue
                self.processed_events.add(event_key)
                our_player_id = self.player_mapping.get(event.player_id, str(event.player_id))
                await self.broadcast({
                    "type": "live_event",
                    "fixture_id": fixture_id,
                    "player_id": our_player_id,
                    "player_name": event.player_name,
                    "event": event.event_type,
                    "detail": event.detail,
                    "minute": event.minute,
                    "price": self.pricing_engine.prices.get(our_player_id, 1000) if self.pricing_engine else 1000
                })
        except Exception as e:
            print(f"Error processing fixture {fixture_id}: {e}")


