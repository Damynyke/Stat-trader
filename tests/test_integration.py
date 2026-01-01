import asyncio
import json
import sys
import os
import pytest

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from data_provider import process_statsbomb, StatUpdate
from pricing_engine import PricingEngine


# Helper to run async code in sync tests
def async_test(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class TestStatsBombParser:
    """Test StatsBomb event parsing and aggregation."""

    def test_parse_goals_and_assists(self):
        """Verify that goals and assists are correctly aggregated."""
        async def run():
            data = {
                "events": [
                    {
                        "type": {"name": "Goal"},
                        "player": {"id": 123, "name": "Player A"},
                        "minute": 10,
                    },
                    {
                        "type": {"name": "Goal"},
                        "player": {"id": 123},
                        "minute": 45,
                        "related_players": [
                            {"player": {"id": 456}, "role": "Assist"}
                        ],
                    },
                ]
            }
            results = []
            await process_statsbomb(data, lambda s: (results.append(s) or asyncio.sleep(0)))
            return results
        
        results = async_test(run())
        assert len(results) >= 1
        p123 = next((r for r in results if r.player_id == "123"), None)
        assert p123 is not None
        assert p123.goals == 2
        assert p123.minutes == 45

    def test_parse_injury(self):
        """Verify that injury events set the injury flag."""
        async def run():
            data = {
                "events": [
                    {
                        "type": {"name": "Injury"},
                        "player": {"id": 789},
                        "minute": 30,
                    }
                ]
            }
            results = []
            await process_statsbomb(data, lambda s: (results.append(s) or asyncio.sleep(0)))
            return results
        
        results = async_test(run())
        assert len(results) >= 1
        p789 = next((r for r in results if r.player_id == "789"), None)
        assert p789 is not None
        assert p789.injury is True

    def test_parse_empty_events(self):
        """Verify parser handles empty event lists gracefully."""
        async def run():
            data = {"events": []}
            results = []
            await process_statsbomb(data, lambda s: (results.append(s) or asyncio.sleep(0)))
            return results
        
        results = async_test(run())
        assert len(results) == 0

    def test_parse_list_input(self):
        """Verify parser accepts a raw list of events."""
        async def run():
            data = [
                {"type": {"name": "Goal"}, "player": {"id": 111}, "minute": 5}
            ]
            results = []
            await process_statsbomb(data, lambda s: (results.append(s) or asyncio.sleep(0)))
            return results
        
        results = async_test(run())
        assert len(results) >= 1


class TestPricingEngine:
    """Test PricingEngine price update logic."""

    def test_base_price_initialization(self):
        """Verify engine initializes with base price."""
        engine = PricingEngine(base_price=1000.0)
        assert engine.base_price == 1000.0
        assert len(engine.prices) == 0

    def test_apply_stat_goals(self):
        """Verify goals increase price (+100 per goal)."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            stat = StatUpdate(player_id="p1", goals=2, assists=0, minutes=0, injury=False)
            price = await engine.apply_stat(stat)
            return price
        
        price = async_test(run())
        assert price == 1200.0

    def test_apply_stat_assists(self):
        """Verify assists increase price (+50 per assist)."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            stat = StatUpdate(player_id="p2", goals=0, assists=3, minutes=0, injury=False)
            price = await engine.apply_stat(stat)
            return price
        
        price = async_test(run())
        assert price == 1150.0

    def test_apply_stat_minutes(self):
        """Verify minutes increase price (+0.1 per minute)."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            stat = StatUpdate(player_id="p3", goals=0, assists=0, minutes=90, injury=False)
            price = await engine.apply_stat(stat)
            return price
        
        price = async_test(run())
        assert price == 1009.0

    def test_apply_stat_injury(self):
        """Verify injury applies 30% penalty (multiply by 0.7)."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            stat = StatUpdate(player_id="p4", goals=0, assists=0, minutes=0, injury=True)
            price = await engine.apply_stat(stat)
            return price
        
        price = async_test(run())
        assert price == 700.0

    def test_apply_stat_combined(self):
        """Verify combined impact (goals + assists + minutes + injury)."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            stat = StatUpdate(player_id="p5", goals=1, assists=2, minutes=45, injury=False)
            price = await engine.apply_stat(stat)
            return price
        
        price = async_test(run())
        assert price == 1204.5

    def test_price_persistence(self):
        """Verify engine maintains prices across multiple updates."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            stat1 = StatUpdate(player_id="p6", goals=1, assists=0, minutes=0, injury=False)
            stat2 = StatUpdate(player_id="p6", goals=1, assists=0, minutes=0, injury=False)
            
            price1 = await engine.apply_stat(stat1)
            price2 = await engine.apply_stat(stat2)
            
            return price1, price2
        
        price1, price2 = async_test(run())
        assert price1 == 1100.0
        assert price2 == 1200.0


class TestIntegration:
    """Test end-to-end StatsBomb -> PricingEngine flow."""

    def test_statsbomb_to_pricing(self):
        """Verify parsed StatsBomb events flow through pricing engine."""
        async def run():
            engine = PricingEngine(base_price=1000.0)
            data = {
                "events": [
                    {
                        "type": {"name": "Goal"},
                        "player": {"id": 999},
                        "minute": 20,
                    },
                    {
                        "type": {"name": "Goal"},
                        "player": {"id": 999},
                        "minute": 75,
                    },
                ]
            }
            
            async def callback(stat):
                await engine.apply_stat(stat)

            await process_statsbomb(data, callback)
            
            # Player 999 should have 2 goals and max minute 75
            # delta = 100*2 + 0.1*75 = 200 + 7.5 = 207.5
            # price = 1000 + 207.5 = 1207.5
            return engine.prices.get("999")
        
        price = async_test(run())
        assert price == 1207.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
