from typing import Dict
import asyncio


class PricingEngine:
    """Simple rule-based pricing engine for the MVP sandbox."""

    def __init__(self, base_price: float = 1000.0):
        self.prices: Dict[str, float] = {}
        self.base_price = float(base_price)

    def _ensure(self, player_id: str) -> float:
        if player_id not in self.prices:
            self.prices[player_id] = self.base_price
        return self.prices[player_id]

    async def apply_stat(self, stat) -> float:
        """Apply a StatUpdate-like object and update price."""
        pid = str(stat.player_id)
        price = self._ensure(pid)
        delta = 100.0 * getattr(stat, "goals", 0)
        delta += 50.0 * getattr(stat, "assists", 0)
        delta += 0.1 * getattr(stat, "minutes", 0)
        if getattr(stat, "injury", False):
            price = price * 0.7
        new_price = price + delta
        self.prices[pid] = round(new_price, 2)
        print(f"PRICE_UPDATE player={pid} price={self.prices[pid]} delta={delta}")
        await asyncio.sleep(0)
        return self.prices[pid]


if __name__ == "__main__":
    print("PricingEngine module")

