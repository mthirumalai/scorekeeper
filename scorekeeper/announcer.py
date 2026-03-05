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


def _build_message(month_label: str, winner_row: dict, monthly_rows: list[dict]) -> str:
    month_name = _month_display(month_label)
    conn_winner = winner_row.get('Connections', 'N/A')
    wordle_winner = winner_row.get('Wordle', 'N/A')

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
        cw = row.get('Connections Won', '0')
        cc = row.get('Connections Completed', '0')
        ww = row.get('Wordles Won', '0')
        wc = row.get('Wordles Completed', '0')
        lines.append(
            f"  {name}: Wordle {ww}/{wc}, Connections {cw}/{cc}"
        )

    return "\n".join(lines)


def _send_imessage(chat_name: str, message: str) -> None:
    # Escape backslashes and double-quotes for AppleScript string
    safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
    script = f'''
tell application "Messages"
    set theChat to first item of (chats whose display name is "{chat_name}")
    send "{safe_message}" to theChat
end tell
'''
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")


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

    message = _build_message(month_label, winner_row, last_month_rows)
    _send_imessage(chat_name, message)
    return True
