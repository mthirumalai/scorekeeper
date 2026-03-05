import json
import os

STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'state.json')


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_seen_rowid": 0}


def save_state(state: dict) -> None:
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
