import os
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
TOKEN_FILE = os.path.join(os.path.dirname(__file__), '..', 'token.json')
TAB_NAME = 'Scores'

HEADERS = ['Date', 'Player', 'Game', 'Puzzle #', 'Result',
           'Mistakes', 'Hard Mode', 'Won', 'Message ROWID', 'Sent At']


def get_service():
    creds: Optional[Credentials] = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('sheets', 'v4', credentials=creds)


def _get_existing_keys(service, sheet_id: str) -> set[tuple]:
    """Read columns A-D to build a set of (date, player, game, puzzle_num) keys."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f'{TAB_NAME}!A:D',
    ).execute()
    rows = result.get('values', [])
    keys = set()
    for row in rows[1:]:  # skip header
        if len(row) == 4:
            keys.add(tuple(row))
    return keys


def ensure_header(service, sheet_id: str) -> None:
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f'{TAB_NAME}!A1:J1',
    ).execute()
    existing = result.get('values', [])
    if not existing or existing[0] != HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f'{TAB_NAME}!A1',
            valueInputOption='RAW',
            body={'values': [HEADERS]},
        ).execute()


def append_scores(service, sheet_id: str, rows: list[list]) -> int:
    """
    Append rows, skipping duplicates based on (Date, Player, Game, Puzzle #).
    Returns count of rows actually written.
    """
    existing_keys = _get_existing_keys(service, sheet_id)
    to_write = []
    for row in rows:
        key = tuple(str(x) for x in row[:4])
        if key not in existing_keys:
            to_write.append(row)
            existing_keys.add(key)  # prevent dupes within this batch

    if not to_write:
        return 0

    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=f'{TAB_NAME}!A1',
        valueInputOption='RAW',
        insertDataOption='INSERT_ROWS',
        body={'values': to_write},
    ).execute()

    return len(to_write)
