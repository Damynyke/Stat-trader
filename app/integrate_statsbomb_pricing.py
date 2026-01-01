import os
import sys
import asyncio
from typing import Any

# ensure this module can import sibling modules when executed as a script
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data_provider import process_statsbomb, StatUpdate  # type: ignore
from pricing_engine_simple import PricingEngine  # type: ignore


async def _cb_apply(engine: PricingEngine, stat: StatUpdate):
    await engine.apply_stat(stat)


async def run(path: str):
    payload = None
    with open(path, "r", encoding="utf-8") as f:
        import json

        payload = json.load(f)

    engine = PricingEngine()
    await process_statsbomb(payload, lambda s: _cb_apply(engine, s))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python integrate_statsbomb_pricing.py <statsbomb_match.json>")
        sys.exit(2)
    path = sys.argv[1]
    asyncio.run(run(path))
