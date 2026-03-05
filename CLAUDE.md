# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Scorekeeper** tracks NY Times game scores (Wordle and Connections) from a Messages app group chat called "NYTimes Games Scoresheet" and writes them to a Google Sheet.

Current players: Diksha Gautham, Josh Wang, and Madhavan (repo owner). Other players may join the chat in future.

## Project Status

Phase 1 complete. Running daily via cron at 8 AM.

## Architecture

- **Cron job** running daily at 8 AM on macOS (no UI)
- Reads messages from the "NYTimes Games Scoresheet" iMessage group chat (no other chats)
- Parses Wordle and Connections score shares (each has a unique puzzle number)
- Filters out non-score messages (congratulations, tapbacks, etc.)
- Writes scores to Google Sheets via the Sheets API
- Handles new users joining the group dynamically
- Recomputes daily winners and monthly stats after each run
- Sends a monthly summary announcement to the iMessage group chat on the 1st of each month

## Games Format

- **Wordle**: Shareable result includes the puzzle number and a grid of colored squares
- **Connections**: Shareable result includes the puzzle number and colored category squares
- Both are shared via the native NY Times app share functionality

## Google Sheet Structure

Four tabs:

| Tab | Description |
|-----|-------------|
| `Scores` | Raw scores — one row per player per puzzle |
| `Daily` | Daily winner(s) per game |
| `Monthly` | Per-player monthly aggregates (won/completed counts) |
| `Winner` | Monthly champion for Wordle and Connections |

### Scores tab columns
| Col | Header | Notes |
|-----|--------|-------|
| A | `Date` | Puzzle date (from Archive prefix or message date) |
| B | `Player` | From config.yaml; falls back to raw phone if unknown |
| C | `Game` | `Wordle` or `Connections` |
| D | `Puzzle #` | Integer |
| E | `Result` | Wordle: `N/6` or `X/6`. Connections: `N/4` |
| F | `Mistakes` | Wordle: always 0. Connections: count of mixed-color rows |
| G | `Hard Mode` | Wordle-only (`TRUE`/`FALSE`). Blank for Connections |
| H | `Won` | `TRUE`/`FALSE` |
| I | `Message ROWID` | For debugging |
| J | `Sent At` | Full iMessage timestamp |

### Winner logic
- **Wordle**: lowest attempt count (numerator of Result) that day; X/6 cannot win
- **Connections**: `Won=TRUE` with the fewest mistakes
- **Monthly champion**: most daily wins in the month per game; ties shown as `Name1 / Name2`

## File Structure

```
scorekeeper/
├── config.yaml                 # Player phone→name map, sheet ID, chat name
├── requirements.txt
├── credentials.json            # [NOT COMMITTED] From Google Cloud Console
├── token.json                  # [NOT COMMITTED] Auto-created on first OAuth run
├── state.json                  # [NOT COMMITTED] Tracks last processed message ROWID
├── setup.py                    # One-time OAuth browser flow
├── compute_stats.py            # Standalone script to recompute stats manually
├── run.sh                      # Shell wrapper (activates venv)
├── com.scorekeeper.plist       # Legacy launchd plist (not in use — cron used instead)
└── scorekeeper/
    ├── main.py                 # Orchestrator: read → parse → write → stats → announce
    ├── messages_reader.py      # chat.db querying + attributedBody text extraction
    ├── parser.py               # Wordle + Connections score parsing
    ├── sheets_writer.py        # Google Sheets OAuth + append + dedup
    ├── stats.py                # Daily winners, monthly stats, monthly champions
    ├── announcer.py            # iMessage announcement on the 1st of each month
    └── state.py                # state.json helpers (last_seen_rowid)
```

## Tech Stack

- Python 3 + venv
- `google-api-python-client`, `google-auth-oauthlib`, `pyyaml`
- Scheduled via crontab (not launchd); `/usr/sbin/cron` has Full Disk Access

## Commands

```bash
# Install dependencies
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# One-time OAuth setup
python setup.py

# Daily run (also called by cron)
venv/bin/python3 -m scorekeeper.main

# Recompute stats only (no message read)
venv/bin/python3 compute_stats.py
```
