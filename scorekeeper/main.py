#!/usr/bin/env python3
"""
Scorekeeper — reads NYT game scores from iMessage and writes to Google Sheets.
"""
import logging
import os
import sys

import yaml

from .announcer import announce_daily_stats, maybe_announce
from .messages_reader import get_messages
from .parser import parse_score
from .sheets_writer import append_scores, ensure_header, get_service
from .state import load_state, save_state
from .stats import run_stats

LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'scorekeeper.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def resolve_player(handle: str | None, is_from_me: bool, config: dict) -> str:
    if is_from_me:
        return config['owner_name']
    if handle and handle in config.get('players', {}):
        return config['players'][handle]
    return handle or 'Unknown'


def run() -> None:
    config = load_config()
    state = load_state()
    last_rowid = state.get('last_seen_rowid', 0)

    log.info(f"Starting run. last_seen_rowid={last_rowid}")

    try:
        service = get_service()
    except Exception as e:
        log.error(f"Failed to connect to Google Sheets: {e}")
        sys.exit(1)

    sheet_id = config['google_sheet_id']
    ensure_header(service, sheet_id)

    chat_name = config['chat_name']
    rows_to_write = []
    max_rowid = last_rowid
    skipped = 0
    parsed = 0

    for msg in get_messages(chat_name, last_rowid):
        max_rowid = max(max_rowid, msg['rowid'])
        score = parse_score(msg['text'], msg['sent_at'])
        if score is None:
            skipped += 1
            continue

        parsed += 1
        player = resolve_player(msg['handle'], msg['is_from_me'], config)
        hard_mode_val = ''
        if score['hard_mode'] is not None:
            hard_mode_val = 'TRUE' if score['hard_mode'] else 'FALSE'

        row = [
            score['puzzle_date'],
            player,
            score['game'],
            score['puzzle_num'],
            score['result'],
            score['mistakes'],
            hard_mode_val,
            'TRUE' if score['won'] else 'FALSE',
            msg['rowid'],
            msg['sent_at'].strftime('%Y-%m-%d %H:%M:%S'),
        ]
        rows_to_write.append(row)

    written = 0
    if rows_to_write:
        try:
            written = append_scores(service, sheet_id, rows_to_write)
        except Exception as e:
            log.error(f"Failed to write to Sheets: {e}")
            sys.exit(1)

    if max_rowid > last_rowid:
        save_state({'last_seen_rowid': max_rowid})

    log.info(
        f"Done. Messages processed: {parsed + skipped}, "
        f"scores parsed: {parsed}, rows written: {written}, "
        f"duplicates skipped: {parsed - written}, "
        f"non-score messages: {skipped}. "
        f"New last_seen_rowid={max_rowid}"
    )

    log.info("Updating Daily and Monthly stats sheets...")
    try:
        run_stats(service, sheet_id)
        log.info("Stats sheets updated.")
    except Exception as e:
        log.error(f"Failed to update stats sheets: {e}")

    try:
        sent = maybe_announce(service, sheet_id, chat_name)
        if sent:
            log.info("Monthly announcement sent to iMessage group chat.")
    except Exception as e:
        log.error(f"Failed to send monthly announcement: {e}")

    try:
        sent = announce_daily_stats(service, sheet_id, chat_name)
        if sent:
            log.info("Daily stats announcement sent to iMessage group chat.")
    except Exception as e:
        log.error(f"Failed to send daily stats announcement: {e}")


if __name__ == '__main__':
    run()
