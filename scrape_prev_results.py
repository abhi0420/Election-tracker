#!/usr/bin/env python3
"""
Scrape previous election constituency results from Wikipedia.
Saves prev_results_{state}.csv in the workspace.

Usage:
    python scrape_prev_results.py wb
    python scrape_prev_results.py all
"""

import sys
import re
import csv
import requests
import pandas as pd
from io import StringIO

WIKI_URLS = {
    'wb':         'https://en.wikipedia.org/wiki/2021_West_Bengal_Legislative_Assembly_election',
    'tn':         'https://en.wikipedia.org/wiki/2021_Tamil_Nadu_legislative_assembly_election',
    'kerala':     'https://en.wikipedia.org/wiki/2021_Kerala_Legislative_Assembly_election',
    'assam':      'https://en.wikipedia.org/wiki/2021_Assam_Legislative_Assembly_election',
    'puducherry': 'https://en.wikipedia.org/wiki/2021_Puducherry_Legislative_Assembly_election',
    'bihar':      'https://en.wikipedia.org/wiki/2020_Bihar_legislative_assembly_election',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; election-tracker/1.0; +https://github.com)'
}


def _to_int(v):
    try:
        return int(str(v).replace(',', '').replace('\u2013', '0').replace('-', '0').strip())
    except Exception:
        return 0


def _to_float(v):
    try:
        return round(float(str(v).replace('%', '').strip()), 2)
    except Exception:
        return 0.0


def _clean(v):
    """Strip Wikipedia citation brackets like [1], [a]."""
    return re.sub(r'\[.*?\]', '', str(v)).strip()


def _find_results_table(tables):
    """
    Find the constituency results table.  It typically has ≥ 10 columns and
    ≥ 20 rows, with the AC number in column 0 or column 1 (some states have
    a leading district column, e.g. Puducherry).
    Returns (table, ac_col) where ac_col is 0 or 1.
    """
    best = None
    best_ac_col = 0
    for tbl in tables:
        ncols = len(tbl.columns)
        nrows = len(tbl)
        if ncols >= 10 and nrows >= 20:
            # Check col 0 first, then col 1
            for c in [0, 1]:
                if c >= ncols:
                    continue
                numeric_count = sum(
                    1 for val in tbl.iloc[:, c].dropna().head(15)
                    if _safe_int(val) is not None
                )
                if numeric_count >= 3:
                    if best is None or nrows > len(best):
                        best = tbl
                        best_ac_col = c
                    break
    return best, best_ac_col


def _safe_int(val):
    try:
        return int(str(val).replace(',', '').strip())
    except Exception:
        return None


