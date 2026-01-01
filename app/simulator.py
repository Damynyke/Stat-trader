import asyncio
import random
from typing import List
from .models import StatUpdate, Player


class Simulator:
    def __init__(self, players: List[Player], callback):
        self.players = players
        self.callback = callback
        self._task = None
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _run(self):
        while self._running:
            await asyncio.sleep(1)
            # pick a random player and generate a small stat update
            p = random.choice(self.players)
            stat = StatUpdate(
                player_id=p.id,
                goals=random.choices([0, 1, 2], weights=[85, 12, 3])[0],
                assists=random.choices([0, 1], weights=[90, 10])[0],
                minutes=random.randint(0, 90),
                injury=random.random() < 0.003,
            )
            await self.callback(stat)
