from fastapi import FastAPI
import random

app = FastAPI(title="Mock Live Football Feed")

# Simple in-memory player list matching MVP sample IDs
players = [
    {"player_id": "p1", "name": "K. Mbappé"},
    {"player_id": "p2", "name": "L. Messi"},
    {"player_id": "p3", "name": "K. De Bruyne"},
    {"player_id": "p4", "name": "V. van Dijk"},
]


@app.get("/feed")
async def feed():
    # Emit a small randomized stat update payload for each player
    out = []
    for p in players:
        item = {
            "player_id": p["player_id"],
            "goals": random.choices([0, 1, 2], weights=[85, 12, 3])[0],
            "assists": random.choices([0, 1], weights=[90, 10])[0],
            "minutes": random.randint(0, 90),
            "injury": random.random() < 0.003,
        }
        out.append(item)
    return {"players": out}
