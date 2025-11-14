import pandas as pd
import geopandas as gpd

# Simulate the exact merge that happens in create_election_map
live_data = pd.read_csv('election_results.csv')
gdf = gpd.read_file('ac/Bihar_AC_with_results.shp')
state_gdf = gdf.copy()

# Drop election columns
election_columns = ['win_party', 'win_cand', 'win_votes', 
                   'sec_party', 'sec_cand', 'sec_votes',
                   'thi_party', 'thi_cand', 'thi_votes', 
                   'tot_votes', 'votes_pct']

for col in election_columns:
    if col in state_gdf.columns:
        state_gdf = state_gdf.drop(columns=[col])

print("Before merge:")
print("Shapefile AC 127:", gdf[gdf['AC_NO'] == 127][['AC_NO', 'AC_NAME']].values)
print("Shapefile AC 128:", gdf[gdf['AC_NO'] == 128][['AC_NO', 'AC_NAME']].values)

# Merge with live data
merged = state_gdf.merge(live_data, on='AC_NO', how='left')

print("\nAfter merge:")
print("Merged AC 127:", merged[merged['AC_NO'] == 127][['AC_NO', 'AC_NAME', 'win_cand']].values)
print("Merged AC 128:", merged[merged['AC_NO'] == 128][['AC_NO', 'AC_NAME', 'win_cand']].values)

print("\nRow index check:")
print("Row 126 (index):", merged.iloc[126]['AC_NO'], merged.iloc[126].get('AC_NAME', 'N/A'), merged.iloc[126]['win_cand'])
print("Row 127 (index):", merged.iloc[127]['AC_NO'], merged.iloc[127].get('AC_NAME', 'N/A'), merged.iloc[127]['win_cand'])
