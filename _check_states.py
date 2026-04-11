import geopandas as gpd
gdf = gpd.read_file('ac/India_AC.shp')
targets = ['TAMIL NADU','WEST BENGAL','ASSAM','KERALA','PUDUCHERRY','BIHAR']
for s in targets:
    sub = gdf[gdf['ST_NAME']==s]
    print(f"{s}: {len(sub)} ACs, ST_CODE={sub['ST_CODE'].iloc[0]}, PCs={sub['PC_NAME'].nunique()}")
print("\nColumns:", gdf.columns.tolist())
