"""
Computes daily winners and monthly stats from the Scores sheet,
writing results to the Daily and Monthly sheets.
"""
from collections import defaultdict
from datetime import datetime

SCORES_TAB = 'Scores'
DAILY_TAB = 'Daily'
MONTHLY_TAB = 'Monthly'
WINNER_TAB = 'Winner'

DAILY_HEADERS = ['Date', 'Game', 'Puzzle #', 'Winner(s)', 'Winning Score']
MONTHLY_HEADERS = ['Month', 'Name', 'Connections Won', 'Wordles Won',
                   'Connections Completed', 'Wordles Completed']


def _read_scores(service, sheet_id: str) -> list[dict]:
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f'{SCORES_TAB}!A:J',
    ).execute()
    rows = result.get('values', [])
    if len(rows) < 2:
        return []

    headers = rows[0]
    records = []
    for row in rows[1:]:
        # Pad short rows
        row += [''] * (len(headers) - len(row))
        records.append(dict(zip(headers, row)))
    return records


def _wordle_attempts(result: str) -> int | None:
    """Return attempt count from 'N/6', or None if X/6 (failed)."""
    numerator = result.split('/')[0]
    if numerator == 'X':
        return None
    try:
        return int(numerator)
    except ValueError:
        return None


def compute_daily_winners(records: list[dict]) -> list[list]:
    """
    For each (Game, Puzzle #), determine the winner(s).
    Uses the earliest Date seen for that puzzle as the canonical date.
    Returns rows ready to write to the Daily sheet.
    """
    # Group by (game, puzzle_num) — puzzle number uniquely identifies a puzzle
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        key = (r['Game'], r['Puzzle #'])
        groups[key].append(r)

    daily_rows = []
    for (game, puzzle_num), entries in sorted(groups.items(), key=lambda x: int(x[0][1]) if x[0][1].isdigit() else 0):
        # Use the earliest date among all players' entries for this puzzle
        date = min(e['Date'] for e in entries)

        if game == 'Wordle':
            scored = [(e['Player'], _wordle_attempts(e['Result'])) for e in entries]
            scored = [(p, a) for p, a in scored if a is not None]
            if not scored:
                winners, score_str = ['No winner (all X)'], 'X/6'
            else:
                min_attempts = min(a for _, a in scored)
                winners = [p for p, a in scored if a == min_attempts]
                score_str = f'{min_attempts}/6'

        elif game == 'Connections':
            won_entries = [e for e in entries if e.get('Won') == 'TRUE']
            if not won_entries:
                winners, score_str = ['No winner'], 'N/A'
            else:
                min_mistakes = min(int(e.get('Mistakes', 0)) for e in won_entries)
                winners = [e['Player'] for e in won_entries
                           if int(e.get('Mistakes', 0)) == min_mistakes]
                score_str = f'{min_mistakes} mistake(s)'
        else:
            continue

        daily_rows.append([date, game, puzzle_num, ', '.join(winners), score_str])

    return daily_rows


def compute_monthly_stats(records: list[dict]) -> list[list]:
    """
    Aggregate per (month, player): connections won, wordles won,
    connections completed, wordles completed.
    """
    # month_player -> {connections_won, wordles_won, connections_completed, wordles_completed}
    stats: dict[tuple, dict] = defaultdict(lambda: {
        'connections_won': 0, 'wordles_won': 0,
        'connections_completed': 0, 'wordles_completed': 0,
    })

    for r in records:
        try:
            month = datetime.strptime(r['Date'], '%Y-%m-%d').strftime('%Y-%m')
        except ValueError:
            continue

        player = r['Player']
        game = r['Game']
        won = r.get('Won') == 'TRUE'
        key = (month, player)

        if game == 'Wordle':
            stats[key]['wordles_completed'] += 1
            if won:
                stats[key]['wordles_won'] += 1
        elif game == 'Connections':
            stats[key]['connections_completed'] += 1
            if won:
                stats[key]['connections_won'] += 1

    rows = []
    for (month, player), s in sorted(stats.items()):
        rows.append([
            month, player,
            s['connections_won'], s['wordles_won'],
            s['connections_completed'], s['wordles_completed'],
        ])
    return rows


def compute_monthly_winners(monthly_rows: list[list]) -> list[list]:
    """
    From Monthly stats rows, find the winner per month per game.
    monthly_rows columns: Month, Name, Connections Won, Wordles Won, ...
    Returns rows for the Winner sheet: Month | Connections | Wordle
    """
    # month -> {player: {connections_won, wordles_won}}
    by_month: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in monthly_rows:
        month, name, conn_won, wordle_won = row[0], row[1], row[2], row[3]
        by_month[month][name] = {
            'connections_won': int(conn_won),
            'wordles_won': int(wordle_won),
        }

    winner_rows = []
    for month in sorted(by_month):
        players = by_month[month]

        max_conn = max(s['connections_won'] for s in players.values())
        conn_winners = [p for p, s in players.items() if s['connections_won'] == max_conn]

        max_wordle = max(s['wordles_won'] for s in players.values())
        wordle_winners = [p for p, s in players.items() if s['wordles_won'] == max_wordle]

        winner_rows.append([month, ' / '.join(sorted(conn_winners)), ' / '.join(sorted(wordle_winners))])

    return winner_rows


def _clear_and_write(service, sheet_id: str, tab: str, headers: list, rows: list[list]) -> None:
    # Clear existing content
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id,
        range=f'{tab}!A:Z',
    ).execute()

    # Write header + data
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f'{tab}!A1',
        valueInputOption='RAW',
        body={'values': [headers] + rows},
    ).execute()


def run_stats(service, sheet_id: str) -> None:
    print("Reading Scores sheet...")
    records = _read_scores(service, sheet_id)
    print(f"  {len(records)} score records found.")

    print("Computing daily winners...")
    daily_rows = compute_daily_winners(records)
    _clear_and_write(service, sheet_id, DAILY_TAB, DAILY_HEADERS, daily_rows)
    print(f"  {len(daily_rows)} daily winner rows written to '{DAILY_TAB}'.")

    print("Computing monthly stats...")
    monthly_rows = compute_monthly_stats(records)
    _clear_and_write(service, sheet_id, MONTHLY_TAB, MONTHLY_HEADERS, monthly_rows)
    print(f"  {len(monthly_rows)} monthly stat rows written to '{MONTHLY_TAB}'.")

    print("Computing monthly winners...")
    winner_rows = compute_monthly_winners(monthly_rows)
    _clear_and_write(service, sheet_id, WINNER_TAB, ['Month', 'Connections', 'Wordle'], winner_rows)
    print(f"  {len(winner_rows)} winner rows written to '{WINNER_TAB}'.")
