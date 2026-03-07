"""
On the 1st of each month, sends a summary of last month's winners and
stats to the iMessage group chat via AppleScript.
"""
import subprocess
from datetime import datetime, date
from collections import defaultdict


def _previous_month_label() -> str:
    """Returns 'YYYY-MM' for last month."""
    today = date.today()
    if today.month == 1:
        return f"{today.year - 1}-12"
    return f"{today.year}-{today.month - 1:02d}"


def _current_month_label() -> str:
    """Returns 'YYYY-MM' for the current month."""
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _month_display(label: str) -> str:
    """'2026-02' -> 'February 2026'"""
    return datetime.strptime(label, '%Y-%m').strftime('%B %Y')


def _read_tab(service, sheet_id: str, tab: str) -> list[dict]:
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f'{tab}!A:Z',
    ).execute()
    rows = result.get('values', [])
    if len(rows) < 2:
        return []
    headers = rows[0]
    records = []
    for row in rows[1:]:
        row += [''] * (len(headers) - len(row))
        records.append(dict(zip(headers, row)))
    return records


def _count_daily_wins(daily_rows: list[dict], month_label: str) -> dict[str, dict[str, int]]:
    """
    Count outright and tied wins per player per game for a given month.
    Returns {player: {'Wordle_outright': N, 'Wordle_tied': N, 'Connections_outright': N, 'Connections_tied': N}}.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {
        'Wordle_outright': 0, 'Wordle_tied': 0,
        'Connections_outright': 0, 'Connections_tied': 0,
    })
    for row in daily_rows:
        date_str = row.get('Date', '')
        if not date_str.startswith(month_label):
            continue
        game = row.get('Game', '')
        if game not in ('Wordle', 'Connections'):
            continue
        winners_str = row.get('Winner(s)', '')
        if not winners_str or winners_str in ('No winner', 'No winner (all X)'):
            continue
        winners = [w.strip() for w in winners_str.split(', ') if w.strip()]
        tied = len(winners) > 1
        for winner in winners:
            key = f"{game}_{'tied' if tied else 'outright'}"
            counts[winner][key] += 1
    return counts


def _build_message(month_label: str, winner_row: dict, monthly_rows: list[dict],
                   daily_rows: list[dict]) -> str:
    month_name = _month_display(month_label)
    conn_winner = winner_row.get('Connections', 'N/A')
    wordle_winner = winner_row.get('Wordle', 'N/A')
    daily_wins = _count_daily_wins(daily_rows, month_label)

    lines = [
        f"{month_name} Results",
        "",
        f"Wordle Champion: {wordle_winner}",
        f"Connections Champion: {conn_winner}",
        "",
        "Stats:",
    ]

    for row in sorted(monthly_rows, key=lambda r: r.get('Name', '')):
        name = row.get('Name', '')
        cc = row.get('Connections Completed', '0')
        cs = row.get('Connections Won', '0')  # successfully solved
        wc = row.get('Wordles Completed', '0')
        ws = row.get('Wordles Won', '0')      # successfully solved
        cw = daily_wins.get(name, {}).get('Connections', 0)  # won daily matchup
        ww = daily_wins.get(name, {}).get('Wordle', 0)       # won daily matchup
        wo = daily_wins.get(name, {}).get('Wordle_outright', 0)
        wt = daily_wins.get(name, {}).get('Wordle_tied', 0)
        co = daily_wins.get(name, {}).get('Connections_outright', 0)
        ct = daily_wins.get(name, {}).get('Connections_tied', 0)
        lines.append(f"  {name}:")
        lines.append(f"    Wordle: played {wc}, completed {ws}, won outright {wo}, won tied {wt}")
        lines.append(f"    Connections: played {cc}, completed {cs}, won outright {co}, won tied {ct}")

    return "\n".join(lines)


def _send_imessage(chat_name: str, message: str) -> None:
    # Build AppleScript string with newlines as (ASCII character 13)
    escaped = message.replace('\\', '\\\\').replace('"', '\\"')
    as_lines = '" & (ASCII character 13) & "'.join(escaped.split('\n'))
    script = f'''
tell application "Messages"
    set theMsg to "{as_lines}"
    set theChat to missing value
    repeat with c in chats
        if name of c is "{chat_name}" then
            set theChat to c
            exit repeat
        end if
    end repeat
    if theChat is missing value then
        error "Chat not found: {chat_name}"
    end if
    send theMsg to theChat
end tell
'''
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")


def _build_daily_stats_message(month_label: str, monthly_rows: list[dict],
                               daily_rows: list[dict]) -> str:
    month_name = _month_display(month_label)
    daily_wins = _count_daily_wins(daily_rows, month_label)

    lines = [
        f"{month_name} Stats (so far)",
        "",
        "Stats:",
    ]

    for row in sorted(monthly_rows, key=lambda r: r.get('Name', '')):
        name = row.get('Name', '')
        cc = row.get('Connections Completed', '0')
        cs = row.get('Connections Won', '0')
        wc = row.get('Wordles Completed', '0')
        ws = row.get('Wordles Won', '0')
        wo = daily_wins.get(name, {}).get('Wordle_outright', 0)
        wt = daily_wins.get(name, {}).get('Wordle_tied', 0)
        co = daily_wins.get(name, {}).get('Connections_outright', 0)
        ct = daily_wins.get(name, {}).get('Connections_tied', 0)
        lines.append(f"  {name}:")
        lines.append(f"    Wordle: played {wc}, completed {ws}, won outright {wo}, won tied {wt}")
        lines.append(f"    Connections: played {cc}, completed {cs}, won outright {co}, won tied {ct}")

    return "\n".join(lines)


def announce_daily_stats(service, sheet_id: str, chat_name: str) -> bool:
    """
    Sends the current month's running stats to the iMessage group chat every day.
    Returns True if an announcement was sent.
    """
    month_label = _current_month_label()

    monthly_records = _read_tab(service, sheet_id, 'Monthly')
    current_month_rows = [r for r in monthly_records if r.get('Month') == month_label]
    if not current_month_rows:
        return False

    daily_records = _read_tab(service, sheet_id, 'Daily')

    message = _build_daily_stats_message(month_label, current_month_rows, daily_records)
    _send_imessage(chat_name, message)
    return True


def maybe_announce(service, sheet_id: str, chat_name: str) -> bool:
    """
    Sends the monthly announcement if today is the 1st.
    Returns True if an announcement was sent.
    """
    if date.today().day != 1:
        return False

    month_label = _previous_month_label()

    winner_records = _read_tab(service, sheet_id, 'Winner')
    winner_row = next((r for r in winner_records if r.get('Month') == month_label), None)
    if not winner_row:
        return False

    monthly_records = _read_tab(service, sheet_id, 'Monthly')
    last_month_rows = [r for r in monthly_records if r.get('Month') == month_label]
    if not last_month_rows:
        return False

    daily_records = _read_tab(service, sheet_id, 'Daily')

    message = _build_message(month_label, winner_row, last_month_rows, daily_records)
    _send_imessage(chat_name, message)
    return True
