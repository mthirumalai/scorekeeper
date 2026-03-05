#!/usr/bin/env python3
"""One-off: send monthly announcements for specific months."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import yaml
from scorekeeper.sheets_writer import get_service
from scorekeeper.announcer import _read_tab, _build_message, _send_imessage

with open('config.yaml') as f:
    config = yaml.safe_load(f)

service = get_service()
sheet_id = config['google_sheet_id']
chat_name = config['chat_name']

winner_records = _read_tab(service, sheet_id, 'Winner')
monthly_records = _read_tab(service, sheet_id, 'Monthly')
daily_records = _read_tab(service, sheet_id, 'Daily')

for month_label in ['2026-01', '2026-02']:
    winner_row = next((r for r in winner_records if r.get('Month') == month_label), None)
    month_rows = [r for r in monthly_records if r.get('Month') == month_label]

    if not winner_row or not month_rows:
        print(f"No data found for {month_label}, skipping.")
        continue

    message = _build_message(month_label, winner_row, month_rows, daily_records)
    print(f"Sending for {month_label}:\n{message}\n")
    _send_imessage(chat_name, message)
    print(f"Sent.")
