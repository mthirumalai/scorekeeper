#!/usr/bin/env python3
"""
Recomputes daily winners and monthly stats from the Scores sheet.
Run manually or after each main.py run.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import yaml
from scorekeeper.sheets_writer import get_service
from scorekeeper.stats import run_stats

if __name__ == '__main__':
    with open('config.yaml') as f:
        config = yaml.safe_load(f)

    service = get_service()
    run_stats(service, config['google_sheet_id'])