def scrape_state(state_code):
    url = WIKI_URLS.get(state_code)
    if not url:
        print(f"[{state_code}] Unknown state code. Available: {', '.join(WIKI_URLS)}")
        return False

    print(f"[{state_code}] Fetching {url} ...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{state_code}] HTTP error: {e}")
        return False

    html = resp.text
    print(f"[{state_code}] Page fetched ({len(html)//1024} KB). Parsing tables...")

    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        print(f"[{state_code}] pandas.read_html failed: {e}")
        return False

    print(f"[{state_code}] Found {len(tables)} tables total.")
    tbl, ac_col = _find_results_table(tables)

    if tbl is None:
        print(f"[{state_code}] Could not identify constituency results table.")
        print("Table shapes found:", [t.shape for t in tables])
        return False

    # Flatten MultiIndex columns
    if isinstance(tbl.columns, pd.MultiIndex):
        tbl.columns = [
            ' '.join(str(c).strip() for c in col if str(c).lower() not in ('nan', '')).strip()
            for col in tbl.columns.values
        ]

    print(f"[{state_code}] Results table: {tbl.shape[0]} rows × {tbl.shape[1]} cols")
    print(f"[{state_code}] AC number detected in column {ac_col}")
    print(f"[{state_code}] Columns: {list(tbl.columns)}")

    # Locate data columns by name rather than fixed offsets.
    # This handles tables with extra Alliance columns (Kerala, TN) or Turnout columns.
    cols_flat = list(tbl.columns)

    def _ci(*keywords):
        """Return index of first column whose name contains ALL keywords (case-insensitive)."""
        for i, col in enumerate(cols_flat):
            col_l = col.lower()
            if all(k.lower() in col_l for k in keywords):
                return i
        return -1

    ci_win_cand  = _ci('winner', 'candidate')
    ci_win_party = _ci('winner', 'party.1')
    if ci_win_party < 0:
        ci_win_party = _ci('winner', 'party')
    ci_win_votes = _ci('winner', 'vote')
    ci_win_pct   = _ci('winner', '%')
    ci_sec_cand  = _ci('runner', 'candidate')
    ci_sec_party = _ci('runner', 'party.1')
    if ci_sec_party < 0:
        ci_sec_party = _ci('runner', 'party')
    ci_sec_votes = _ci('runner', 'vote')
    ci_sec_pct   = _ci('runner', '%')
    ci_margin    = _ci('margin')

    print(f"[{state_code}] Column positions → "
          f"win_cand={ci_win_cand} win_party={ci_win_party} "
          f"win_votes={ci_win_votes} win_pct={ci_win_pct} "
          f"sec_cand={ci_sec_cand} sec_party={ci_sec_party} "
          f"sec_votes={ci_sec_votes} sec_pct={ci_sec_pct} margin={ci_margin}")

    missing = [n for n, c in [('win_cand', ci_win_cand), ('win_votes', ci_win_votes),
                               ('sec_cand', ci_sec_cand), ('sec_votes', ci_sec_votes),
                               ('margin', ci_margin)] if c < 0]
    if missing:
        print(f"[{state_code}] WARNING: Could not locate columns: {missing}")

    max_ci = max(ci for ci in [ci_win_cand, ci_win_party, ci_win_votes, ci_win_pct,
                                ci_sec_cand, ci_sec_party, ci_sec_votes, ci_sec_pct,
                                ci_margin] if ci >= 0)

    out_file = f"prev_results_{state_code}.csv"
    rows_written = 0

    with open(out_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'AC_NO', 'prev_win_cand', 'prev_win_party',
            'prev_win_votes', 'prev_win_pct',
            'prev_sec_cand', 'prev_sec_party',
            'prev_sec_votes', 'prev_sec_pct',
            'prev_margin',
        ])
        writer.writeheader()

        def _get(vals, ci):
            return vals[ci] if 0 <= ci < len(vals) else 'nan'

        for _, row in tbl.iterrows():
            vals = [str(v) for v in row.values]

            # AC number must be a plain integer
            ac_no = _safe_int(vals[ac_col]) if ac_col < len(vals) else None
            if ac_no is None:
                continue  # header, district separator, or non-data row

            if len(vals) <= max_ci:
                continue

            writer.writerow({
                'AC_NO':          ac_no,
                'prev_win_cand':  _clean(_get(vals, ci_win_cand)),
                'prev_win_party': _clean(_get(vals, ci_win_party)),
                'prev_win_votes': _to_int(_get(vals, ci_win_votes)),
                'prev_win_pct':   _to_float(_get(vals, ci_win_pct)),
                'prev_sec_cand':  _clean(_get(vals, ci_sec_cand)),
                'prev_sec_party': _clean(_get(vals, ci_sec_party)),
                'prev_sec_votes': _to_int(_get(vals, ci_sec_votes)),
                'prev_sec_pct':   _to_float(_get(vals, ci_sec_pct)),
                'prev_margin':    _to_int(_get(vals, ci_margin)),
            })
            rows_written += 1

    if rows_written == 0:
        print(f"[{state_code}] WARNING: 0 rows written. Column positions may be wrong.")
        print("First 3 data rows:")
        print(tbl.head(3).to_string())
    else:
        print(f"[{state_code}] Saved {rows_written} constituencies → {out_file}")

    return rows_written > 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scrape_prev_results.py <state_code|all>")
        print("States:", ', '.join(WIKI_URLS))
        sys.exit(1)

    target = sys.argv[1].lower()
    if target == 'all':
        ok = 0
        for code in WIKI_URLS:
            if scrape_state(code):
                ok += 1
        print(f"\nDone: {ok}/{len(WIKI_URLS)} states scraped successfully.")
    else:
        success = scrape_state(target)
        sys.exit(0 if success else 1)
