"""
Generate dummy election results CSVs for all 5 states.
Uses real AC_NO + AC_NAME from shapefiles.
Run: python generate_dummy_data.py
"""
import random
import pandas as pd
import geopandas as gpd

random.seed(42)

# ── Party pools per state (winner pool, runner-up pool) ───────────────────────
STATE_PARTIES = {
    'tn': {
        'shapefile': 'ac/TN_AC_clean.shp',
        'csv_file': 'election_results_tn.csv',
        # (party, weight) — higher weight = more seats won
        'win_weights': [
            ('DMK', 40), ('ADMK', 25), ('BJP', 10), ('INC', 5),
            ('PMK', 5),  ('NTK', 5),  ('VCK', 4), ('OTH', 6),
        ],
        'other_parties': ['ADMK', 'BJP', 'INC', 'PMK', 'MDMK', 'VCK', 'NTK', 'AMMK', 'OTH'],
    },
    'wb': {
        'shapefile': 'ac/WB_AC_clean.shp',
        'csv_file': 'election_results_wb.csv',
        'win_weights': [
            ('TMC', 50), ('BJP', 30), ('INC', 5), ('CPIM', 6), ('ISF', 4), ('OTH', 5),
        ],
        'other_parties': ['TMC', 'BJP', 'INC', 'CPIM', 'RSP', 'ISF', 'OTH'],
    },
    'assam': {
        'shapefile': 'ac/Assam_AC_clean.shp',
        'csv_file': 'election_results_assam.csv',
        'win_weights': [
            ('BJP', 40), ('INC', 25), ('AGP', 10), ('AIUDF', 10),
            ('UPPL', 5),  ('AJP', 5),  ('OTH', 5),
        ],
        'other_parties': ['BJP', 'INC', 'AGP', 'AIUDF', 'UPPL', 'BPF', 'AJP', 'OTH'],
    },
    'kerala': {
        'shapefile': 'ac/Kerala_AC_clean.shp',
        'csv_file': 'election_results_kerala.csv',
        'win_weights': [
            ('CPIM', 30), ('INC', 25), ('CPI', 10), ('IUML', 10),
            ('BJP', 8),   ('KC(M)', 5), ('OTH', 12),
        ],
        'other_parties': ['CPIM', 'INC', 'CPI', 'IUML', 'KC(M)', 'NCP', 'BJP', 'RSP', 'JD(S)', 'KEC', 'OTH'],
    },
    'puducherry': {
        'shapefile': 'ac/Puducherry_AC_clean.shp',
        'csv_file': 'election_results_puducherry.csv',
        'win_weights': [
            ('INC', 10), ('AINRC', 8), ('DMK', 6), ('BJP', 4), ('OTH', 2),
        ],
        'other_parties': ['INC', 'DMK', 'BJP', 'AINRC', 'ADMK', 'NR', 'OTH'],
    },
}

CANDIDATE_NAMES = [
    'A. Kumar', 'B. Singh', 'C. Sharma', 'D. Patel', 'E. Reddy',
    'F. Nair', 'G. Rao', 'H. Das', 'I. Mehta', 'J. Pillai',
    'K. Iyer', 'L. Verma', 'M. Gupta', 'N. Joshi', 'O. Mishra',
    'P. Bose', 'Q. Menon', 'R. Sinha', 'S. Tiwari', 'T. Pandey',
    'U. Chatterjee', 'V. Mukherjee', 'W. Banerjee', 'X. Sen', 'Y. Ghosh',
]

def weighted_choice(weights):
    parties, wts = zip(*weights)
    return random.choices(parties, weights=wts, k=1)[0]

def pick_other(pool, exclude):
    choices = [p for p in pool if p != exclude]
    return random.choice(choices)

def gen_votes():
    """Generate win/sec/thi vote counts with realistic margins."""
    total = random.randint(80_000, 200_000)
    win_pct = random.uniform(0.35, 0.55)
    sec_pct = random.uniform(0.25, win_pct - 0.05)
    win = int(total * win_pct)
    sec = int(total * sec_pct)
    thi = int(total * random.uniform(0.05, 0.12))
    # Clamp so win > sec > thi
    sec = min(sec, win - 1000)
    thi = min(thi, sec - 500)
    return win, sec, thi, win + sec + thi + random.randint(5000, 20000)

def generate(state_code, cfg):
    gdf = gpd.read_file(cfg['shapefile'])
    gdf = gdf.sort_values('AC_NO').reset_index(drop=True)

    rows = []
    for _, row in gdf.iterrows():
        ac_no = int(row['AC_NO'])
        name  = str(row['AC_NAME']).strip().title()

        win_party = weighted_choice(cfg['win_weights'])
        sec_party = pick_other(cfg['other_parties'], win_party)
        thi_party = pick_other(cfg['other_parties'], win_party)
        if thi_party == sec_party:
            thi_party = pick_other(cfg['other_parties'], sec_party)

        win_c = random.choice(CANDIDATE_NAMES)
        sec_c = random.choice([c for c in CANDIDATE_NAMES if c != win_c])
        thi_c = random.choice([c for c in CANDIDATE_NAMES if c not in (win_c, sec_c)])

        win_v, sec_v, thi_v, tot_v = gen_votes()
        margin = win_v - sec_v
        votes_pct = round(random.uniform(55.0, 80.0), 2)

        rows.append({
            'AC_NO':      ac_no,
            'Constituency': name,
            'win_cand':   win_c,
            'win_party':  win_party,
            'win_votes':  win_v,
            'sec_cand':   sec_c,
            'sec_party':  sec_party,
            'sec_votes':  sec_v,
            'thi_cand':   thi_c,
            'thi_party':  thi_party,
            'thi_votes':  thi_v,
            'margin':     margin,
            'tot_votes':  tot_v,
            'votes_pct':  votes_pct,
        })

    df = pd.DataFrame(rows)
    df.to_csv(cfg['csv_file'], index=False)
    print(f"[{state_code.upper():12s}] {len(df):3d} rows → {cfg['csv_file']}")


if __name__ == '__main__':
    for state_code, cfg in STATE_PARTIES.items():
        generate(state_code, cfg)
    print("\nDone. Commit these CSVs to test the map app.")
