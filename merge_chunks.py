"""
Merge chunk CSVs into final per-state election result files.
Called by the GitHub Actions merge job after all scrape jobs complete.

Reads:  chunks/{state}_{start}_{end}.csv  (one per parallel job)
Writes: election_results_{state}.csv
        election_results_{state}.json
"""
import os
import json
import glob
import logging
import pandas as pd
from datetime import datetime
from state_config import ALL_STATES, get_state_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CHUNK_DIR = 'chunks'

EMPTY_COLS = [
    'AC_NO', 'Constituency', 'win_cand', 'win_party', 'win_votes',
    'sec_cand', 'sec_party', 'sec_votes', 'thi_cand', 'thi_party',
    'thi_votes', 'margin', 'tot_votes', 'votes_pct'
]


def merge_electors(election_df, electors_file):
    """Merge with electors file to compute votes_pct."""
    try:
        electors_df = pd.read_csv(electors_file)
        electors_df = electors_df.rename(columns={'AC_No': 'AC_NO', 'Total Votes': 'total_votes_cast'})
        election_df = election_df.merge(electors_df[['AC_NO', 'total_votes_cast']], on='AC_NO', how='left')
        election_df['votes_pct'] = (
            (election_df['tot_votes'] / election_df['total_votes_cast'] * 100)
            .fillna(0).clip(upper=100).round(2)
        )
        election_df = election_df.drop(columns=['total_votes_cast'])
        logging.info("  ✓ Merged electors data")
    except FileNotFoundError:
        logging.warning(f"  {electors_file} not found — votes_pct defaulting to 100")
        election_df['votes_pct'] = 100
    except Exception as e:
        logging.warning(f"  Electors merge error: {e} — votes_pct defaulting to 100")
        election_df['votes_pct'] = 100
    return election_df


def main():
    if not os.path.isdir(CHUNK_DIR):
        logging.error(f"No '{CHUNK_DIR}' directory found — nothing to merge.")
        return

    timestamp = datetime.utcnow().isoformat() + 'Z'
    total_merged = 0

    for state_code, sc in ALL_STATES.items():
        csv_file = sc['csv_file']
        electors_file = sc['electors_file']

        # Find all chunk files for this state
        pattern = os.path.join(CHUNK_DIR, f"{state_code}_*.csv")
        chunk_files = sorted(glob.glob(pattern))

        if not chunk_files:
            logging.info(f"[{sc['name']}] No chunks found — skipping.")
            continue

        logging.info(f"[{sc['name']}] Merging {len(chunk_files)} chunks...")

        dfs = []
        for cf in chunk_files:
            try:
                df = pd.read_csv(cf)
                if len(df) > 0:
                    dfs.append(df)
                    logging.info(f"  + {os.path.basename(cf)}: {len(df)} rows")
                else:
                    logging.warning(f"  - {os.path.basename(cf)}: empty, skipping")
            except Exception as e:
                logging.warning(f"  - {os.path.basename(cf)}: read error ({e}), skipping")

        if not dfs:
            logging.warning(f"[{sc['name']}] All chunks empty — writing empty CSV.")
            pd.DataFrame(columns=EMPTY_COLS).to_csv(csv_file, index=False)
            continue

        # Combine, deduplicate (keep last version of each AC_NO), sort
        election_df = (
            pd.concat(dfs, ignore_index=True)
            .drop_duplicates(subset=['AC_NO'], keep='last')
            .sort_values('AC_NO')
            .reset_index(drop=True)
        )

        logging.info(f"  Combined: {len(election_df)} constituencies")

        # Add votes_pct
        election_df = merge_electors(election_df, electors_file)

        # Save CSV
        election_df.to_csv(csv_file, index=False)
        logging.info(f"  ✓ Saved: {csv_file}")

        # Save JSON
        json_file = csv_file.replace('.csv', '.json')
        json_data = {
            "last_updated": timestamp,
            "total_seats": len(election_df),
            "data": election_df.to_dict(orient='records')
        }
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        logging.info(f"  ✓ Saved: {json_file}")

        total_merged += len(election_df)

    logging.info(f"\n✓ Merge complete — {total_merged} total constituencies across all states.")


if __name__ == "__main__":
    main()
