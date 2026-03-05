import re
from datetime import datetime
from typing import Optional

# Tapback prefixes to reject
TAPBACK_PREFIXES = ('Liked "', 'Loved "', 'Disliked "', 'Laughed at "',
                    'Emphasized "', 'Questioned "')

WORDLE_RE = re.compile(r'Wordle\s+([\d,]+)\s+([1-6X])/6(\*?)', re.IGNORECASE)
CONNECTIONS_RE = re.compile(r'Connections\s*\n?Puzzle\s+#(\d+)', re.IGNORECASE)
ARCHIVE_RE = re.compile(r'^Archive\s+(\w+ \d+, \d{4})\n', re.IGNORECASE)

CONNECTIONS_EMOJIS = {'🟨', '🟩', '🟦', '🟪'}


def is_tapback(text: str) -> bool:
    return text.startswith(TAPBACK_PREFIXES)


def extract_archive_date(text: str) -> Optional[datetime]:
    m = ARCHIVE_RE.match(text)
    if m:
        try:
            return datetime.strptime(m.group(1), '%B %d, %Y')
        except ValueError:
            return None
    return None


def _split_into_emoji_chars(line: str) -> list[str]:
    """Split a string into individual Unicode characters (handles multi-byte emoji)."""
    return list(line)


def _is_connections_grid_line(line: str) -> bool:
    chars = _split_into_emoji_chars(line.strip())
    return len(chars) == 4 and all(c in CONNECTIONS_EMOJIS for c in chars)


def _count_connections_mistakes(grid_lines: list[str]) -> int:
    mistakes = 0
    for line in grid_lines:
        chars = _split_into_emoji_chars(line.strip())
        if len(set(chars)) > 1:
            mistakes += 1
    return mistakes


def _connections_won(grid_lines: list[str]) -> bool:
    solid_rows = sum(
        1 for line in grid_lines
        if len(set(_split_into_emoji_chars(line.strip()))) == 1
    )
    return solid_rows == 4


def parse_score(text: str, message_date: datetime) -> Optional[dict]:
    """
    Parse a Wordle or Connections share text.
    Returns a dict with parsed fields, or None if not a score message.
    """
    if not text or is_tapback(text):
        return None

    archive_date = extract_archive_date(text)
    puzzle_date = archive_date if archive_date else message_date

    # Try Wordle
    m = WORDLE_RE.search(text)
    if m:
        puzzle_num = int(m.group(1).replace(',', ''))
        score = m.group(2)
        hard_mode = bool(m.group(3))
        result = f"{score}/6"
        won = score != 'X'
        return {
            'game': 'Wordle',
            'puzzle_num': puzzle_num,
            'puzzle_date': puzzle_date.strftime('%Y-%m-%d'),
            'result': result,
            'mistakes': 0,
            'hard_mode': hard_mode,
            'won': won,
        }

    # Try Connections
    m = CONNECTIONS_RE.search(text)
    if m:
        puzzle_num = int(m.group(1))
        lines = text.splitlines()
        grid_lines = [ln for ln in lines if _is_connections_grid_line(ln)]
        mistakes = _count_connections_mistakes(grid_lines)
        won = _connections_won(grid_lines)
        categories_correct = sum(
            1 for ln in grid_lines
            if len(set(_split_into_emoji_chars(ln.strip()))) == 1
        )
        result = f"{categories_correct}/4"
        return {
            'game': 'Connections',
            'puzzle_num': puzzle_num,
            'puzzle_date': puzzle_date.strftime('%Y-%m-%d'),
            'result': result,
            'mistakes': mistakes,
            'hard_mode': None,
            'won': won,
        }

    return None
