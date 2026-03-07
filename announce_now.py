#!/usr/bin/env python3
"""
Sends the current month's stats to the iMessage group chat immediately.
Run manually whenever you want to trigger the daily stats announcement.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import yaml
from scorekeeper.sheets_writer import get_service
from scorekeeper.announcer import announce_daily_stats

if __name__ == '__main__':
    with open('config.yaml') as f:
        config = yaml.safe_load(f)

    service = get_service()
    sent = announce_daily_stats(service, config['google_sheet_id'], config['chat_name'])
    if sent:
        print("Stats sent to iMessage group chat.")
    else:
        print("No stats found for current month — nothing sent.")
