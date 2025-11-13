import geopandas as gpd
import pandas as pd

def merge_election_data(shapefile_path='ac/Bihar_AC_clean.shp', csv_path='election_results.csv', output_path='ac/Bihar_AC_with_results.shp'):
    """
    Merge election results CSV with Bihar shapefile based on AC_NO
    """
    # Read shapefile
    print(f"Reading shapefile: {shapefile_path}")
    gdf = gpd.read_file(shapefile_path)
    
    # Read CSV
    print(f"Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Ensure AC_NO is the same type in both
    gdf['AC_NO'] = gdf['AC_NO'].astype(int)
    df['AC_NO'] = df['AC_NO'].astype(int)
    
    # Rename CSV columns to be shapefile-friendly (10 char max, no special chars)
    # Keep only essential columns for shapefile storage
    df_clean = df.rename(columns={
        'winning_party': 'win_party',
        'winner_candidate': 'win_cand',
        'winner_votes': 'win_votes',
        'second_party': 'sec_party',
        'second_candidate': 'sec_cand',
        'second_votes': 'sec_votes',
        'third_party': 'thi_party',
        'third_candidate': 'thi_cand',
        'third_votes': 'thi_votes',
        'total_votes': 'tot_votes',
        'votes_counted_percent': 'votes_pct'
    })
    
    # Keep only the renamed columns
    cols_to_keep = ['AC_NO', 'win_party', 'win_cand', 'win_votes', 
                    'sec_party', 'sec_cand', 'sec_votes',
                    'thi_party', 'thi_cand', 'thi_votes', 
                    'tot_votes', 'votes_pct']
    df_clean = df_clean[cols_to_keep]
    
    # Merge on AC_NO
    print("Merging data based on AC_NO...")
    gdf_merged = gdf.merge(df_clean, on='AC_NO', how='left')
    
    # Save merged shapefile
    print(f"Saving merged shapefile: {output_path}")
    gdf_merged.to_file(output_path)
    
    print(f"\nMerge complete!")
    print(f"Total constituencies: {len(gdf_merged)}")
    print(f"Constituencies with data: {gdf_merged['win_party'].notna().sum()}")
    print("\nColumns in merged shapefile:")
    print(gdf_merged.columns.tolist())
    
    return gdf_merged

if __name__ == "__main__":
    merge_election_data()