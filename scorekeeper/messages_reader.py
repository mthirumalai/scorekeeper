import sqlite3
import struct
from datetime import datetime, timedelta
from typing import Iterator

CHAT_DB_PATH = "file:///Users/{user}/Library/Messages/chat.db?mode=ro"
MAC_EPOCH = datetime(2001, 1, 1)

QUERY = """
SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, m.handle_id,
       m.date, h.id AS handle
FROM message m
JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
JOIN chat c ON cmj.chat_id = c.ROWID
LEFT JOIN handle h ON m.handle_id = h.ROWID
WHERE c.display_name = ?
  AND m.ROWID > ?
  AND m.item_type = 0
  AND m.associated_message_type = 0
ORDER BY m.ROWID ASC
"""


def _mac_date_to_datetime(mac_ts: int) -> datetime:
    return MAC_EPOCH + timedelta(seconds=mac_ts / 1e9)


def _extract_attributed_body_text(blob: bytes) -> str | None:
    """
    Extract plain text from an NSTypedStream attributedBody blob.
    Scans for the NSString marker and extracts the UTF-8 payload.
    """
    if not blob:
        return None

    # Look for the NSString class name marker followed by the string length+content
    # The blob contains NSAttributedString encoded via NSTypedStream
    # Strategy: find the UTF-8 text by scanning for long ASCII/UTF-8 runs after known markers
    try:
        # NSTypedStream format: look for string content after 'NSString' marker
        marker = b'NSString'
        idx = blob.find(marker)
        if idx == -1:
            return None

        # After NSString marker, skip to the actual string data
        # The string is length-prefixed; scan forward for readable content
        search_start = idx + len(marker)

        # Try to find the string by looking for the length byte followed by UTF-8 text
        # NSTypedStream stores strings as: <length as 2-byte big-endian> <utf8 bytes>
        # But we'll use a heuristic: scan for a printable ASCII/emoji sequence
        for i in range(search_start, min(search_start + 200, len(blob) - 2)):
            # Check if we have a 2-byte big-endian length followed by matching content
            length = struct.unpack('>H', blob[i:i+2])[0]
            if 0 < length < 4096 and i + 2 + length <= len(blob):
                candidate = blob[i+2:i+2+length]
                try:
                    text = candidate.decode('utf-8')
                    # Validate: should have some printable characters
                    if len(text) > 2 and any(c.isprintable() for c in text):
                        return text
                except (UnicodeDecodeError, ValueError):
                    continue
    except Exception:
        pass
    return None


def get_messages(chat_name: str, since_rowid: int, db_path: str | None = None) -> Iterator[dict]:
    import os
    if db_path is None:
        username = os.environ.get('USER', os.environ.get('LOGNAME', 'unknown'))
        db_path = f"file:///Users/{username}/Library/Messages/chat.db?mode=ro"

    try:
        conn = sqlite3.connect(db_path, uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"Cannot open chat.db: {e}\n"
            "Grant Full Disk Access to Terminal in System Settings → Privacy & Security."
        ) from e

    with conn:
        cursor = conn.execute(QUERY, (chat_name, since_rowid))
        for row in cursor:
            text = row['text']
            if not text and row['attributedBody']:
                text = _extract_attributed_body_text(bytes(row['attributedBody']))

            if not text:
                continue

            sent_at = _mac_date_to_datetime(row['date'])

            yield {
                'rowid': row['ROWID'],
                'text': text.strip(),
                'is_from_me': bool(row['is_from_me']),
                'handle': row['handle'],  # phone number or None for self
                'sent_at': sent_at,
            }
