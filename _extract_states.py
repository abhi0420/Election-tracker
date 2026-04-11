"""Extract clean shapefiles (geometry + base columns only) for each target state from India_AC.shp"""
import geopandas as gpd
import os

gdf = gpd.read_file('ac/India_AC.shp')

# Columns to keep (geometry-only, no election data)
keep_cols = ['ST_CODE', 'ST_NAME', 'DT_CODE', 'DIST_NAME', 'AC_NO', 'AC_NAME', 'PC_NO', 'PC_NAME', 'geometry']

states = {
    'TAMIL NADU': 'TN_AC_clean',
    'WEST BENGAL': 'WB_AC_clean',
    'ASSAM': 'Assam_AC_clean',
    'KERALA': 'Kerala_AC_clean',
    'PUDUCHERRY': 'Puducherry_AC_clean',
}

for st_name, filename in states.items():
    sub = gdf[gdf['ST_NAME'] == st_name][keep_cols].copy()
    sub['AC_NO'] = sub['AC_NO'].astype(int)
    out_path = f'ac/{filename}.shp'
    sub.to_file(out_path)
    print(f"Saved {out_path}: {len(sub)} constituencies")

print("Done!")
