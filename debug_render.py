import pandas as pd
import geopandas as gpd
import requests
from io import StringIO

# Simulate the exact flow in create_election_map
print("=== SIMULATING MAP RENDERING ===\n")

# Step 1: Fetch live data from GitHub
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    response = requests.get('https://github.com/abhi0420/Election-tracker/raw/main/election_results.csv', headers=headers, timeout=10)
    live_data = pd.read_csv(StringIO(response.text))
    print(f"[LIVE] Fetched {len(live_data)} rows from GitHub")
except:
    live_data = pd.read_csv('election_results.csv')
    print(f"[LOCAL] Using local CSV - {len(live_data)} rows")

print("\n[LIVE DATA] AC 127:", live_data[live_data['AC_NO'] == 127][['AC_NO', 'Constituency', 'win_cand']].values)
print("[LIVE DATA] AC 128:", live_data[live_data['AC_NO'] == 128][['AC_NO', 'Constituency', 'win_cand']].values)

# Step 2: Read shapefile
gdf = gpd.read_file('ac/Bihar_AC_with_results.shp')
state_gdf = gdf[gdf['ST_NAME'].str.contains('Bihar', case=False, na=False)].copy()
print(f"\n[SHAPEFILE] Read {len(state_gdf)} constituencies")

# Step 3: Drop old election columns
election_columns = ['win_party', 'win_cand', 'win_votes', 
                   'sec_party', 'sec_cand', 'sec_votes',
                   'thi_party', 'thi_cand', 'thi_votes', 
                   'tot_votes', 'votes_pct']

for col in election_columns:
    if col in state_gdf.columns:
        state_gdf = state_gdf.drop(columns=[col])

# Step 4: Merge with live data
state_gdf = state_gdf.merge(live_data, on='AC_NO', how='left')
print(f"[MERGE] Merged data")

print("\n[AFTER MERGE] AC 127:", state_gdf[state_gdf['AC_NO'] == 127][['AC_NO', 'AC_NAME', 'win_cand']].values)
print("[AFTER MERGE] AC 128:", state_gdf[state_gdf['AC_NO'] == 128][['AC_NO', 'AC_NAME', 'win_cand']].values)

# Step 5: Rename columns to match popup JavaScript
rename_map = {
    'win_party': 'winning_party',
    'win_cand': 'winner_candidate',
    'win_votes': 'winner_votes',
    'sec_party': 'second_party',
    'sec_cand': 'second_candidate',
    'sec_votes': 'second_votes',
    'thi_party': 'third_party',
    'thi_cand': 'third_candidate',
    'thi_votes': 'third_votes',
    'tot_votes': 'total_votes',
    'votes_pct': 'votes_counted_percent'
}
state_gdf = state_gdf.rename(columns=rename_map)

print("\n[AFTER RENAME] AC 127:", state_gdf[state_gdf['AC_NO'] == 127][['AC_NO', 'AC_NAME', 'winner_candidate']].values)
print("[AFTER RENAME] AC 128:", state_gdf[state_gdf['AC_NO'] == 128][['AC_NO', 'AC_NAME', 'winner_candidate']].values)

# Step 6: Sort by AC_NO (THE FIX)
state_gdf = state_gdf.sort_values('AC_NO').reset_index(drop=True)
print(f"\n[SORTED] By AC_NO")

# Step 7: Check final data
print("\n=== FINAL RENDERED DATA ===")
print("Row index 126 (should be AC 127):", state_gdf.iloc[126][['AC_NO', 'AC_NAME', 'winner_candidate']].values)
print("Row index 127 (should be AC 128):", state_gdf.iloc[127][['AC_NO', 'AC_NAME', 'winner_candidate']].values)

print("\n=== WHAT JAVASCRIPT WILL SHOW ===")
print("When clicking Raja Pakar (AC 127), JavaScript fetches row 126:")
print("  AC_NO:", state_gdf.iloc[126]['AC_NO'])
print("  Constituency:", state_gdf.iloc[126]['AC_NAME'])
print("  Winner:", state_gdf.iloc[126]['winner_candidate'])
print("  Party:", state_gdf.iloc[126]['winning_party'])
