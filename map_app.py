from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import geopandas as gpd
from bokeh.plotting import figure
from bokeh.models import HoverTool, GeoJSONDataSource, Legend, LegendItem, Div, TapTool, CustomJS, Select, Range1d
from bokeh.layouts import row, column
from bokeh.palettes import Category20
from bokeh.transform import factor_cmap
from bokeh.embed import components, file_html
from bokeh.resources import CDN
import pandas as pd
import numpy as np
import requests
from io import StringIO
import os
import json
import re
from state_config import ALL_STATES, DEFAULT_STATE, get_state_config, get_party_to_alliance, get_alliance_colors, normalize_party_name as normalize_party



app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-for-local-testing')

# ── Previous election results cache + fetcher ─────────────────────────────────
_prev_results_cache = {}

from html.parser import HTMLParser

class _EciTableParser(HTMLParser):
    """Lightweight HTML table parser for ECI result archive pages."""
    def __init__(self):
        super().__init__()
        self._tables = []
        self._cur_table = None
        self._cur_row = None
        self._cur_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._cur_table = []
        elif tag == 'tr' and self._cur_table is not None:
            self._cur_row = []
        elif tag in ('td', 'th') and self._cur_row is not None:
            self._cur_cell = ''

    def handle_endtag(self, tag):
        if tag == 'table' and self._cur_table is not None:
            self._tables.append(self._cur_table)
            self._cur_table = None
        elif tag == 'tr' and self._cur_table is not None and self._cur_row is not None:
            if self._cur_row:
                self._cur_table.append(self._cur_row)
            self._cur_row = None
        elif tag in ('td', 'th') and self._cur_row is not None and self._cur_cell is not None:
            self._cur_row.append(self._cur_cell.strip())
            self._cur_cell = None

    def handle_data(self, data):
        if self._cur_cell is not None:
            self._cur_cell += data

    @property
    def tables(self):
        return self._tables


@app.route('/api/prev-results/<state_code>/<int:ac_no>')
def prev_results_api(state_code, ac_no):
    """Fetch previous election constituency results from ECI archive."""
    cache_key = f"{state_code}_{ac_no}"
    if cache_key in _prev_results_cache:
        return jsonify(_prev_results_cache[cache_key])

    sc = get_state_config(state_code)
    if sc is None:
        return jsonify({'error': 'Unknown state'}), 404
    if 'prev_election_event' not in sc:
        return jsonify({'error': '2021 election data not available for this seat'}), 404

    prev_event = sc['prev_election_event']
    eci_code = sc['eci_state_code']
    prev_year = sc.get('prev_year', 'Previous')
    party_name_map = sc.get('party_name_map', {})

    hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    urls = [
        f"https://results.eci.gov.in/{prev_event}/Constituencywise-{eci_code}{ac_no}.htm",
        f"https://results.eci.gov.in/{prev_event}/candidateswise-{eci_code}{ac_no}.htm",
    ]

    table_rows = None
    page_text = ''
    for url in urls:
        try:
            resp = requests.get(url, timeout=15, headers=hdrs)
            if resp.status_code != 200:
                continue
            page_text = resp.text
            parser = _EciTableParser()
            parser.feed(page_text)
            for tbl in parser.tables:
                if len(tbl) >= 3:
                    table_rows = tbl
                    break
            if table_rows:
                break
        except Exception:
            continue

    if not table_rows:
        result = {'error': 'Previous results not available (ECI archive unreachable or no data).'}
        return jsonify(result), 503

    # Determine column indices (standard ECI format: SNo, Candidate, Party, EVM, Postal, Total, %)
    def _to_int(v):
        try:
            return int(str(v).replace(',', '').strip())
        except Exception:
            return 0

    def _to_float(v):
        try:
            return round(float(str(v).replace('%', '').strip()), 2)
        except Exception:
            return 0.0

    candidates = []
    for row in table_rows:
        if len(row) < 4:
            continue
        # Skip header rows
        if any(cell.lower() in ('candidate', 'party', 'sno', 'sl. no.', 'sl no', 'serial no') for cell in row[:3]):
            continue
        ncols = len(row)
        cand = row[1].strip() if ncols > 1 else ''
        party_raw = row[2].strip() if ncols > 2 else ''
        total = _to_int(row[5]) if ncols > 5 else _to_int(row[3])
        pct = _to_float(row[6]) if ncols > 6 else (_to_float(row[4]) if ncols > 4 else 0.0)
        if cand and total > 0:
            party = party_name_map.get(party_raw, party_raw)
            candidates.append({'candidate': cand, 'party': party, 'votes': total, 'percent': pct})

    if not candidates:
        result = {'error': 'Could not parse candidate data from previous results.'}
        return jsonify(result), 503

    candidates.sort(key=lambda x: -x['votes'])
    if len(candidates) >= 2:
        candidates[0]['margin'] = candidates[0]['votes'] - candidates[1]['votes']

    # Try to extract constituency name from page title
    m = re.search(r'<title[^>]*>(.*?)</title>', page_text, re.IGNORECASE | re.DOTALL)
    cname = m.group(1).strip() if m else f'AC {ac_no}'

    result = {
        'year': prev_year,
        'constituency': cname,
        'results': candidates[:3],
    }
    _prev_results_cache[cache_key] = result
    return jsonify(result)

# Shapefile paths per state (clean = geometry only, results = merged with data)
STATE_SHAPEFILE_MAP = {
    'tn': {'clean': 'ac/TN_AC_clean.shp', 'results': 'ac/TN_AC_with_results.shp'},
    'wb': {'clean': 'ac/WB_AC_clean.shp', 'results': 'ac/WB_AC_with_results.shp'},
    'assam': {'clean': 'ac/Assam_AC_clean.shp', 'results': 'ac/Assam_AC_with_results.shp'},
    'kerala': {'clean': 'ac/Kerala_AC_clean.shp', 'results': 'ac/Kerala_AC_with_results.shp'},
    'puducherry': {'clean': 'ac/Puducherry_AC_clean.shp', 'results': 'ac/Puducherry_AC_with_results.shp'},
}

# GitHub repository info for fetching live data
GITHUB_REPO = "abhi0420/Election-tracker"
GITHUB_BRANCH = "main"

def get_github_url(csv_filename='election_results.csv'):
    """Generate GitHub API URL with optional token for private repos"""
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{csv_filename}?ref={GITHUB_BRANCH}", token
    else:
        return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{csv_filename}", None

def auto_merge_election_data(state_code=None):
    """
    Automatically merge election CSV with shapefile if needed
    Returns the merged GeoDataFrame or None if merge fails
    """
    if state_code is None:
        state_code = DEFAULT_STATE
    try:
        sc = get_state_config(state_code)
        csv_file = sc['csv_file']
        paths = STATE_SHAPEFILE_MAP.get(state_code)
        results_shapefile = paths['results']

        print(f"[AUTO-MERGE] Starting auto-merge for {sc['name']}...")
        
        # Check if CSV exists
        if not os.path.exists(csv_file):
            print(f"[AUTO-MERGE] {csv_file} not found, skipping auto-merge")
            return None
        
        # Read shapefile (use clean version without results)
        clean_shapefile = paths['clean']
        if not os.path.exists(clean_shapefile):
            print(f"[AUTO-MERGE] {clean_shapefile} not found, using results shapefile")
            clean_shapefile = results_shapefile
        
        print(f"[AUTO-MERGE] Reading shapefile: {clean_shapefile}")
        gdf = gpd.read_file(clean_shapefile)
        print(f"[AUTO-MERGE] Shapefile columns: {gdf.columns.tolist()}")
        
        # Read CSV
        print(f"[AUTO-MERGE] Reading {csv_file}")
        df = pd.read_csv(csv_file)
        print(f"[AUTO-MERGE] CSV columns: {df.columns.tolist()}")
        print(f"[AUTO-MERGE] CSV rows: {len(df)}")
        
        # Check if AC_NO exists in both
        if 'AC_NO' not in gdf.columns:
            print("[AUTO-MERGE] AC_NO not found in shapefile")
            return None
        
        if 'AC_NO' not in df.columns:
            print("[AUTO-MERGE] AC_NO not found in CSV")
            return None
        
        # Ensure AC_NO is the same type in both
        gdf['AC_NO'] = gdf['AC_NO'].astype(int)
        df['AC_NO'] = df['AC_NO'].astype(int)
        
        # Rename CSV columns to be shapefile-friendly (only rename if they exist)
        rename_map = {}
        if 'winning_party' in df.columns:
            rename_map['winning_party'] = 'win_party'
        if 'winner_candidate' in df.columns:
            rename_map['winner_candidate'] = 'win_cand'
        if 'winner_votes' in df.columns:
            rename_map['winner_votes'] = 'win_votes'
        if 'second_party' in df.columns:
            rename_map['second_party'] = 'sec_party'
        if 'second_candidate' in df.columns:
            rename_map['second_candidate'] = 'sec_cand'
        if 'second_votes' in df.columns:
            rename_map['second_votes'] = 'sec_votes'
        if 'third_party' in df.columns:
            rename_map['third_party'] = 'thi_party'
        if 'third_candidate' in df.columns:
            rename_map['third_candidate'] = 'thi_cand'
        if 'third_votes' in df.columns:
            rename_map['third_votes'] = 'thi_votes'
        if 'total_votes' in df.columns:
            rename_map['total_votes'] = 'tot_votes'
        if 'Total Votes' in df.columns:  # Handle "Total Votes" with space
            rename_map['Total Votes'] = 'tot_votes'
        if 'votes_counted_percent' in df.columns:
            rename_map['votes_counted_percent'] = 'votes_pct'
        
        df_clean = df.rename(columns=rename_map)
        
        # Add votes_pct column if missing (default to 100%)
        if 'votes_pct' not in df_clean.columns:
            df_clean['votes_pct'] = 100.0
            print("   Added default votes_pct column (100%)")
        
        # Keep only the columns that exist
        cols_to_keep = ['AC_NO']
        for col in ['win_party', 'win_cand', 'win_votes', 
                    'sec_party', 'sec_cand', 'sec_votes',
                    'thi_party', 'thi_cand', 'thi_votes', 
                    'tot_votes', 'votes_pct']:
            if col in df_clean.columns:
                cols_to_keep.append(col)
        
        df_clean = df_clean[cols_to_keep]
        print(f"[AUTO-MERGE] Columns to merge: {cols_to_keep}")
        
        # Merge on AC_NO
        print("[AUTO-MERGE] Merging data...")
        gdf_merged = gdf.merge(df_clean, on='AC_NO', how='left')
        
        # Fill missing data with "Awaiting Results"
        print("[AUTO-MERGE] Filling missing constituencies with 'Awaiting Results'...")
        gdf_merged['win_party'] = gdf_merged['win_party'].fillna('AWAITED')
        gdf_merged['win_cand'] = gdf_merged['win_cand'].fillna('Awaiting Results')
        gdf_merged['win_votes'] = gdf_merged['win_votes'].fillna(0).astype(int)
        gdf_merged['sec_party'] = gdf_merged['sec_party'].fillna('AWAITED')
        gdf_merged['sec_cand'] = gdf_merged['sec_cand'].fillna('Awaiting Results')
        gdf_merged['sec_votes'] = gdf_merged['sec_votes'].fillna(0).astype(int)
        gdf_merged['thi_party'] = gdf_merged['thi_party'].fillna('AWAITED')
        gdf_merged['thi_cand'] = gdf_merged['thi_cand'].fillna('Awaiting Results')
        gdf_merged['thi_votes'] = gdf_merged['thi_votes'].fillna(0).astype(int)
        gdf_merged['tot_votes'] = gdf_merged['tot_votes'].fillna(0).astype(int)
        # Handle votes_pct - replace inf/nan with 0, then convert to float (not int to preserve decimals)
        gdf_merged['votes_pct'] = gdf_merged['votes_pct'].replace([float('inf'), float('-inf')], 0).fillna(0).astype(float)
        
        # Save merged shapefile
        print(f"[AUTO-MERGE] Saving to {results_shapefile}")
        gdf_merged.to_file(results_shapefile)
        
        print(f"[AUTO-MERGE] Complete! {gdf_merged['win_party'].notna().sum() if 'win_party' in gdf_merged.columns else 0} constituencies merged")
        return gdf_merged
        
    except Exception as e:
        import traceback
        print(f"[AUTO-MERGE] Failed with error:")
        traceback.print_exc()
        return None

def get_live_election_data(state_code=None):
    """Fetch latest election results CSV from GitHub"""
    if state_code is None:
        state_code = DEFAULT_STATE
    sc = get_state_config(state_code)
    csv_file = sc['csv_file']
    url, token = get_github_url(csv_file)
    try:
        hdrs = {}
        if token:
            hdrs['Authorization'] = f'token {token}'
        resp = requests.get(url, timeout=15, headers=hdrs)
        resp.raise_for_status()
        if token:
            import base64 as _b64
            data = json.loads(resp.text)
            content = _b64.b64decode(data['content']).decode('utf-8')
        else:
            content = resp.text
        df = pd.read_csv(StringIO(content))
        print(f"[GITHUB DATA] Read {len(df)} rows from {csv_file}")
        return df
    except Exception as e:
        print(f"[GITHUB DATA] Failed to fetch {csv_file}: {e}")
        return None

def get_available_states():
    """Get list of all available states"""
    return sorted([sc['name'] for sc in ALL_STATES.values()])

def create_state_map(state_name):
    """Create a Bokeh map for the specified state"""
    try:
        # Read shapefile and filter for the state
        gdf = gpd.read_file('ac/India_AC.shp')
        state_gdf = gdf[gdf['ST_NAME'].str.contains(state_name, case=False, na=False)].copy()
        
        if len(state_gdf) == 0:
            return None, f"State '{state_name}' not found!"
        
        # Convert to Web Mercator for Bokeh
        state_gdf = state_gdf.to_crs(epsg=3857)
        
        # Calculate bounds for proper zoom
        bounds = state_gdf.total_bounds
        x_range = (bounds[0], bounds[2])
        y_range = (bounds[1], bounds[3])
        
        # Add some padding
        x_pad = (x_range[1] - x_range[0]) * 0.1
        y_pad = (y_range[1] - y_range[0]) * 0.1
        
        # Create the plot
        p = figure(
            title=f"{state_name} - {len(state_gdf)} Constituencies",
            width=900,
            height=700,
            tools="pan,wheel_zoom,box_zoom,reset,save",
            x_axis_type="mercator",
            y_axis_type="mercator",
            background_fill_color="#f0f0f0",
            x_range=(x_range[0] - x_pad, x_range[1] + x_pad),
            y_range=(y_range[0] - y_pad, y_range[1] + y_pad)
        )
        
        # Convert to GeoJSON and plot
        geosource = GeoJSONDataSource(geojson=state_gdf.to_json())
        
        # Add constituencies
        constituencies = p.patches(
            'xs', 'ys', 
            source=geosource,
            fill_color='#3498db',
            fill_alpha=0.6,
            line_color="black",
            line_width=1.5,
            hover_fill_color='#e74c3c',
            hover_fill_alpha=0.8
        )
        
        # Add hover tooltips
        hover = HoverTool(
            tooltips=[
                ("Constituency", "@AC_NAME"), 
                ("District", "@DIST_NAME"),
                ("State", "@ST_NAME")
            ],
            renderers=[constituencies]
        )
        p.add_tools(hover)
        
        # Style the plot
        p.title.text_font_size = "16pt"
        p.title.align = "center"
        p.xgrid.grid_line_color = None
        p.ygrid.grid_line_color = None
        
        return p, len(state_gdf)
    
    except Exception as e:
        return None, f"Error creating map: {str(e)}"

def create_election_map(state_name, state_code=None):
    """Create election results map with party data - now uses LIVE data from GitHub"""
    try:
        import traceback
        
        # Resolve state_code from state_name if not provided
        if state_code is None:
            # Try to find state_code from state_name
            for code, cfg in ALL_STATES.items():
                if cfg['name'].lower() == state_name.lower():
                    state_code = code
                    break
            if state_code is None:
                state_code = DEFAULT_STATE
        
        sc = get_state_config(state_code)
        if sc is None:
            return None, f"Unknown state code: {state_code}", {}, {}, {}
        
        state_name = sc['name']
        
        # Fetch LIVE election data from GitHub
        live_data = get_live_election_data(state_code=state_code)
        
        # Read shapefile
        paths = STATE_SHAPEFILE_MAP.get(state_code)
        if paths is None:
            return None, f"No shapefile configured for state: {state_code}", {}, {}, {}
        shapefile_path = paths['results'] if os.path.exists(paths['results']) else paths['clean']
        gdf = gpd.read_file(shapefile_path)
        state_gdf = gdf.copy()  # Already state-specific shapefile
        
        if len(state_gdf) == 0:
            return None, f"State '{state_name}' not found in shapefile!", {}, {}, {}
        
        # If we have live data, merge it with shapefile (replace old data with live data)
        if live_data is not None:
            # Drop old election columns from shapefile (but KEEP AC_NO for merging!)
            election_columns = ['winning_party', 'winner_candidate', 'winner_votes',
                              'second_party', 'second_candidate', 'second_votes',
                              'third_party', 'third_candidate', 'third_votes',
                              'total_votes', 'votes_counted_percent',
                              'win_party', 'win_cand', 'win_votes',
                              'sec_party', 'sec_cand', 'sec_votes',
                              'thi_party', 'thi_cand', 'thi_votes',
                              'tot_votes', 'votes_pct']
            
            for col in election_columns:
                if col in state_gdf.columns:
                    state_gdf = state_gdf.drop(columns=[col])
            
            # Merge with live data based on AC_NO (AC_NO must exist in shapefile!)
            if 'AC_NO' in state_gdf.columns:
                state_gdf = state_gdf.merge(live_data, on='AC_NO', how='left')
                print("[MERGE] Merged live data with shapefile on AC_NO")
            else:
                print("[ERROR] AC_NO not found in shapefile - cannot merge!")
                return None, "AC_NO column missing from shapefile", {}, {}, {}
        
        # Use state config for parties, colors, alliances
        individual_parties = sc['parties']
        individual_party_colors = sc['party_colors']
        party_to_alliance = get_party_to_alliance(sc)
        alliance_colors_map = get_alliance_colors(sc)
        alliance_list = list(sc['alliances'].keys()) + ['AWAITED']
        
        # Check if election data columns exist in shapefile (clean column names from merge_data.py)
        required_columns = ['win_party', 'win_cand', 'win_votes',
                          'sec_party', 'sec_cand', 'sec_votes',
                          'thi_party', 'thi_cand', 'thi_votes',
                          'tot_votes', 'votes_pct']
        
        if not all(col in state_gdf.columns for col in required_columns):
            print("[AUTO-MERGE] Election data columns not found, attempting auto-merge...")
            merged_gdf = auto_merge_election_data(state_code=state_code)
            
            if merged_gdf is not None:
                # Re-read the shapefile after merge
                gdf = gpd.read_file(shapefile_path)
                state_gdf = gdf.copy()
                print("[AUTO-MERGE] Using auto-merged data")
            else:
                # No data available — fill all constituencies with AWAITED
                print("[AUTO-MERGE] No data available, showing all seats as AWAITED")
                for col in required_columns:
                    if col not in state_gdf.columns:
                        if 'party' in col:
                            state_gdf[col] = 'AWAITED'
                        elif 'cand' in col:
                            state_gdf[col] = 'Awaiting Results'
                        else:
                            state_gdf[col] = 0
        
        print("[DATA] Using election data from shapefile")
        
        # Calculate derived fields using pandas (not stored in shapefile)
        # Ensure numeric columns are proper type first
        state_gdf['win_votes'] = pd.to_numeric(state_gdf['win_votes'], errors='coerce').fillna(0)
        state_gdf['sec_votes'] = pd.to_numeric(state_gdf['sec_votes'], errors='coerce').fillna(0)
        state_gdf['thi_votes'] = pd.to_numeric(state_gdf['thi_votes'], errors='coerce').fillna(0)
        state_gdf['tot_votes'] = pd.to_numeric(state_gdf['tot_votes'], errors='coerce').fillna(0)
        state_gdf['votes_pct'] = pd.to_numeric(state_gdf['votes_pct'], errors='coerce').fillna(0).clip(upper=100)
        
        # Calculate percentages and margins (round to 2 decimal places)
        state_gdf['winner_percent'] = ((state_gdf['win_votes'] / state_gdf['tot_votes'].replace(0, 1) * 100) * 100).round() / 100
        state_gdf['second_percent'] = ((state_gdf['sec_votes'] / state_gdf['tot_votes'].replace(0, 1) * 100) * 100).round() / 100
        state_gdf['third_percent'] = ((state_gdf['thi_votes'] / state_gdf['tot_votes'].replace(0, 1) * 100) * 100).round() / 100
        state_gdf['lead_margin'] = (state_gdf['win_votes'] - state_gdf['sec_votes']).fillna(0).astype(int)
        
        # Create friendly column aliases for use in code below
        state_gdf['winning_party'] = state_gdf['win_party'].fillna('AWAITED')
        state_gdf['winner_candidate'] = state_gdf['win_cand'].fillna('Awaiting Results')
        state_gdf['winner_votes'] = state_gdf['win_votes']
        state_gdf['second_party'] = state_gdf['sec_party'].fillna('AWAITED')
        state_gdf['second_candidate'] = state_gdf['sec_cand'].fillna('Awaiting Results')
        state_gdf['second_votes'] = state_gdf['sec_votes']
        state_gdf['third_party'] = state_gdf['thi_party'].fillna('AWAITED')
        state_gdf['third_candidate'] = state_gdf['thi_cand'].fillna('Awaiting Results')
        state_gdf['third_votes'] = state_gdf['thi_votes']
        state_gdf['total_votes'] = state_gdf['tot_votes']
        state_gdf['votes_counted_percent'] = state_gdf['votes_pct']
        
        # Calculate all party votes for vote share calculations
        all_party_votes = []
        for idx, r in state_gdf.iterrows():
            # For now, we only have top 3 parties, so we'll use those for vote share
            # In real data, you might have all parties listed
            # Filter out nan/null parties
            constituency_votes = {}
            if pd.notna(r['win_party']) and r['win_party'] != 'AWAITED':
                constituency_votes[r['win_party']] = r['win_votes']
            if pd.notna(r['sec_party']) and r['sec_party'] != 'AWAITED':
                constituency_votes[r['sec_party']] = r['sec_votes']
            if pd.notna(r['thi_party']) and r['thi_party'] != 'AWAITED':
                constituency_votes[r['thi_party']] = r['thi_votes']
            all_party_votes.append(constituency_votes)
        
        # Convert to Web Mercator
        state_gdf = state_gdf.to_crs(epsg=3857)
        
        # Calculate bounds
        bounds = state_gdf.total_bounds
        x_range = (bounds[0], bounds[2])
        y_range = (bounds[1], bounds[3])
        x_pad = (x_range[1] - x_range[0]) * 0.1
        y_pad = (y_range[1] - y_range[0]) * 0.1

        # Use per-state default bounds if configured (e.g. Puducherry zooms to main enclave)
        default_bounds = sc.get('map_default_bounds')
        if default_bounds:
            ix0, ix1 = default_bounds['x']
            iy0, iy1 = default_bounds['y']
            print(f"[BOUNDS] Using custom bounds: x={default_bounds['x']}, y={default_bounds['y']}")
        else:
            ix0, ix1 = x_range[0] - x_pad, x_range[1] + x_pad
            iy0, iy1 = y_range[0] - y_pad, y_range[1] + y_pad

        init_x_range = Range1d(ix0, ix1)
        init_y_range = Range1d(iy0, iy1)

        # Compute figure height from the initial view aspect ratio
        map_width = 800
        x_span = (ix1 - ix0) or 1
        y_span = (iy1 - iy0) or 1
        aspect = y_span / x_span
        map_height = int(max(450, min(950, map_width * aspect)))

        # Create plot
        p = figure(
            title=f"{state_name} - Live Election Results {sc['year']}",
            width=map_width,
            height=map_height,
            tools="pan,wheel_zoom,box_zoom,reset",
            toolbar_location=None,  # Remove toolbar
            x_axis_type="mercator",
            y_axis_type="mercator",
            background_fill_color="#f0f0f0",
            x_range=init_x_range,
            y_range=init_y_range
        )
        
        # Convert to GeoJSON
        geosource = GeoJSONDataSource(geojson=state_gdf.to_json())
        
        # Map party names to colors for the color mapper (default: party-level)
        # Fill any unmapped parties with gray color
        state_gdf['party_color'] = state_gdf['winning_party'].map(individual_party_colors).fillna('#CCCCCC')
        
        # Map alliance colors (use dynamic state config, not hardcoded)
        state_gdf['alliance'] = state_gdf['winning_party'].map(party_to_alliance).fillna('AWAITED')
        state_gdf['alliance_color'] = state_gdf['alliance'].map(alliance_colors_map).fillna('#CCCCCC')
        
        # Default color is alliance-level
        state_gdf['color'] = state_gdf['alliance_color']
        
        geosource = GeoJSONDataSource(geojson=state_gdf.to_json())
        
        # Create single renderer with all constituencies
        renderer = p.patches(
            'xs', 'ys',
            source=geosource,
            fill_color='color',  # Use mapped colors
            fill_alpha=0.8,
            line_color="#CCCCCC",  # Light grey boundaries
            line_width=1,
            hover_line_color="yellow",
            hover_line_width=3,
            # Selection appearance - full color, same border
            selection_line_color="#888888",  # Medium grey for selected
            selection_line_width=1.5,
            selection_fill_alpha=1.0,
            # Non-selected constituencies are heavily dimmed (almost transparent)
            nonselection_fill_alpha=0.15,
            nonselection_line_alpha=0.3,
            name="main_renderer"
        )
        
        # Add hover tooltips (basic info) - works on all renderers
        hover = HoverTool(
            tooltips=[
                ("Constituency", "@AC_NAME"), 
                ("District", "@DIST_NAME"),
                ("Winning Party", "@winning_party"),
                ("Vote %", "@winner_percent%")
            ]
        )
        p.add_tools(hover)
        
        # Add TapTool for clicking on constituencies
        tap = TapTool()
        p.add_tools(tap)
        
        # Create click callback to show popup
        import json as _json
        _colors_js = _json.dumps(individual_party_colors)
        _top_parties_js = ''.join(
            f'<div style="padding: 8px 16px; background: linear-gradient(135deg, {color} 0%, {color}dd 100%); color: white; border-radius: 20px; font-size: 13px; font-weight: 600; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">{party}</div>'
            for party, color in list(individual_party_colors.items())[:3]
            if party not in ('OTH', 'AWAITED')
        )
        callback = CustomJS(args=dict(source=geosource), code="""
            const indices = source.selected.indices;
            
            // Check if this is a single-click (for popup) vs multi-select (for filtering)
            if (indices.length === 1) {
                const clicked_idx = indices[0];
                const data = source.data;
                
                // Get the AC_NO from the clicked polygon
                const clicked_ac_no = data['AC_NO'][clicked_idx];
                
                // CRITICAL FIX: Find the index where AC_NO matches (data might not be in AC_NO order)
                const ac_no_array = data['AC_NO'];
                let idx = clicked_idx;  // default to clicked index
                
                // Search for matching AC_NO in the data
                for (let i = 0; i < ac_no_array.length; i++) {
                    if (ac_no_array[i] === clicked_ac_no) {
                        idx = i;
                        break;
                    }
                }
                
                const ac_no = data['AC_NO'][idx];
                const constituency = data['AC_NAME'][idx];
                const district = data['DIST_NAME'][idx];
                
                console.log('DEBUG: Clicked idx=' + clicked_idx + ', Clicked AC_NO=' + clicked_ac_no + ', Found idx=' + idx + ', Data AC_NO=' + ac_no);
                
                const winner_party = data['winning_party'][idx];
                const winner_candidate = data['winner_candidate'][idx];
                const winner_votes = data['winner_votes'][idx];
                const winner_percent = data['winner_percent'][idx];
                
                const second_party = data['second_party'][idx];
                const second_candidate = data['second_candidate'][idx];
                const second_votes = data['second_votes'][idx];
                const second_percent = data['second_percent'][idx];
                
                const third_party = data['third_party'][idx];
                const third_candidate = data['third_candidate'][idx];
                const third_votes = data['third_votes'][idx];
                const third_percent = data['third_percent'][idx];
                
                const votes_counted = data['votes_counted_percent'][idx];
                const total_votes = data['total_votes'][idx];
                
                // Check if results are awaited
                const isAwaited = winner_party === 'AWAITED' || winner_candidate === 'Awaiting Results';
                
                // Color mapping
                const colors = __PARTY_COLORS__;
                
                // Remove existing modal if any
                const existingModal = document.getElementById('constituency-modal');
                if (existingModal) {
                    existingModal.remove();
                }
                
                // Create modal HTML
                const modalHTML = `
                    <div id="constituency-modal" style="
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0, 0, 0, 0.6);
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        z-index: 10000;
                        animation: fadeIn 0.3s ease-in-out;
                    ">
                        <div style="
                            background: white;
                            border-radius: 15px;
                            padding: 0;
                            max-width: 500px;
                            width: 90%;
                            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                            animation: slideIn 0.3s ease-out;
                            max-height: 90vh;
                            overflow-y: auto;
                        ">
                            <!-- Header -->
                            <div style="
                                background: ${isAwaited ? '#CCCCCC' : colors[winner_party]};
                                color: white;
                                padding: 25px;
                                border-radius: 15px 15px 0 0;
                                position: relative;
                            ">
                                <button onclick="document.getElementById('constituency-modal').remove()" style="
                                    position: absolute;
                                    top: 15px;
                                    right: 15px;
                                    background: rgba(255, 255, 255, 0.2);
                                    border: none;
                                    color: white;
                                    font-size: 24px;
                                    width: 35px;
                                    height: 35px;
                                    border-radius: 50%;
                                    cursor: pointer;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    transition: background 0.2s;
                                " onmouseover="this.style.background='rgba(255,255,255,0.3)'" 
                                   onmouseout="this.style.background='rgba(255,255,255,0.2)'">×</button>
                                <h2 style="margin: 0; font-size: 24px;">${constituency}</h2>
                                <p style="margin: 5px 0 0 0; opacity: 0.9;">District: ${district} | AC_NO: ${ac_no} | IDX: ${idx}</p>
                            </div>
                            
                            <!-- Content -->
                            <div style="padding: 25px;">
                                <!-- Year toggle -->
                                <div style="display:flex;margin-bottom:16px;border-radius:8px;overflow:hidden;border:1.5px solid #e0e0e0;box-shadow:0 2px 6px rgba(0,0,0,0.07);">
                                    <button id="btn-prev-${ac_no}"
                                        onclick="window._loadPrevResults(${ac_no});this.style.cssText='flex:1;padding:9px 0;font-size:13px;font-weight:700;background:#6c757d;color:white;border:none;cursor:pointer;';document.getElementById('btn-cur-'+${ac_no}).style.cssText='flex:1;padding:9px 0;font-size:13px;font-weight:600;background:white;color:#666;border:none;cursor:pointer;border-left:1.5px solid #e0e0e0;';"
                                        style="flex:1;padding:9px 0;font-size:13px;font-weight:600;background:white;color:#666;border:none;cursor:pointer;">
                                        __PREV_YEAR__ Results
                                    </button>
                                    <button id="btn-cur-${ac_no}"
                                        onclick="window._restoreCurResults(${ac_no});this.style.cssText='flex:1;padding:9px 0;font-size:13px;font-weight:700;background:#1471C7;color:white;border:none;cursor:pointer;border-left:1.5px solid #e0e0e0;';document.getElementById('btn-prev-'+${ac_no}).style.cssText='flex:1;padding:9px 0;font-size:13px;font-weight:600;background:white;color:#666;border:none;cursor:pointer;';"
                                        style="flex:1;padding:9px 0;font-size:13px;font-weight:700;background:#1471C7;color:white;border:none;cursor:pointer;border-left:1.5px solid #e0e0e0;">
                                        __CUR_YEAR__ Results
                                    </button>
                                </div>
                                <div id="results-box-${ac_no}">
                                ${isAwaited ? `
                                    <!-- Awaiting Results Message -->
                                    <div style="
                                        text-align: center;
                                        padding: 30px 20px;
                                        background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
                                        border-radius: 10px;
                                        margin: 20px 0;
                                    ">
                                        <div style="
                                            font-size: 48px;
                                            margin-bottom: 15px;
                                        ">⏳</div>
                                        <h3 style="
                                            color: #666;
                                            font-size: 20px;
                                            margin: 0 0 10px 0;
                                            font-weight: 600;
                                        ">Awaiting Results</h3>
                                        <p style="
                                            color: #888;
                                            font-size: 14px;
                                            margin: 0 0 20px 0;
                                        ">Counting has not started for this constituency yet</p>
                                        
                                        <!-- Random contesting parties preview -->
                                        <div style="
                                            margin-top: 20px;
                                            padding: 15px;
                                            background: white;
                                            border-radius: 8px;
                                        ">
                                            <p style="
                                                color: #999;
                                                font-size: 12px;
                                                margin: 0 0 12px 0;
                                                text-transform: uppercase;
                                                letter-spacing: 1px;
                                            ">Expected Contesting Parties</p>
                                            <div style="
                                                display: flex;
                                                justify-content: center;
                                                gap: 15px;
                                                flex-wrap: wrap;
                                            ">
                                                __TOP_PARTIES__
                                            </div>
                                        </div>
                                    </div>
                                ` : `
                                    <!-- Vote Counting Progress -->
                                    <div style="margin-bottom: 20px;">
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                            <span style="color: #666; font-size: 14px; font-weight: 600;">Votes Counted</span>
                                            <span style="color: #28a745; font-size: 16px; font-weight: bold;">${votes_counted}%</span>
                                        </div>
                                        <div style="
                                            width: 100%;
                                            height: 8px;
                                            background: #e0e0e0;
                                            border-radius: 10px;
                                            overflow: hidden;
                                        ">
                                            <div style="
                                                width: ${votes_counted}%;
                                                height: 100%;
                                                background: linear-gradient(90deg, #28a745, #20c997);
                                                border-radius: 10px;
                                                transition: width 0.3s ease;
                                            "></div>
                                        </div>
                                    </div>
                                    
                                    <!-- 1st Place -->
                                <div style="
                                    margin-bottom: 12px;
                                    padding: 15px;
                                    background: linear-gradient(to right, ${colors[winner_party]}15, white);
                                    border-radius: 10px;
                                    border-left: 5px solid ${colors[winner_party]};
                                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                ">
                                    <div>
                                        <div style="font-size: 16px; font-weight: bold; color: ${colors[winner_party]}; margin-bottom: 4px;">${winner_party}</div>
                                        <div style="color: #666; font-size: 14px;">${winner_candidate}</div>
                                    </div>
                                    <div style="text-align: right;">
                                        <div style="
                                            background: ${colors[winner_party]};
                                            color: white;
                                            padding: 4px 10px;
                                            border-radius: 5px;
                                            font-size: 11px;
                                            font-weight: bold;
                                            margin-bottom: 6px;
                                            display: inline-block;
                                        ">AHEAD BY ${(winner_votes - second_votes).toLocaleString()}</div>
                                        <div style="font-size: 20px; font-weight: bold; color: #333;">${winner_votes.toLocaleString()}</div>
                                        <div style="font-size: 16px; font-weight: bold; color: ${colors[winner_party]};">${winner_percent}%</div>
                                    </div>
                                </div>
                                
                                <!-- 2nd Place -->
                                <div style="
                                    margin-bottom: 12px;
                                    padding: 15px;
                                    background: linear-gradient(to right, ${colors[second_party]}10, white);
                                    border-radius: 10px;
                                    border-left: 5px solid ${colors[second_party]};
                                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                ">
                                    <div>
                                        <div style="font-size: 16px; font-weight: bold; color: ${colors[second_party]}; margin-bottom: 4px;">${second_party}</div>
                                        <div style="color: #666; font-size: 14px;">${second_candidate}</div>
                                    </div>
                                    <div style="text-align: right;">
                                        <div style="font-size: 20px; font-weight: bold; color: #333;">${second_votes.toLocaleString()}</div>
                                        <div style="font-size: 16px; font-weight: bold; color: ${colors[second_party]};">${second_percent}%</div>
                                    </div>
                                </div>
                                
                                <!-- 3rd Place -->
                                <div style="
                                    margin-bottom: 12px;
                                    padding: 15px;
                                    background: linear-gradient(to right, ${colors[third_party]}10, white);
                                    border-radius: 10px;
                                    border-left: 5px solid ${colors[third_party]};
                                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                ">
                                    <div>
                                        <div style="font-size: 16px; font-weight: bold; color: ${colors[third_party]}; margin-bottom: 4px;">${third_party}</div>
                                        <div style="color: #666; font-size: 14px;">${third_candidate}</div>
                                    </div>
                                    <div style="text-align: right;">
                                        <div style="font-size: 20px; font-weight: bold; color: #333;">${third_votes.toLocaleString()}</div>
                                        <div style="font-size: 16px; font-weight: bold; color: ${colors[third_party]};">${third_percent}%</div>
                                    </div>
                                </div>
                                `}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <style>
                        @keyframes fadeIn {
                            from { opacity: 0; }
                            to { opacity: 1; }
                        }
                        @keyframes slideIn {
                            from { transform: translateY(-50px); opacity: 0; }
                            to { transform: translateY(0); opacity: 1; }
                        }
                    </style>
                `;
                
                // Add modal to document
                document.body.insertAdjacentHTML('beforeend', modalHTML);
                
                // Save current results HTML so toggle can restore it
                window._savedResults = window._savedResults || {};
                const _rb = document.getElementById('results-box-' + ac_no);
                if (_rb) window._savedResults[ac_no] = _rb.innerHTML;
                
                // Function to restore filter when modal closes
                function restoreFilter() {
                    if (window.currentFilteredIndices && window.currentFilteredIndices.length > 0) {
                        source.selected.indices = window.currentFilteredIndices;
                    }
                }
                
                // Close on background click
                document.getElementById('constituency-modal').addEventListener('click', function(e) {
                    if (e.target === this) {
                        this.remove();
                        restoreFilter();
                    }
                });
                
                // Also restore filter when close button is clicked
                const closeButton = document.querySelector('#constituency-modal button');
                if (closeButton) {
                    closeButton.addEventListener('click', restoreFilter);
                }
            }
        """.replace('__PARTY_COLORS__', _colors_js).replace('__TOP_PARTIES__', _top_parties_js).replace('__CUR_YEAR__', str(sc['year'])).replace('__PREV_YEAR__', str(sc.get('prev_year', 'Previous'))))
        
        geosource.selected.js_on_change('indices', callback)
        
        # Calculate summary (seat count) and vote percentages for individual parties
        party_counts = state_gdf['winning_party'].value_counts().to_dict()
        individual_summary = {party: party_counts.get(party, 0) for party in individual_parties}
        
        # Aggregate to alliance level for display
        # alliance_list is already defined dynamically from state config above
        summary = {}
        for alliance in alliance_list:
            alliance_seats = 0
            for party, alliance_name in party_to_alliance.items():
                if alliance_name == alliance:
                    alliance_seats += individual_summary.get(party, 0)
            summary[alliance] = alliance_seats
        
        # Calculate total votes per party across all constituencies (ALL votes, not just winners)
        party_vote_totals = {party: 0 for party in individual_parties}
        grand_total_votes = 0
        
        for constituency_votes in all_party_votes:
            for party, votes in constituency_votes.items():
                if party in party_vote_totals:  # Only count if party is in our list
                    party_vote_totals[party] += votes
                    grand_total_votes += votes
        
        # Aggregate votes to alliance level
        alliance_vote_totals = {}
        for alliance in alliance_list:
            alliance_votes = 0
            for party, alliance_name in party_to_alliance.items():
                if alliance_name == alliance:
                    alliance_votes += party_vote_totals.get(party, 0)
            alliance_vote_totals[alliance] = alliance_votes
        
        # Calculate vote share percentages for alliances
        party_vote_shares = {alliance: (alliance_vote_totals[alliance] / grand_total_votes * 100) if grand_total_votes > 0 else 0 
                            for alliance in alliance_list}
        
        # Calculate district-wise seat distribution aggregated by alliance
        district_stats = {}
        for district in state_gdf['DIST_NAME'].unique():
            district_data = state_gdf[state_gdf['DIST_NAME'] == district]
            district_party_counts = district_data['winning_party'].value_counts().to_dict()
            # Aggregate to alliance level
            district_alliance_counts = {}
            for alliance in alliance_list:
                alliance_seats = 0
                for party, alliance_name in party_to_alliance.items():
                    if alliance_name == alliance:
                        alliance_seats += district_party_counts.get(party, 0)
                district_alliance_counts[alliance] = alliance_seats
            district_stats[district] = district_alliance_counts
        
        # Compute district-wise party vote totals (for voteshare filter)
        district_vote_totals = {}
        district_party_seats_map = {}
        for district in state_gdf['DIST_NAME'].unique():
            dist_rows = state_gdf[state_gdf['DIST_NAME'] == district]
            dv = {}
            for _, r in dist_rows.iterrows():
                for pcol, vcol in [('win_party', 'win_votes'), ('sec_party', 'sec_votes'), ('thi_party', 'thi_votes')]:
                    party_name = r.get(pcol)
                    if pd.notna(party_name) and party_name not in ('AWAITED', '', None):
                        dv[party_name] = dv.get(party_name, 0) + float(r.get(vcol, 0) or 0)
            district_vote_totals[str(district)] = dv
            district_party_seats_map[str(district)] = dist_rows['winning_party'].value_counts().to_dict()

        # Calculate parliament constituency-wise seat distribution aggregated by alliance
        pc_stats = {}
        for pc in state_gdf['PC_NAME'].unique():
            pc_data = state_gdf[state_gdf['PC_NAME'] == pc]
            pc_party_counts = pc_data['winning_party'].value_counts().to_dict()
            # Aggregate to alliance level
            pc_alliance_counts = {}
            for alliance in alliance_list:
                alliance_seats = 0
                for party, alliance_name in party_to_alliance.items():
                    if alliance_name == alliance:
                        alliance_seats += pc_party_counts.get(party, 0)
                pc_alliance_counts[alliance] = alliance_seats
            pc_stats[pc] = pc_alliance_counts
        
        # Create dynamic info panel (replaces legend)
        # Sort alliances by seat count (highest first)
        sorted_parties = sorted(summary.items(), key=lambda x: x[1], reverse=True)
        
        party_boxes = ""
        for party, seats in sorted_parties:
            party_boxes += f"""
                <div onclick="filterByAlliance('{party}');" style="background: linear-gradient(135deg, {alliance_colors_map[party]} 0%, {alliance_colors_map[party]}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                    <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">{party}</div>
                    <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">{seats}</div>
                    <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                </div>
            """
        
        info_html = f"""
        <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
            <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                <span id="info-title">📊 OVERALL RESULTS (ALLIANCE)</span>
            </h3>
            <div id="info-content" style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                {party_boxes}
            </div>
            <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">{sum(summary.values())}</span> <span style="color: #6c757d;">seats</span>
            </div>
        </div>
        """
        
        info_div = Div(text=info_html, width=350)
        
        # Style
        p.title.text_font_size = "16pt"
        p.title.align = "center"
        p.xgrid.visible = False  # Hide gridlines
        p.ygrid.visible = False  # Hide gridlines
        p.xaxis.visible = False  # Hide x-axis
        p.yaxis.visible = False  # Hide y-axis
        p.outline_line_color = None  # Remove border
        
        # Prepare district stats, PC stats, and summary for JavaScript
        district_stats_json = json.dumps(district_stats)
        pc_stats_json = json.dumps(pc_stats)
        summary_json = json.dumps(summary)
        individual_summary_json = json.dumps(individual_summary)
        party_colors_json = json.dumps(individual_party_colors)
        alliance_colors_json = json.dumps(alliance_colors_map)
        
        # Create toggle button for color mode
        from bokeh.models import Button
        color_mode_button = Button(
            label="🔄 Switch to Party View",
            button_type="success",
            width=320,
            height=45
        )
        
        # JavaScript callback for toggling color mode
        color_mode_callback = CustomJS(args=dict(
            source=geosource,
            button=color_mode_button,
            info_div=info_div
        ), code=f"""
            const data = source.data;
            const alliance_summary = {summary_json};
            const party_summary = {individual_summary_json};
            const alliance_colors = {alliance_colors_json};
            const party_colors = {party_colors_json};
            const pc_stats = {pc_stats_json};
            const district_stats = {district_stats_json};
            const party_to_alliance = {json.dumps(party_to_alliance)};
            
            // Check if there's an active filter
            const hasFilter = window.currentFilteredIndices && window.currentFilteredIndices.length > 0;
            
            // Toggle between party and alliance colors
            if (button.label === "🔄 Switch to Party View") {{
                // Switch to party colors
                data['color'] = data['party_color'];
                button.label = "🔄 Switch to Alliance View";
                
                // Determine what to show based on active filters
                let party_boxes = '';
                let total = 0;
                let title = '📊 OVERALL RESULTS (PARTY)';
                let summary_to_use = party_summary;
                
                // Check for PC filter
                if (window.currentPCFilter && window.currentPCFilter !== "All Parliament Seats") {{
                    title = `📊 ${{window.currentPCFilter}} (PARTY)`;
                    const pc_alliance_stats = pc_stats[window.currentPCFilter];
                    summary_to_use = {{}};
                    
                    // Convert alliance stats to party stats by checking winning parties in filtered indices
                    const winning_parties = data['winning_party'];
                    for (let idx of window.currentFilteredIndices) {{
                        const party = winning_parties[idx];
                        summary_to_use[party] = (summary_to_use[party] || 0) + 1;
                    }}
                }} else if (window.currentDistrictFilter && window.currentDistrictFilter !== "All Districts") {{
                    title = `📊 ${{window.currentDistrictFilter}} (PARTY)`;
                    summary_to_use = {{}};
                    
                    // Convert alliance stats to party stats by checking winning parties in filtered indices
                    const winning_parties = data['winning_party'];
                    for (let idx of window.currentFilteredIndices) {{
                        const party = winning_parties[idx];
                        summary_to_use[party] = (summary_to_use[party] || 0) + 1;
                    }}
                }} else if (window.currentPartyFilter && window.currentPartyFilter !== "All Parties") {{
                    const filterVal = window.currentPartyFilter;
                    // If the filter value is an alliance name (has no party color), break down by party
                    if (alliance_colors[filterVal] && !party_colors[filterVal]) {{
                        title = `📊 ${{filterVal}} (PARTY)`;
                        summary_to_use = {{}};
                        const winning_parties = data['winning_party'];
                        for (let idx of window.currentFilteredIndices) {{
                            const party = winning_parties[idx];
                            summary_to_use[party] = (summary_to_use[party] || 0) + 1;
                        }}
                    }} else {{
                        title = `📊 ${{filterVal}}`;
                        summary_to_use = {{}};
                        summary_to_use[filterVal] = window.currentFilteredIndices.length;
                    }}
                }} else if (window.currentLeadMarginFilter && window.currentLeadMarginFilter !== "All Margins") {{
                    title = `📊 ${{window.currentLeadMarginFilter}} (PARTY)`;
                    summary_to_use = {{}};
                    
                    // Calculate party counts from filtered indices
                    const winning_parties = data['winning_party'];
                    for (let idx of window.currentFilteredIndices) {{
                        const party = winning_parties[idx];
                        summary_to_use[party] = (summary_to_use[party] || 0) + 1;
                    }}
                }}
                
                const sorted_parties = Object.entries(summary_to_use).sort((a, b) => b[1] - a[1]);
                for (const [party, seats] of sorted_parties) {{
                    total += seats || 0;
                    party_boxes += `
                        <div onclick="filterByParty('${{party}}');" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                            <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{party}}</div>
                            <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                            <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                        ${{title}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                        ${{party_boxes}}
                    </div>
                    <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                        <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{total}}</span> <span style="color: #6c757d;">seats</span>
                    </div>
                </div>
                `;
            }} else {{
                // Switch back to alliance colors
                data['color'] = data['alliance_color'];
                button.label = "🔄 Switch to Party View";
                
                // Determine what to show based on active filters
                let alliance_boxes = '';
                let total = 0;
                let title = '📊 OVERALL RESULTS (ALLIANCE)';
                let summary_to_use = alliance_summary;
                
                // Check for PC filter
                if (window.currentPCFilter && window.currentPCFilter !== "All Parliament Seats") {{
                    title = `📊 ${{window.currentPCFilter}} (ALLIANCE)`;
                    summary_to_use = pc_stats[window.currentPCFilter];
                }} else if (window.currentDistrictFilter && window.currentDistrictFilter !== "All Districts") {{
                    title = `📊 ${{window.currentDistrictFilter}} (ALLIANCE)`;
                    summary_to_use = district_stats[window.currentDistrictFilter];
                }} else if (window.currentPartyFilter && window.currentPartyFilter !== "All Parties") {{
                    // For party filter, convert to alliance
                    const filterVal = window.currentPartyFilter;
                    // If already an alliance name, use it directly; otherwise look up
                    const alliance = alliance_colors[filterVal] ? filterVal : (party_to_alliance[filterVal] || filterVal);
                    title = `📊 ${{filterVal}} (${{alliance}})`;
                    summary_to_use = {{}};
                    summary_to_use[alliance] = window.currentFilteredIndices.length;
                }} else if (window.currentLeadMarginFilter && window.currentLeadMarginFilter !== "All Margins") {{
                    title = `📊 ${{window.currentLeadMarginFilter}} (ALLIANCE)`;
                    summary_to_use = {{}};
                    
                    // Calculate alliance counts from filtered indices
                    const winning_parties = data['winning_party'];
                    for (let idx of window.currentFilteredIndices) {{
                        const party = winning_parties[idx];
                        const alliance = party_to_alliance[party];
                        summary_to_use[alliance] = (summary_to_use[alliance] || 0) + 1;
                    }}
                }}
                
                const sorted_alliances = Object.entries(summary_to_use).sort((a, b) => b[1] - a[1]);
                for (const [alliance, seats] of sorted_alliances) {{
                    total += seats || 0;
                    alliance_boxes += `
                        <div onclick="filterByAlliance('${{alliance}}');" style="background: linear-gradient(135deg, ${{alliance_colors[alliance]}} 0%, ${{alliance_colors[alliance]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                            <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{alliance}}</div>
                            <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                            <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                        ${{title}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                        ${{alliance_boxes}}
                    </div>
                    <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                        <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{total}}</span> <span style="color: #6c757d;">seats</span>
                    </div>
                </div>
                `;
            }}
            
            source.change.emit();
        """)
        
        color_mode_button.js_on_click(color_mode_callback)
        
        # Create cascading filter system
        filter_type_select = Select(
            title="🎯 Select Filter Type:",
            value="None",
            options=["None", "Parliament Seat", "District", "Party", "Lead Margin"],
            width=320,
            height=50,
            name="filter_type_select"
        )
        
        filter_value_select = Select(
            title="📌 Select Value:",
            value="",
            options=[""],
            width=320,
            height=50,
            name="filter_value_select"
        )
        
        # Prepare data for cascading filter
        pc_names = sorted(state_gdf['PC_NAME'].unique().tolist())
        district_names = sorted(state_gdf['DIST_NAME'].unique().tolist())
        individual_parties_for_filter = list(sc['alliances'].keys()) + [p for p in individual_parties if p not in ('AWAITED',)]
        lead_margin_options = ["Less than 1,000", "Less than 5,000", "Greater than 5,000", "Greater than 10,000", "Greater than 25,000"]
        
        # Callback to populate filter_value_select based on filter_type_select
        filter_type_callback = CustomJS(args=dict(
            filter_type=filter_type_select,
            filter_value=filter_value_select,
            source=geosource,
            info_div=info_div
        ), code=f"""
            const filterType = filter_type.value;
            const pcNames = {json.dumps(pc_names)};
            const districtNames = {json.dumps(district_names)};
            const parties = {json.dumps(individual_parties_for_filter)};
            const leadMargins = {json.dumps(lead_margin_options)};
            
            if (filterType === "None") {{
                filter_value.options = [""];
                filter_value.value = "";
                
                // Clear selection immediately
                source.selected.indices = [];
                window.currentFilteredIndices = [];
                window.currentPCFilter = null;
                window.currentDistrictFilter = null;
                window.currentPartyFilter = null;
                window.currentLeadMarginFilter = null;
                
                // Show overall results
                const overall_summary = {summary_json};
                const alliance_colors = {alliance_colors_json};
                const sorted_overall = Object.entries(overall_summary).sort((a, b) => b[1] - a[1]);
                let overall_boxes = '';
                let overall_total = 0;
                for (const [alliance, seats] of sorted_overall) {{
                    overall_total += seats || 0;
                    overall_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Overall Results
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 6px; justify-items: start; max-height: 360px; overflow-y: auto;">
                        ${{overall_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{overall_total}} seats
                    </div>
                </div>
                `;
                source.change.emit();
                
            }} else if (filterType === "Parliament Seat") {{
                filter_value.options = pcNames;
                filter_value.value = pcNames[0] || "";
                // Trigger filter application by manually calling the filter logic
                setTimeout(() => {{ filter_value.change.emit(); }}, 10);
            }} else if (filterType === "District") {{
                filter_value.options = districtNames;
                filter_value.value = districtNames[0] || "";
                setTimeout(() => {{ filter_value.change.emit(); }}, 10);
            }} else if (filterType === "Party") {{
                filter_value.options = parties;
                filter_value.value = parties[0] || "";
                setTimeout(() => {{ filter_value.change.emit(); }}, 10);
            }} else if (filterType === "Lead Margin") {{
                filter_value.options = leadMargins;
                filter_value.value = leadMargins[0] || "";
                setTimeout(() => {{ filter_value.change.emit(); }}, 10);
            }}
        """)
        
        filter_type_select.js_on_change('value', filter_type_callback)
        
        # Main filter callback that applies the selected filter
        filter_apply_callback = CustomJS(args=dict(
            source=geosource,
            filter_type=filter_type_select,
            filter_value=filter_value_select,
            info_div=info_div
        ), code=f"""
            const filterType = filter_type.value;
            const filterValue = filter_value.value;
            const data = source.data;
            
            const pc_stats = {pc_stats_json};
            const district_stats = {district_stats_json};
            const overall_summary = {summary_json};
            const alliance_colors = {alliance_colors_json};
            const party_to_alliance = {json.dumps(party_to_alliance)};
            const party_colors_map = {party_colors_json};
            
            // Clear previous filter state
            window.currentPCFilter = null;
            window.currentDistrictFilter = null;
            window.currentPartyFilter = null;
            window.currentLeadMarginFilter = null;
            window.currentFilteredIndices = [];
            
            if (filterType === "None" || filterValue === "") {{
                // Show all constituencies
                source.selected.indices = [];
                window.currentFilteredIndices = [];
                
                // Show overall results in info panel
                const sorted_overall = Object.entries(overall_summary).sort((a, b) => b[1] - a[1]);
                let overall_boxes = '';
                let overall_total = 0;
                for (const [alliance, seats] of sorted_overall) {{
                    overall_total += seats || 0;
                    overall_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Overall Results
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 6px; justify-items: start; max-height: 360px; overflow-y: auto;">
                        ${{overall_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{overall_total}} seats
                    </div>
                </div>
                `;
                
            }} else if (filterType === "Parliament Seat") {{
                // Filter by Parliament Seat
                window.currentPCFilter = filterValue;
                const pc_names = data['PC_NAME'];
                const selectedIndices = [];
                for (let i = 0; i < pc_names.length; i++) {{
                    if (pc_names[i] === filterValue) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Update info panel with PC stats
                const stats = pc_stats[filterValue];
                const sorted_stats = Object.entries(stats).sort((a, b) => b[1] - a[1]);
                let pc_boxes = '';
                let pc_total = 0;
                for (const [alliance, seats] of sorted_stats) {{
                    pc_total += seats || 0;
                    pc_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        ${{filterValue}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 6px; justify-items: start; max-height: 360px; overflow-y: auto;">
                        ${{pc_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{pc_total}} seats
                    </div>
                </div>
                `;
                
            }} else if (filterType === "District") {{
                // Filter by District
                window.currentDistrictFilter = filterValue;
                const districts = data['DIST_NAME'];
                const selectedIndices = [];
                for (let i = 0; i < districts.length; i++) {{
                    if (districts[i] === filterValue) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Update info panel with district stats
                const stats = district_stats[filterValue];
                const sorted_stats = Object.entries(stats).sort((a, b) => b[1] - a[1]);
                let district_boxes = '';
                let district_total = 0;
                for (const [alliance, seats] of sorted_stats) {{
                    district_total += seats || 0;
                    district_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        ${{filterValue}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 6px; justify-items: start; max-height: 360px; overflow-y: auto;">
                        ${{district_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{district_total}} seats
                    </div>
                </div>
                `;
                
            }} else if (filterType === "Party") {{
                // Filter by Party or Alliance (alliance name matches all parties belonging to it)
                window.currentPartyFilter = filterValue;
                const winning_parties = data['winning_party'];
                const selectedIndices = [];
                for (let i = 0; i < winning_parties.length; i++) {{
                    const p = winning_parties[i];
                    if (p === filterValue || party_to_alliance[p] === filterValue) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Show party-specific info
                const alliance = party_to_alliance[filterValue] || filterValue;
                const party_color = party_colors_map[filterValue] || alliance_colors[alliance];
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        ${{filterValue}} Seats
                    </h3>
                    <div style="display: flex; justify-content: center; align-items: center; margin: 10px 0;">
                        <div style="background: ${{party_color}}; border-radius: 4px; padding: 15px; text-align: center; width: 80px; height: 80px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 10px; font-weight: 600; margin-bottom: 5px;">${{filterValue}}</div>
                            <div style="color: white; font-size: 24px; font-weight: bold; line-height: 1;">${{selectedIndices.length}}</div>
                        </div>
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center;">
                        Showing constituencies won by ${{filterValue}}
                    </div>
                </div>
                `;
                
            }} else if (filterType === "Lead Margin") {{
                // Filter by Lead Margin
                window.currentLeadMarginFilter = filterValue;
                const lead_margins = data['lead_margin'];
                const selectedIndices = [];
                
                for (let i = 0; i < lead_margins.length; i++) {{
                    const margin = lead_margins[i];
                    let matches = false;
                    
                    if (filterValue === "Less than 1,000" && margin < 1000) {{
                        matches = true;
                    }} else if (filterValue === "Less than 5,000" && margin < 5000) {{
                        matches = true;
                    }} else if (filterValue === "Greater than 5,000" && margin > 5000) {{
                        matches = true;
                    }} else if (filterValue === "Greater than 10,000" && margin > 10000) {{
                        matches = true;
                    }} else if (filterValue === "Greater than 25,000" && margin > 25000) {{
                        matches = true;
                    }}
                    
                    if (matches) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Calculate alliance breakdown for filtered seats
                const alliances_filtered = {{}};
                const winning_alliances = data['alliance'];
                for (let i of selectedIndices) {{
                    const alliance = winning_alliances[i];
                    alliances_filtered[alliance] = (alliances_filtered[alliance] || 0) + 1;
                }}
                
                // Show lead margin info with alliance breakdown
                const sorted_alliances = Object.entries(alliances_filtered).sort((a, b) => b[1] - a[1]);
                let alliance_boxes = '';
                for (const [alliance, seats] of sorted_alliances) {{
                    alliance_boxes += `
                        <div onclick="filterByAlliance('${{alliance}}');" style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center; cursor: pointer;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Lead Margin: ${{filterValue}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 6px; justify-items: start; max-height: 360px; overflow-y: auto;">
                        ${{alliance_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{selectedIndices.length}} seats
                    </div>
                </div>
                `;
            }}
            
            source.change.emit();
        """)
        
        filter_value_select.js_on_change('value', filter_apply_callback)
        
        # Create reset filters button
        reset_button = Button(
            label="🔄 Reset Filters",
            button_type="warning",
            width=320,
            height=40
        )
        
        reset_callback = CustomJS(args=dict(
            source=geosource,
            filter_type=filter_type_select,
            filter_value=filter_value_select,
            info_div=info_div,
            color_button=color_mode_button
        ), code=f"""
            // Reset filter dropdowns
            filter_type.value = "None";
            filter_value.options = [""];
            filter_value.value = "";
            
            // Clear selection
            source.selected.indices = [];
            
            // Clear global filter state
            window.currentPCFilter = null;
            window.currentDistrictFilter = null;
            window.currentPartyFilter = null;
            window.currentLeadMarginFilter = null;
            window.currentFilteredIndices = [];
            
            // Check current view mode from button label
            const isPartyView = color_button.label === "🔄 Switch to Alliance View";
            
            // Reset map colors based on current view mode
            const data = source.data;
            if (isPartyView) {{
                // Set to party colors
                data['color'] = data['party_color'];
            }} else {{
                // Set to alliance colors
                data['color'] = data['alliance_color'];
            }}
            
            // Show overall results based on current view mode
            if (isPartyView) {{
                // Party view
                const individual_summary = {individual_summary_json};
                const party_colors = {party_colors_json};
                const sorted_parties = Object.entries(individual_summary).sort((a, b) => b[1] - a[1]);
                let party_boxes = '';
                let party_total = 0;
                for (const [party, seats] of sorted_parties) {{
                    party_total += seats || 0;
                    party_boxes += `
                        <div onclick="filterByParty('${{party}}');" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                            <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{party}}</div>
                            <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                            <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                        Overall Results (PARTY)
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(auto-fill, minmax(70px, 1fr)); gap: 8px 2px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                        ${{party_boxes}}
                    </div>
                    <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                        <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{party_total}}</span> <span style="color: #6c757d;">seats</span>
                    </div>
                </div>
                `;
            }} else {{
                // Alliance view
                const overall_summary = {summary_json};
                const alliance_colors = {alliance_colors_json};
                const sorted_overall = Object.entries(overall_summary).sort((a, b) => b[1] - a[1]);
                let overall_boxes = '';
                let overall_total = 0;
                for (const [alliance, seats] of sorted_overall) {{
                    overall_total += seats || 0;
                    overall_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Overall Results
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 6px; justify-items: start; max-height: 360px; overflow-y: auto;">
                        ${{overall_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{overall_total}} seats
                    </div>
                </div>
                `;
            }}
            
            source.change.emit();
        """)
        
        reset_button.js_on_click(reset_callback)
        
        pc_select = Select(
            title="🏛️ Filter by Parliament Seat:",
            value="All Parliament Seats",
            options=["All Parliament Seats"] + pc_names,
            width=320,
            height=50
        )
        
        # JavaScript callback for parliament constituency filtering with info panel update
        pc_callback = CustomJS(args=dict(
            source=geosource, 
            select=pc_select, 
            info_div=info_div
        ), code=f"""
            const pc_name = select.value;
            const data = source.data;
            const pc_names = data['PC_NAME'];
            const pc_stats = {pc_stats_json};
            const overall_summary = {summary_json};
            
            // Store current filter state globally
            window.currentPCFilter = pc_name;
            window.currentFilteredIndices = [];
            
            if (pc_name === "All Parliament Seats") {{
                // Clear selection to show all
                source.selected.indices = [];
                window.currentFilteredIndices = [];
                
                // Update info panel to show overall results
                const alliance_colors = {alliance_colors_json};
                const sorted_overall = Object.entries(overall_summary).sort((a, b) => b[1] - a[1]);
                let overall_boxes = '';
                let overall_total = 0;
                for (const [alliance, seats] of sorted_overall) {{
                    overall_total += seats || 0;
                    overall_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Overall Results
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 4px 2px; justify-items: start;">
                        ${{overall_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{overall_total}} seats
                    </div>
                </div>
                `;
            }} else {{
                // Find all assembly constituencies in this parliament constituency
                const selectedIndices = [];
                for (let i = 0; i < pc_names.length; i++) {{
                    if (pc_names[i] === pc_name) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Update info panel with PC stats
                const stats = pc_stats[pc_name];
                const alliance_colors = {alliance_colors_json};
                const sorted_stats = Object.entries(stats).sort((a, b) => b[1] - a[1]);
                let pc_boxes = '';
                let pc_total = 0;
                for (const [alliance, seats] of sorted_stats) {{
                    pc_total += seats || 0;
                    pc_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        ${{pc_name}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 4px 2px; justify-items: start;">
                        ${{pc_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{pc_total}} seats
                    </div>
                </div>
                `;
            }}
        """)
        
        pc_select.js_on_change('value', pc_callback)
        
        # Create dropdown for district selection
        district_names = sorted(state_gdf['DIST_NAME'].unique().tolist())
        district_select = Select(
            title="📍 Filter by District:",
            value="All Districts",
            options=["All Districts"] + district_names,
            width=320,
            height=50
        )
        
        # JavaScript callback for district filtering with info panel update
        district_callback = CustomJS(args=dict(
            source=geosource, 
            select=district_select, 
            info_div=info_div
        ), code=f"""
            const district_name = select.value;
            const data = source.data;
            const districts = data['DIST_NAME'];
            const district_stats = {district_stats_json};
            const overall_summary = {summary_json};
            
            // Store current filter state globally
            window.currentDistrictFilter = district_name;
            window.currentFilteredIndices = [];
            
            // Store current filter state globally so click handlers can preserve it
            window.currentDistrictFilter = district_name;
            window.currentFilteredIndices = [];
            
            if (district_name === "All Districts") {{
                // Clear selection to show all
                source.selected.indices = [];
                window.currentFilteredIndices = [];
                
                // Update info panel to show overall results
                const alliance_colors = {alliance_colors_json};
                const sorted_overall = Object.entries(overall_summary).sort((a, b) => b[1] - a[1]);
                let overall_boxes = '';
                let overall_total = 0;
                for (const [alliance, seats] of sorted_overall) {{
                    overall_total += seats || 0;
                    overall_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Overall Results
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 4px 2px; justify-items: start;">
                        ${{overall_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{overall_total}} seats
                    </div>
                </div>
                `;
            }} else {{
                // Find all constituencies in this district
                const selectedIndices = [];
                for (let i = 0; i < districts.length; i++) {{
                    if (districts[i] === district_name) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;  // Store for restoration after click
                
                // Update info panel with district stats
                const stats = district_stats[district_name];
                const alliance_colors = {alliance_colors_json};
                const sorted_stats = Object.entries(stats).sort((a, b) => b[1] - a[1]);
                let district_boxes = '';
                let district_total = 0;
                for (const [alliance, seats] of sorted_stats) {{
                    district_total += seats || 0;
                    district_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        ${{district_name}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 4px 2px; justify-items: start;">
                        ${{district_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{district_total}} seats
                    </div>
                </div>
                `;
            }}
        """)
        
        district_select.js_on_change('value', district_callback)
        
        # Create dropdown for party filtering
        party_select = Select(
            title="🎯 Filter by Party:",
            value="All Parties",
            options=["All Parties"] + individual_parties,
            width=320,
            height=50
        )
        
        # JavaScript callback for party filtering
        party_callback = CustomJS(args=dict(
            source=geosource, 
            select=party_select, 
            info_div=info_div
        ), code=f"""
            const party_name = select.value;
            const data = source.data;
            const winning_parties = data['winning_party'];
            const overall_summary = {summary_json};
            const party_to_alliance = {json.dumps(party_to_alliance)};
            
            // Store current filter state globally
            window.currentPartyFilter = party_name;
            window.currentFilteredIndices = [];
            
            // Store current filter state globally
            window.currentPartyFilter = party_name;
            window.currentFilteredIndices = [];
            
            if (party_name === "All Parties") {{
                // Clear selection to show all
                source.selected.indices = [];
                window.currentFilteredIndices = [];
                
                // Update info panel to show overall results
                const alliance_colors = {alliance_colors_json};
                const sorted_overall = Object.entries(overall_summary).sort((a, b) => b[1] - a[1]);
                let overall_boxes = '';
                let overall_total = 0;
                for (const [alliance, seats] of sorted_overall) {{
                    overall_total += seats || 0;
                    overall_boxes += `
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{alliance}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seats || 0}}</div>
                        </div>
                    `;
                }}
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        Overall Results
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 4px 2px; justify-items: start;">
                        ${{overall_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{overall_total}} seats
                    </div>
                </div>
                `;
            }} else {{
                // Find all constituencies won by this party
                const selectedIndices = [];
                for (let i = 0; i < winning_parties.length; i++) {{
                    if (winning_parties[i] === party_name) {{
                        selectedIndices.push(i);
                    }}
                }}
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Update info panel with party-specific stats
                const party_colors = {party_colors_json};
                const party_color = party_colors[party_name];
                const seat_count = selectedIndices.length;
                
                info_div.text = `
                <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 300px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 12px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 5px;">
                        ${{party_name}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 4px 8px; justify-items: start;">
                        <div style="background: ${{party_color}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div style="color: white; font-size: 8px; font-weight: 600; margin-bottom: 3px;">${{party_name}}</div>
                            <div style="color: white; font-size: 18px; font-weight: bold; line-height: 1;">${{seat_count}}</div>
                        </div>
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{seat_count}} seats
                    </div>
                </div>
                `;
            }}
        """)
        
        party_select.js_on_change('value', party_callback)
        
        # Create lead margin filter
        lead_margin_select = Select(
            title="📊 Filter by Lead Margin:",
            value="All Margins",
            options=["All Margins", "Less than 1,000", "Less than 5,000", "Greater than 5,000", "Greater than 10,000", "Greater than 25,000"],
            width=320,
            height=50
        )
        
        # JavaScript callback for lead margin filter
        lead_margin_callback = CustomJS(args=dict(
            source=geosource,
            select=lead_margin_select,
            info_div=info_div,
            pc_select=pc_select,
            district_select=district_select,
            party_select=party_select
        ), code=f"""
            const margin_filter = select.value;
            const data = source.data;
            const lead_margins = data['lead_margin'];
            
            // Store current filter
            window.currentLeadMarginFilter = margin_filter;
            
            // Reset other filters
            window.currentPCFilter = null;
            window.currentDistrictFilter = null;
            window.currentPartyFilter = null;
            pc_select.value = "All Parliament Seats";
            district_select.value = "All Districts";
            party_select.value = "All Parties";
            
            const alliance_summary = {summary_json};
            const party_summary = {individual_summary_json};
            const alliance_colors = {alliance_colors_json};
            const party_colors = {party_colors_json};
            
            if (margin_filter === "All Margins") {{
                // Show all constituencies
                source.selected.indices = [];
                window.currentFilteredIndices = [];
                
                // Determine current view mode
                const isAllianceView = data['color'][0] === data['alliance_color'][0];
                
                if (isAllianceView) {{
                    const sorted_alliances = Object.entries(alliance_summary).sort((a, b) => b[1] - a[1]);
                    let alliance_boxes = '';
                    let total = 0;
                    for (const [alliance, seats] of sorted_alliances) {{
                        total += seats || 0;
                        alliance_boxes += `
                            <div style="background: linear-gradient(135deg, ${{alliance_colors[alliance]}} 0%, ${{alliance_colors[alliance]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                                <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{alliance}}</div>
                                <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                                <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                            </div>
                        `;
                    }}
                    
                    info_div.text = `
                    <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                            📊 OVERALL RESULTS (ALLIANCE)
                        </h3>
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                            ${{alliance_boxes}}
                        </div>
                        <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                            <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{total}}</span> <span style="color: #6c757d;">seats</span>
                        </div>
                    </div>
                    `;
                }} else {{
                    const sorted_parties = Object.entries(party_summary).sort((a, b) => b[1] - a[1]);
                    let party_boxes = '';
                    let total = 0;
                    for (const [party, seats] of sorted_parties) {{
                        total += seats || 0;
                        party_boxes += `
                            <div onclick="filterByParty('${{party}}');" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                                <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{party}}</div>
                                <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                                <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                            </div>
                        `;
                    }}
                    
                    info_div.text = `
                    <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                            📊 OVERALL RESULTS (PARTY)
                        </h3>
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                            ${{party_boxes}}
                        </div>
                        <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                            <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{total}}</span> <span style="color: #6c757d;">seats</span>
                        </div>
                    </div>
                    `;
                }}
            }} else {{
                // Filter based on lead margin
                let selectedIndices = [];
                for (let i = 0; i < lead_margins.length; i++) {{
                    const margin = lead_margins[i];
                    let include = false;
                    
                    if (margin_filter === "Less than 1,000") {{
                        include = margin < 1000;
                    }} else if (margin_filter === "Less than 5,000") {{
                        include = margin < 5000;
                    }} else if (margin_filter === "Greater than 5,000") {{
                        include = margin > 5000;
                    }} else if (margin_filter === "Greater than 10,000") {{
                        include = margin > 10000;
                    }} else if (margin_filter === "Greater than 25,000") {{
                        include = margin > 25000;
                    }}
                    
                    if (include) {{
                        selectedIndices.push(i);
                    }}
                }}
                
                source.selected.indices = selectedIndices;
                window.currentFilteredIndices = selectedIndices;
                
                // Calculate party/alliance counts for filtered constituencies
                const winning_parties = data['winning_party'];
                const party_to_alliance = {json.dumps(party_to_alliance)};
                
                const filtered_alliance_counts = {{}};
                const filtered_party_counts = {{}};
                
                for (const idx of selectedIndices) {{
                    const party = winning_parties[idx];
                    const alliance = party_to_alliance[party];
                    
                    filtered_party_counts[party] = (filtered_party_counts[party] || 0) + 1;
                    filtered_alliance_counts[alliance] = (filtered_alliance_counts[alliance] || 0) + 1;
                }}
                
                // Determine current view mode
                const isAllianceView = data['color'][0] === data['alliance_color'][0];
                
                if (isAllianceView) {{
                    const sorted_alliances = Object.entries(filtered_alliance_counts).sort((a, b) => b[1] - a[1]);
                    let alliance_boxes = '';
                    let total = 0;
                    for (const [alliance, seats] of sorted_alliances) {{
                        total += seats || 0;
                        alliance_boxes += `
                            <div style="background: linear-gradient(135deg, ${{alliance_colors[alliance]}} 0%, ${{alliance_colors[alliance]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                                <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{alliance}}</div>
                                <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                                <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                            </div>
                        `;
                    }}
                    
                    info_div.text = `
                    <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                            📊 ${{margin_filter}} (ALLIANCE)
                        </h3>
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                            ${{alliance_boxes}}
                        </div>
                        <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                            <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{total}}</span> <span style="color: #6c757d;">seats</span>
                        </div>
                    </div>
                    `;
                }} else {{
                    const sorted_parties = Object.entries(filtered_party_counts).sort((a, b) => b[1] - a[1]);
                    let party_boxes = '';
                    let total = 0;
                    for (const [party, seats] of sorted_parties) {{
                        total += seats || 0;
                        party_boxes += `
                            <div onclick="filterByParty('${{party}}');" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
                                <div style="color: white; font-size: 9px; font-weight: 700; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; text-shadow: 0 1px 2px rgba(0,0,0,0.2);">${{party}}</div>
                                <div style="color: white; font-size: 22px; font-weight: 900; line-height: 1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">${{seats || 0}}</div>
                                <div style="color: rgba(255,255,255,0.9); font-size: 7px; margin-top: 2px; font-weight: 500;">SEATS</div>
                            </div>
                        `;
                    }}
                    
                    info_div.text = `
                    <div style="background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); padding: 15px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); width: 320px; border: 1px solid rgba(102, 126, 234, 0.1);">
                        <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #2c3e50; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; padding-bottom: 8px; border-bottom: 3px solid #667eea; font-weight: 800; letter-spacing: 0.5px;">
                            📊 ${{margin_filter}} (PARTY)
                        </h3>
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 6px; justify-items: start; padding: 8px 0; max-height: 360px; overflow-y: auto;">
                            ${{party_boxes}}
                        </div>
                        <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                            <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">${{total}}</span> <span style="color: #6c757d;">seats</span>
                        </div>
                    </div>
                    `;
                }}
            }}
            
            source.change.emit();
        """)
        
        lead_margin_select.js_on_change('value', lead_margin_callback)
        
        # Create dropdown for constituency selection
        constituency_names = sorted(state_gdf['AC_NAME'].unique().tolist())
        constituency_select = Select(
            title="🔍 Select Constituency:",
            value="",
            options=[""] + constituency_names,
            width=320,
            height=50
        )
        
        # JavaScript callback for dropdown selection
        select_callback = CustomJS(args=dict(source=geosource, select=constituency_select), code="""
            const constituency_name = select.value;
            if (constituency_name) {
                const data = source.data;
                const ac_names = data['AC_NAME'];
                
                // Find the index of the selected constituency
                for (let i = 0; i < ac_names.length; i++) {
                    if (ac_names[i] === constituency_name) {
                        // Select this constituency
                        source.selected.indices = [i];
                        break;
                    }
                }
            }
        """)
        
        constituency_select.js_on_change('value', select_callback)
        
        # Combine plot, info panel, and dropdowns in layout
        selectors = column(info_div, color_mode_button, reset_button, filter_type_select, filter_value_select, constituency_select)
        layout = row(selectors, p)
        
        # Build per-seat data list for trends/swing views
        seat_data = []
        for _, row_d in state_gdf.iterrows():
            ac_no = int(row_d.get('AC_NO', 0))
            wp = str(row_d.get('winning_party', row_d.get('win_party', 'AWAITED')))
            vp = float(row_d.get('votes_pct', 0) or 0)
            wv = int(row_d.get('win_votes', 0) or 0)
            sv = int(row_d.get('sec_votes', 0) or 0)
            seat_data.append({
                'ac_no': ac_no,
                'ac_name': str(row_d.get('AC_NAME', f'AC {ac_no}')),
                'win_party': wp,
                'votes_pct': vp,
                'margin': wv - sv,
            })

        return layout, summary, party_vote_shares, party_vote_totals, individual_summary, district_vote_totals, district_party_seats_map, seat_data
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"Error creating election map: {str(e)}", {}, {}, {}, {}, {}, []


def _build_pie_html(actual_party_seats, party_vote_totals, sc):
    """Build a styled SVG donut chart + legend for party vote shares."""
    from math import pi, cos, sin

    individual_parties  = sc['parties']
    party_colors        = sc['party_colors']
    party_to_alliance   = get_party_to_alliance(sc)

    # Only include parties with votes, sorted descending
    pie_parties = sorted(
        [p for p in individual_parties if p not in ('AWAITED',) and party_vote_totals.get(p, 0) > 0],
        key=lambda p: party_vote_totals[p], reverse=True
    )
    if not pie_parties:
        return '<p style="padding:40px;color:#888;">No vote data available.</p>'

    pie_votes  = [party_vote_totals[p] for p in pie_parties]
    pie_colors = [party_colors.get(p, '#CCCCCC') for p in pie_parties]
    grand      = sum(pie_votes) or 1
    pie_pcts   = [v / grand * 100 for v in pie_votes]
    pie_seats  = [actual_party_seats.get(p, 0) for p in pie_parties]

    # SVG donut wedges — outer radius R, inner hole radius r
    cx, cy, R, r = 200, 200, 170, 80
    GAP = 0.012   # radians gap between slices for cleaner look
    angle = -pi / 2
    paths = []
    for i, (votes, color, party, pct) in enumerate(zip(pie_votes, pie_colors, pie_parties, pie_pcts)):
        sweep = max(votes / grand * 2 * pi - GAP, 0.001)
        a0, a1 = angle + GAP / 2, angle + GAP / 2 + sweep

        ox1, oy1 = cx + R * cos(a0), cy + R * sin(a0)
        ox2, oy2 = cx + R * cos(a1), cy + R * sin(a1)
        ix1, iy1 = cx + r * cos(a1), cy + r * sin(a1)
        ix2, iy2 = cx + r * cos(a0), cy + r * sin(a0)
        large = 1 if sweep > pi else 0
        d = (f"M{ox1:.2f},{oy1:.2f} "
             f"A{R},{R} 0 {large},1 {ox2:.2f},{oy2:.2f} "
             f"L{ix1:.2f},{iy1:.2f} "
             f"A{r},{r} 0 {large},0 {ix2:.2f},{iy2:.2f} Z")

        votes_fmt = f"{votes:,}"
        label_esc = party.replace("'", "\\'")
        paths.append(
            f'<path d="{d}" fill="{color}" stroke="white" stroke-width="1.5" '
            f'style="cursor:pointer;transition:transform 0.18s,filter 0.18s;" '
            f'onmouseover="pieHover(this,\'{label_esc}\',\'{pct:.1f}%\',\'{votes_fmt} votes\')" '
            f'onmouseout="pieOut(this)"/>'
        )
        angle += votes / grand * 2 * pi

    tooltip = '''<g id="pie-tooltip" style="pointer-events:none;display:none;">
        <rect id="pie-tt-bg" rx="8" ry="8" fill="rgba(30,30,40,0.88)" />
        <text id="pie-tt-party"  x="0" y="0" fill="white" font-size="13" font-weight="700" font-family="Segoe UI,sans-serif"/>
        <text id="pie-tt-pct"    x="0" y="0" fill="#ccc"  font-size="12" font-family="Segoe UI,sans-serif"/>
        <text id="pie-tt-votes"  x="0" y="0" fill="#aaa"  font-size="11" font-family="Segoe UI,sans-serif"/>
    </g>'''

    center_label = f'''
        <text x="{cx}" y="{cy - 10}" text-anchor="middle" fill="#444"
              font-size="13" font-weight="600" font-family="Segoe UI,sans-serif">PARTY</text>
        <text x="{cx}" y="{cy + 10}" text-anchor="middle" fill="#444"
              font-size="13" font-weight="600" font-family="Segoe UI,sans-serif">VOTE SHARE</text>'''

    svg = (f'<svg id="pie-svg" viewBox="0 0 400 400" width="360" height="360" '
           f'style="display:block;margin:0 auto;overflow:visible;">'
           f'{"".join(paths)}{center_label}{tooltip}</svg>')

    # Legend rows
    rows = ''
    for party, pct, seats, color, votes in zip(pie_parties, pie_pcts, pie_seats, pie_colors, pie_votes):
        alliance = party_to_alliance.get(party, '')
        alliance_tag = f'<span style="font-size:0.75em;color:#aaa;margin-left:5px;">· {alliance}</span>' if alliance else ''
        bar_w = max(2, round(pct * 1.6))
        votes_fmt = f"{votes:,}"
        rows += f'''
        <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #f0f0f0;">
            <div style="width:13px;height:13px;border-radius:3px;background:{color};flex-shrink:0;
                        box-shadow:0 1px 4px rgba(0,0,0,0.25);"></div>
            <div style="flex:1;min-width:0;">
                <div style="font-weight:700;font-size:0.9em;color:#1a1a2e;">{party}{alliance_tag}</div>
                <div style="background:#eee;border-radius:6px;height:6px;margin-top:4px;">
                    <div style="width:{bar_w}%;background:{color};height:6px;border-radius:6px;
                                transition:width 0.4s ease;"></div>
                </div>
                <div style="font-size:0.72em;color:#999;margin-top:2px;">{votes_fmt} votes &nbsp;·&nbsp; {seats} seats</div>
            </div>
            <div style="text-align:right;flex-shrink:0;">
                <div style="font-weight:900;font-size:1.05em;color:#1a1a2e;">{pct:.1f}%</div>
            </div>
        </div>'''

    js = '''
    <script>
    function pieHover(el, party, pct, votes) {
        el.style.filter = 'brightness(1.15) drop-shadow(0 4px 10px rgba(0,0,0,0.3))';
        el.style.transform = 'scale(1.04)';
        el.style.transformOrigin = '200px 200px';
        var tt   = document.getElementById('pie-tooltip');
        var bg   = document.getElementById('pie-tt-bg');
        var tp   = document.getElementById('pie-tt-party');
        var tpct = document.getElementById('pie-tt-pct');
        var tv   = document.getElementById('pie-tt-votes');
        tp.textContent   = party;
        tpct.textContent = pct;
        tv.textContent   = votes;
        tp.setAttribute('x', 200); tp.setAttribute('y', 242);
        tpct.setAttribute('x', 200); tpct.setAttribute('y', 258);
        tv.setAttribute('x', 200); tv.setAttribute('y', 272);
        tp.setAttribute('text-anchor','middle');
        tpct.setAttribute('text-anchor','middle');
        tv.setAttribute('text-anchor','middle');
        bg.setAttribute('x', 130); bg.setAttribute('y', 228);
        bg.setAttribute('width', 140); bg.setAttribute('height', 54);
        tt.style.display = 'block';
    }
    function pieOut(el) {
        el.style.filter = '';
        el.style.transform = '';
        document.getElementById('pie-tooltip').style.display = 'none';
    }
    </script>'''

    return f'''
    <div style="max-width:900px;margin:0 auto;display:flex;gap:36px;align-items:flex-start;flex-wrap:wrap;padding:16px 0;">
        <div style="flex:0 0 360px;">
            <h3 style="text-align:center;color:#1a1a2e;font-size:1em;margin-bottom:8px;
                        font-weight:700;letter-spacing:1px;text-transform:uppercase;opacity:0.7;">
                Party Vote Share
            </h3>
            {svg}
        </div>
        <div style="flex:1;min-width:260px;max-height:420px;overflow-y:auto;padding-right:8px;">
            <h3 style="color:#1a1a2e;font-size:1em;margin-bottom:10px;font-weight:700;
                        letter-spacing:1px;text-transform:uppercase;opacity:0.7;">Breakdown</h3>
            {rows}
        </div>
    </div>{js}'''


@app.route('/state/<state_code>')
def state_map_redirect(state_code):
    """Redirect old /state/<code> URLs to /?state=<code>"""
    return redirect(f'/?state={state_code}', code=301)

@app.route('/')
def index():
    """Single-page election map with state switcher"""
    state_code = request.args.get('state', DEFAULT_STATE).lower()
    sc = get_state_config(state_code)
    if sc is None:
        return f"<h1>Error</h1><p>Unknown state: {state_code}</p>", 404
    
    state_name = sc['name']
    print(f"Generating election map for {state_name}")
    
    try:
        plot, summary, party_vote_shares, party_vote_totals, actual_party_seats, district_vote_totals, district_party_seats_map, seat_data = create_election_map(state_name, state_code=state_code)
        
        if plot is None:
            return f"<h1>Error</h1><p>{summary}</p>", 500
        
        # Generate Bokeh HTML
        bokeh_html = file_html(plot, CDN, f"{state_name} Election Results")

        # Load previous election results from GitHub
        prev_data = {}
        prev_csv_path = f"prev_results_{state_code}.csv"
        prev_url, prev_token = get_github_url(prev_csv_path)
        try:
            prev_hdrs = {}
            if prev_token:
                prev_hdrs['Authorization'] = f'token {prev_token}'
            prev_resp = requests.get(prev_url, timeout=10, headers=prev_hdrs)
            if prev_resp.status_code == 200:
                if prev_token:
                    import base64 as _b64
                    prev_content = _b64.b64decode(json.loads(prev_resp.text)['content']).decode('utf-8')
                else:
                    prev_content = prev_resp.text
                prev_df = pd.read_csv(StringIO(prev_content))
                for _, prev_row in prev_df.iterrows():
                    try:
                        ac = int(prev_row['AC_NO'])
                        prev_data[str(ac)] = {
                            'win_cand':  str(prev_row.get('prev_win_cand', '')),
                            'win_party': str(prev_row.get('prev_win_party', '')),
                            'win_votes': int(prev_row.get('prev_win_votes', 0) or 0),
                            'win_pct':   float(prev_row.get('prev_win_pct', 0) or 0),
                            'sec_cand':  str(prev_row.get('prev_sec_cand', '')),
                            'sec_party': str(prev_row.get('prev_sec_party', '')),
                            'sec_votes': int(prev_row.get('prev_sec_votes', 0) or 0),
                            'sec_pct':   float(prev_row.get('prev_sec_pct', 0) or 0),
                            'margin':    int(prev_row.get('prev_margin', 0) or 0),
                        }
                    except Exception:
                        pass
                print(f"Loaded {len(prev_data)} prev rows from GitHub:{prev_csv_path}")
        except Exception as e:
            print(f"Could not load {prev_csv_path} from GitHub: {e}")
        _prev_data_json = json.dumps(prev_data)

        # Build SVG pie chart from party_vote_totals
        pie_html = _build_pie_html(actual_party_seats, party_vote_totals, sc)

        # ── Trends view ──────────────────────────────────────────────────────
        _p2a_trends = get_party_to_alliance(sc)
        _alliance_colors_trends = get_alliance_colors(sc)
        total_seats = len(seat_data)
        reporting = sum(1 for s in seat_data if s['votes_pct'] > 0)
        declared  = sum(1 for s in seat_data if s['votes_pct'] >= 99.9)
        # Per-alliance won/leading counts
        from collections import defaultdict
        _al_won     = defaultdict(int)
        _al_leading = defaultdict(int)
        for s in seat_data:
            if s['win_party'] == 'AWAITED':
                continue
            al = _p2a_trends.get(s['win_party'], s['win_party'])
            if s['votes_pct'] >= 99.9:
                _al_won[al] += 1
            elif s['votes_pct'] > 0:
                _al_leading[al] += 1
        # Build table rows sorted by total (won+leading)
        _all_alliances = sorted(
            set(list(_al_won.keys()) + list(_al_leading.keys())),
            key=lambda a: -(_al_won[a] + _al_leading[a])
        )
        _trends_rows = ''
        for al in _all_alliances:
            won_n = _al_won[al]
            lead_n = _al_leading[al]
            total_n = won_n + lead_n
            color = _alliance_colors_trends.get(al, '#95A5A6')
            _trends_rows += f'''
            <tr>
                <td style="padding:8px 10px;">
                    <span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{color};margin-right:6px;vertical-align:middle;"></span>
                    <strong>{al}</strong>
                </td>
                <td style="padding:8px 10px;text-align:center;color:#27ae60;font-weight:700;">{won_n}</td>
                <td style="padding:8px 10px;text-align:center;color:#e67e22;font-weight:700;">{lead_n}</td>
                <td style="padding:8px 10px;text-align:center;font-weight:800;font-size:1.05em;">{total_n}</td>
            </tr>'''
        majority = total_seats // 2 + 1
        trends_html = f'''
        <div style="max-width:700px;margin:0 auto;">
            <h2 style="font-size:1.3em;font-weight:800;color:#2c3e50;margin:0 0 6px 0;">📈 Seat Tally</h2>
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px;">
                <div style="background:#f0f4ff;border-radius:10px;padding:10px 18px;text-align:center;">
                    <div style="font-size:1.6em;font-weight:800;color:#667eea;">{reporting}</div>
                    <div style="font-size:0.75em;color:#666;font-weight:600;">REPORTING</div>
                </div>
                <div style="background:#f0fff4;border-radius:10px;padding:10px 18px;text-align:center;">
                    <div style="font-size:1.6em;font-weight:800;color:#27ae60;">{declared}</div>
                    <div style="font-size:0.75em;color:#666;font-weight:600;">DECLARED</div>
                </div>
                <div style="background:#fff8f0;border-radius:10px;padding:10px 18px;text-align:center;">
                    <div style="font-size:1.6em;font-weight:800;color:#e67e22;">{total_seats - reporting}</div>
                    <div style="font-size:0.75em;color:#666;font-weight:600;">AWAITED</div>
                </div>
                <div style="background:#f8f0ff;border-radius:10px;padding:10px 18px;text-align:center;">
                    <div style="font-size:1.6em;font-weight:800;color:#8e44ad;">{majority}</div>
                    <div style="font-size:0.75em;color:#666;font-weight:600;">MAJORITY MARK</div>
                </div>
            </div>
            <table style="width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <thead>
                    <tr style="background:#f0f4ff;">
                        <th style="padding:10px 10px;text-align:left;font-size:0.85em;color:#555;">ALLIANCE / PARTY</th>
                        <th style="padding:10px;text-align:center;font-size:0.85em;color:#27ae60;">✅ WON</th>
                        <th style="padding:10px;text-align:center;font-size:0.85em;color:#e67e22;">📊 LEADING</th>
                        <th style="padding:10px;text-align:center;font-size:0.85em;color:#333;">TOTAL</th>
                    </tr>
                </thead>
                <tbody>{_trends_rows}</tbody>
            </table>
            <p style="font-size:0.75em;color:#aaa;margin-top:10px;">Won = counting complete (100%). Leading = counting in progress.</p>
        </div>'''

        # ── Swing Seats view ─────────────────────────────────────────────────
        _swing_seats = []
        for s in seat_data:
            ac_str = str(s['ac_no'])
            if ac_str not in prev_data:
                continue
            prev_p = prev_data[ac_str].get('win_party', '')
            curr_p = s['win_party']
            if not prev_p or curr_p == 'AWAITED' or prev_p == curr_p:
                continue
            prev_al = _p2a_trends.get(prev_p, prev_p)
            curr_al = _p2a_trends.get(curr_p, curr_p)
            if prev_al == curr_al:
                continue  # within same alliance, not a real swing
            _swing_seats.append({
                'ac_name': s['ac_name'],
                'prev_party': prev_p,
                'curr_party': curr_p,
                'prev_al': prev_al,
                'curr_al': curr_al,
                'margin': s['margin'],
                'votes_pct': s['votes_pct'],
            })
        # Direction summary
        _direction_counts = defaultdict(int)
        for sw in _swing_seats:
            _direction_counts[(sw['prev_al'], sw['curr_al'])] += 1
        _direction_rows = ''
        for (frm, to), cnt in sorted(_direction_counts.items(), key=lambda x: -x[1]):
            frm_color = _alliance_colors_trends.get(frm, '#95A5A6')
            to_color  = _alliance_colors_trends.get(to,  '#95A5A6')
            _direction_rows += f'''
            <div style="display:flex;align-items:center;gap:8px;background:#f8f9ff;border-radius:8px;padding:8px 14px;font-size:0.9em;">
                <span style="background:{frm_color};color:white;padding:3px 9px;border-radius:5px;font-weight:700;">{frm}</span>
                <span style="color:#888;font-size:1.1em;">→</span>
                <span style="background:{to_color};color:white;padding:3px 9px;border-radius:5px;font-weight:700;">{to}</span>
                <span style="margin-left:auto;font-weight:800;font-size:1.05em;">{cnt} seats</span>
            </div>'''
        # Individual swing seat rows (sorted by declared first, then by margin)
        _seat_rows = ''
        for sw in sorted(_swing_seats, key=lambda x: (-x['votes_pct'], -x['margin'])):
            frm_color = _alliance_colors_trends.get(sw['prev_al'], '#95A5A6')
            to_color  = _alliance_colors_trends.get(sw['curr_al'], '#95A5A6')
            status = '✅' if sw['votes_pct'] >= 99.9 else '📊'
            margin_str = f"+{sw['margin']:,}" if sw['margin'] >= 0 else f"{sw['margin']:,}"
            _seat_rows += f'''
            <tr style="border-bottom:1px solid #f0f0f0;">
                <td style="padding:7px 10px;font-weight:600;font-size:0.88em;">{status} {sw["ac_name"]}</td>
                <td style="padding:7px 8px;text-align:center;">
                    <span style="background:{frm_color};color:white;padding:2px 7px;border-radius:4px;font-size:0.8em;font-weight:700;">{sw["prev_party"]}</span>
                </td>
                <td style="padding:7px 4px;text-align:center;color:#888;">→</td>
                <td style="padding:7px 8px;text-align:center;">
                    <span style="background:{to_color};color:white;padding:2px 7px;border-radius:4px;font-size:0.8em;font-weight:700;">{sw["curr_party"]}</span>
                </td>
                <td style="padding:7px 10px;text-align:right;font-size:0.85em;color:#555;">{margin_str}</td>
            </tr>'''
        prev_yr = sc.get('prev_year', 'Previous')
        swing_html = f'''
        <div style="max-width:700px;margin:0 auto;">
            <h2 style="font-size:1.3em;font-weight:800;color:#2c3e50;margin:0 0 6px 0;">🔄 Swing from {prev_yr}</h2>
            <p style="color:#666;font-size:0.88em;margin:0 0 14px 0;">{len(_swing_seats)} seats have flipped alliance from {prev_yr} results</p>
            {"<p style='color:#aaa;font-size:0.88em;'>No swing data yet — previous results not loaded.</p>" if not prev_data else ""}
            <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px;">{_direction_rows}</div>
            {"" if not _seat_rows else f"""
            <table style="width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                <thead>
                    <tr style="background:#f0f4ff;">
                        <th style="padding:9px 10px;text-align:left;font-size:0.82em;color:#555;">CONSTITUENCY</th>
                        <th style="padding:9px 8px;text-align:center;font-size:0.82em;color:#555;">{prev_yr}</th>
                        <th style="padding:9px 4px;"></th>
                        <th style="padding:9px 8px;text-align:center;font-size:0.82em;color:#555;">NOW</th>
                        <th style="padding:9px 10px;text-align:right;font-size:0.82em;color:#555;">MARGIN</th>
                    </tr>
                </thead>
                <tbody>{_seat_rows}</tbody>
            </table>"""}
        </div>'''

        # District filter data for voteshare JS
        _p2a = get_party_to_alliance(sc)
        _district_vote_totals_json = json.dumps(district_vote_totals)
        _district_party_seats_json = json.dumps(district_party_seats_map)
        _state_vote_totals_json = json.dumps(party_vote_totals)
        _state_seats_json = json.dumps(actual_party_seats)
        _pie_party_colors_json = json.dumps(sc['party_colors'])
        _pie_party_to_alliance_json = json.dumps(_p2a)
        _district_options_html = ''.join(
            f'<option value="{d}">{d}</option>'
            for d in sorted(district_vote_totals.keys())
        )
        
        # Build alliances dynamically from state config
        alliances = {}
        for alliance_name, alliance_info in sc['alliances'].items():
            breakdown = {}
            for party in alliance_info['parties']:
                breakdown[party] = {
                    'seats': actual_party_seats.get(party, 0),
                    'color': sc['party_colors'].get(party, '#95A5A6')
                }
            alliances[alliance_name] = {
                'parties': [alliance_name],
                'color': alliance_info['color'],
                'description': alliance_info['description'],
                'breakdown': breakdown
            }
        
        total_seats = sum(summary.values())
        
        # Build state navigation bar
        state_nav_html = ""
        for code, cfg in ALL_STATES.items():
            is_active = code == state_code
            style = "background: white; color: #667eea; font-weight: 700;" if is_active else "background: rgba(255,255,255,0.2); color: white;"
            state_nav_html += f'<a href="/?state={code}" style="flex:1;text-align:center;padding: 8px 0; border-radius: 6px; text-decoration: none; font-size: 0.9em; transition: all 0.2s; {style}">{cfg["name"]}</a>'

        # Build alliance cards HTML with party breakdown
        alliance_results_html = ""
        for alliance_name, alliance_info in alliances.items():
            alliance_color = alliance_info['color']
            alliance_parties = alliance_info['parties']
            alliance_description = alliance_info['description']
            
            # Calculate total votes and vote share for this alliance
            alliance_total_votes = sum(party_vote_totals.get(party, 0) for party in alliance_parties)
            alliance_vote_share = sum(party_vote_shares.get(party, 0) for party in alliance_parties)
            alliance_seats = sum(summary.get(party, 0) for party in alliance_parties)
            
            # Build party breakdown within alliance - show constituent parties with colors and seats
            party_breakdown = ""
            breakdown_data = alliance_info.get('breakdown', {})
            for party_name, party_info in breakdown_data.items():
                party_color = party_info['color']
                party_seats = party_info['seats']
                party_breakdown += f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.2);">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 12px; height: 12px; border-radius: 2px; background: {party_color};"></div>
                            <span style="font-size: 0.9em; color: white;">{party_name}</span>
                        </div>
                        <span style="font-size: 0.9em; font-weight: 600; color: white;">{party_seats}</span>
                    </div>
                """
            
            alliance_results_html += f"""
                <div class="alliance-card" style="
                    cursor: default; 
                    transition: all 0.3s ease;
                    background: linear-gradient(135deg, {alliance_color} 0%, {alliance_color}dd 100%);
                    padding: 20px;
                    border-radius: 14px;
                    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    position: relative;
                    overflow: hidden;
                " 
                     onmouseover="this.style.transform='translateY(-6px)'; this.style.boxShadow='0 8px 20px rgba(0,0,0,0.25)';"
                     onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(0, 0, 0, 0.15)';">
                    <div style="position: absolute; top: -20px; right: -20px; width: 100px; height: 100px; background: rgba(255,255,255,0.1); border-radius: 50%;"></div>
                    <div style="display: flex; justify-content: space-between; align-items: center; position: relative;">
                        <div style="flex: 1;">
                            <div style="color: white; font-weight: 800; font-size: 1.1em; margin-bottom: 8px; opacity: 0.95; text-transform: uppercase; letter-spacing: 0.5px;">{alliance_name}</div>
                            <div style="font-size: 2.5em; color: white; font-weight: 900; text-shadow: 0 3px 6px rgba(0,0,0,0.2); line-height: 1;">{alliance_seats}</div>
                            <div style="color: rgba(255,255,255,0.95); font-size: 0.9em; margin-top: 6px; font-weight: 600;">
                                <span style="opacity: 0.8;">📊</span> {alliance_vote_share:.1f}% votes
                            </div>
                        </div>
                        <div onclick="event.stopPropagation(); toggleBreakdown(this.closest('.alliance-card'), '{alliance_name}');" style="color: rgba(255,255,255,0.8); font-size: 1.4em; transition: transform 0.3s; padding: 8px; cursor: pointer;" class="expand-icon">▼</div>
                    </div>
                    <div class="breakdown" style="display: none; border-top: 2px solid rgba(255,255,255,0.3); padding-top: 12px; margin-top: 12px;">
                        <div style="font-size: 0.85em; color: rgba(255,255,255,0.9); font-weight: 700; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;">Party Breakdown:</div>
                        {party_breakdown}
                    </div>
                </div>
"""
        
        # Create wrapper with header and info panel
        _alliance_parties_js = json.dumps({name: [name] for name in sc['alliances'].keys()})

        # District pie filter: data script (f-string) + logic script (plain string, no escaping needed)
        _district_data_script = (
            '<script>'
            f'const _districtVotes={_district_vote_totals_json};'
            f'const _districtSeats={_district_party_seats_json};'
            f'const _stateVotes={_state_vote_totals_json};'
            f'const _stateSeats={_state_seats_json};'
            f'const _piePartyColors={_pie_party_colors_json};'
            f'const _piePartyToAlliance={_pie_party_to_alliance_json};'
            '</script>'
        )
        _district_pie_js = '''<script>
function filterPieByDistrict(district) {
    var votes = district ? _districtVotes[district] : _stateVotes;
    var seats = district ? _districtSeats[district] : _stateSeats;
    var title = district ? district + " \u2014 Party Vote Share" : "State-wide \u2014 Party Vote Share";
    renderDistrictPieChart(votes, seats, title);
}
function renderDistrictPieChart(partyVotes, partySeats, title) {
    var entries = Object.entries(partyVotes || {}).filter(function(e){return e[0]!=="AWAITED"&&e[1]>0;}).sort(function(a,b){return b[1]-a[1];});
    if (!entries.length) {
        document.getElementById("pie-chart-container").innerHTML = "<p style=\'padding:40px;color:#888;\'>No vote data available.</p>";
        return;
    }
    var total = entries.reduce(function(s,e){return s+e[1];},0) || 1;
    var NS = "http://www.w3.org/2000/svg";
    var cx=200,cy=200,R=170,r=80,GAP=0.012;
    var svg = document.createElementNS(NS,"svg");
    svg.setAttribute("id","pie-svg"); svg.setAttribute("viewBox","0 0 400 400");
    svg.setAttribute("width","360"); svg.setAttribute("height","360");
    svg.style.cssText = "display:block;margin:0 auto;overflow:visible;";
    var angle = -Math.PI/2;
    for (var i=0;i<entries.length;i++) {
        var party=entries[i][0], votes=entries[i][1];
        var sweep = Math.max(votes/total*2*Math.PI-GAP,0.001);
        var a0=angle+GAP/2, a1=angle+GAP/2+sweep;
        var ox1=cx+R*Math.cos(a0),oy1=cy+R*Math.sin(a0);
        var ox2=cx+R*Math.cos(a1),oy2=cy+R*Math.sin(a1);
        var ix1=cx+r*Math.cos(a1),iy1=cy+r*Math.sin(a1);
        var ix2=cx+r*Math.cos(a0),iy2=cy+r*Math.sin(a0);
        var large=sweep>Math.PI?1:0;
        var d="M"+ox1.toFixed(2)+","+oy1.toFixed(2)+" A"+R+","+R+" 0 "+large+",1 "+ox2.toFixed(2)+","+oy2.toFixed(2)+" L"+ix1.toFixed(2)+","+iy1.toFixed(2)+" A"+r+","+r+" 0 "+large+",0 "+ix2.toFixed(2)+","+iy2.toFixed(2)+" Z";
        var color=(_piePartyColors[party]||"#ccc");
        var pct=(votes/total*100).toFixed(1);
        var vfmt=votes.toLocaleString();
        var path=document.createElementNS(NS,"path");
        path.setAttribute("d",d); path.setAttribute("fill",color);
        path.setAttribute("stroke","white"); path.setAttribute("stroke-width","1.5");
        path.style.cssText="cursor:pointer;transition:transform 0.18s,filter 0.18s;";
        (function(el,p,pc,v){
            el.addEventListener("mouseover",function(){pieHover(el,p,pc,v);});
            el.addEventListener("mouseout",function(){pieOut(el);});
        })(path,party,pct+"%",vfmt+" votes");
        svg.appendChild(path);
        angle+=votes/total*2*Math.PI;
    }
    var labels=[["PARTY",-10],["VOTE SHARE",10]];
    for (var j=0;j<labels.length;j++) {
        var t=document.createElementNS(NS,"text");
        t.setAttribute("x",cx); t.setAttribute("y",cy+labels[j][1]);
        t.setAttribute("text-anchor","middle"); t.setAttribute("fill","#444");
        t.setAttribute("font-size","13"); t.setAttribute("font-weight","600");
        t.setAttribute("font-family","Segoe UI,sans-serif");
        t.textContent=labels[j][0]; svg.appendChild(t);
    }
    svg.insertAdjacentHTML("beforeend","<g id=\\"pie-tooltip\\" style=\\"pointer-events:none;display:none;\\"><rect id=\\"pie-tt-bg\\" rx=\\"8\\" ry=\\"8\\" fill=\\"rgba(30,30,40,0.88)\\"/><text id=\\"pie-tt-party\\" x=\\"0\\" y=\\"0\\" fill=\\"white\\" font-size=\\"13\\" font-weight=\\"700\\" font-family=\\"Segoe UI,sans-serif\\"/><text id=\\"pie-tt-pct\\" x=\\"0\\" y=\\"0\\" fill=\\"#ccc\\" font-size=\\"12\\" font-family=\\"Segoe UI,sans-serif\\"/><text id=\\"pie-tt-votes\\" x=\\"0\\" y=\\"0\\" fill=\\"#aaa\\" font-size=\\"11\\" font-family=\\"Segoe UI,sans-serif\\"/></g>");
    var rows="";
    for (var k=0;k<entries.length;k++) {
        var ep=entries[k][0],ev=entries[k][1];
        var epct=(ev/total*100).toFixed(1);
        var eseats=(partySeats&&partySeats[ep])||0;
        var ecolor=(_piePartyColors[ep]||"#ccc");
        var barW=Math.max(2,Math.round(parseFloat(epct)*1.6));
        var alliance=(_piePartyToAlliance[ep]||"");
        var alTag=alliance?"<span style=\\"font-size:0.75em;color:#aaa;margin-left:5px;\\">\\u00b7 "+alliance+"</span>":"";
        rows+="<div style=\\"display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #f0f0f0;\\">"
             +"<div style=\\"width:13px;height:13px;border-radius:3px;background:"+ecolor+";flex-shrink:0;box-shadow:0 1px 4px rgba(0,0,0,0.25);\\"></div>"
             +"<div style=\\"flex:1;min-width:0;\\">"
             +"<div style=\\"font-weight:700;font-size:0.9em;color:#1a1a2e;\\">"+ep+alTag+"</div>"
             +"<div style=\\"background:#eee;border-radius:6px;height:6px;margin-top:4px;\\">"
             +"<div style=\\"width:"+barW+"%;background:"+ecolor+";height:6px;border-radius:6px;transition:width 0.4s ease;\\"></div>"
             +"</div>"
             +"<div style=\\"font-size:0.72em;color:#999;margin-top:2px;\\">"+ev.toLocaleString()+" votes \u00a0\u00b7\u00a0 "+eseats+" seats</div>"
             +"</div>"
             +"<div style=\\"text-align:right;flex-shrink:0;\\"><div style=\\"font-weight:900;font-size:1.05em;color:#1a1a2e;\\">"+epct+"%</div></div>"
             +"</div>";
    }
    var container=document.getElementById("pie-chart-container");
    container.innerHTML="";
    var wrapper=document.createElement("div");
    wrapper.style.cssText="max-width:900px;margin:0 auto;display:flex;gap:36px;align-items:flex-start;flex-wrap:wrap;padding:16px 0;";
    var svgDiv=document.createElement("div"); svgDiv.style.cssText="flex:0 0 360px;";
    var h3=document.createElement("h3");
    h3.style.cssText="text-align:center;color:#1a1a2e;font-size:1em;margin-bottom:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;opacity:0.7;";
    h3.textContent=title; svgDiv.appendChild(h3); svgDiv.appendChild(svg);
    var legendDiv=document.createElement("div");
    legendDiv.style.cssText="flex:1;min-width:260px;max-height:420px;overflow-y:auto;padding-right:8px;";
    legendDiv.innerHTML="<h3 style=\\"color:#1a1a2e;font-size:1em;margin-bottom:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;opacity:0.7;\\">Breakdown</h3>"+rows;
    wrapper.appendChild(svgDiv); wrapper.appendChild(legendDiv);
    container.appendChild(wrapper);
}
</script>'''

        final_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state_name} Election Results - Interactive Map</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            margin: 0;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }}
        .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .info-panel {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px;
            border-left: 6px solid #667eea;
            margin: 20px 30px;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }}
        .info-panel h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        .election-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 10px;
            align-items: start;
        }}
        .party-result {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        .party-name {{
            font-weight: 600;
            margin-bottom: 5px;
            font-size: 1.05em;
        }}
        .party-seats {{
            font-size: 1.8em;
            color: #667eea;
            font-weight: bold;
        }}
        .map-container {{
            padding: 30px;
            background: white;
        }}

        /* ── Bokeh Tabs: vertical pill toggle on the RIGHT of the map ───── */
        /* Tabs notebook: flex-row so header goes to the right */
        .bk-root .bk-tabs-header {{
            display: flex !important;
            flex-direction: column !important;
            justify-content: flex-start !important;
            gap: 8px !important;
            padding: 12px 8px !important;
            background: transparent !important;
            border: none !important;
            order: 2 !important;
            align-self: flex-start !important;
            margin-top: 8px !important;
        }}
        /* Hide the default scrollbuttons */
        .bk-root .bk-tabs-header .bk-btn-group {{
            display: flex !important;
            flex-direction: column !important;
            gap: 8px !important;
        }}
        .bk-root .bk-headers-wrapper {{
            display: flex !important;
            flex-direction: column !important;
        }}
        /* Each tab button */
        .bk-root .bk-tab {{
            display: block !important;
            padding: 10px 18px !important;
            border-radius: 24px !important;
            border: 2px solid #667eea !important;
            background: white !important;
            color: #667eea !important;
            font-weight: 600 !important;
            font-size: 0.85em !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            text-align: center !important;
            white-space: nowrap !important;
            letter-spacing: 0.3px !important;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15) !important;
            min-width: 90px !important;
        }}
        .bk-root .bk-tab:hover {{
            background: #667eea !important;
            color: white !important;
            transform: translateX(-3px) !important;
            box-shadow: 0 4px 14px rgba(102, 126, 234, 0.35) !important;
        }}
        .bk-root .bk-tab.bk-active {{
            background: linear-gradient(135deg, #667eea, #764ba2) !important;
            color: white !important;
            border-color: transparent !important;
            box-shadow: 0 4px 14px rgba(102, 126, 234, 0.4) !important;
        }}
        /* The notebook container: row layout so content left, buttons right */
        .bk-root .bk-notebook {{
            display: flex !important;
            flex-direction: row !important;
            background: transparent !important;
        }}
        .bk-root .bk-notebook > .bk-panel-models-layouts-GridBox,
        .bk-root .bk-notebook > div:first-child {{
            order: 1 !important;
        }}
        footer {{
            background: #2c3e50;
            color: white;
            padding: 20px 30px;
            text-align: center;
        }}
        footer p {{
            margin: 5px 0;
            opacity: 0.9;
        }}
        .note {{
            font-size: 0.9em;
            font-style: italic;
            opacity: 0.7;
        }}
        
        /* Mobile responsive: stack filters on top of map */
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            .bk-root .bk-layout-row {{
                display: flex !important;
                flex-direction: column !important;
            }}
            .bk-root .bk-layout-row > div {{
                width: 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
            }}
            /* Selectors panel is already first in DOM — no reorder needed */
            /* Reduce selector widths on mobile */
            .bk-root select, .bk-root .bk-input {{
                width: 100% !important;
                max-width: 100% !important;
            }}
            /* Make map container scrollable if needed */
            .map-container {{
                padding: 10px;
                overflow-x: auto;
            }}
            header h1 {{
                font-size: 1.8em;
            }}
            .subtitle {{
                font-size: 0.95em;
            }}
            .info-panel {{
                margin: 10px;
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🗺️ {state_name} Election Results {sc['year']}</h1>
            <p class="subtitle">Live Interactive Analysis</p>
            <nav style="margin-top: 15px; display: flex; gap: 8px;">
                {state_nav_html}
            </nav>
        </header>

        <div class="info-panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="margin: 0; font-size: 1.8em; color: #2c3e50; font-weight: 800;">Results</h3>
                <div style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 12px 24px;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                    text-align: center;
                ">
                    <div style="color: white; font-size: 0.75em; font-weight: 600; opacity: 0.9; margin-bottom: 4px; letter-spacing: 1px;">LEADS IN</div>
                    <div style="color: white; font-size: 1.8em; font-weight: 900; line-height: 1;">{total_seats}/{total_seats}</div>
                    <div style="color: rgba(255,255,255,0.85); font-size: 0.7em; margin-top: 2px; font-weight: 500;">constituencies</div>
                </div>
            </div>
            <div class="election-summary">
                {alliance_results_html}
            </div>
            <p style="margin-top: 15px; color: #666; text-align: center;">
                <small>💡 Click the ▼ icon to expand party breakdown. Use the filters on the right to filter the map.</small>
            </p>
        </div>

        <!-- Map + vertical toggle on the right -->
        <div id="views-wrapper" style="display:flex; align-items:flex-start;">

            <div id="view-map" class="map-container" style="flex:1; min-width:0;">
                {bokeh_html}
            </div>
            <div id="view-voteshare" style="display:none; flex:1; min-width:0; padding:30px; background:white; overflow-y:auto;">
                <div style="margin-bottom:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                    <label style="font-weight:700;font-size:0.9em;color:#444;">Filter by District:</label>
                    <select id="district-pie-select" onchange="filterPieByDistrict(this.value)" style="padding:7px 14px;border-radius:8px;border:1.5px solid #c5caff;font-size:0.9em;background:white;color:#333;cursor:pointer;">
                        <option value="">All Districts (State-wide)</option>
                        {_district_options_html}
                    </select>
                </div>
                <div id="pie-chart-container">
                    {pie_html}
                </div>
            </div>
            <div id="view-trends" style="display:none; flex:1; min-width:0; padding:30px; background:white; overflow-y:auto;">
                {trends_html}
            </div>
            <div id="view-swing" style="display:none; flex:1; min-width:0; padding:30px; background:white; overflow-y:auto;">
                {swing_html}
            </div>

            <!-- Vertical toggle strip (desktop) / Horizontal tab bar (mobile) -->
            <div id="view-toggle-strip" style="
                display:flex; flex-direction:column; gap:10px;
                padding:16px 12px;
                background:#f8f9ff;
                border-left:1px solid #e0e4ff;
                align-self:stretch;
                align-items:center;
                min-width:115px;
            ">
                <button id="btn-map" onclick="showView('map')" style="
                    padding:12px 16px; border:none; cursor:pointer;
                    background:linear-gradient(135deg,#667eea,#764ba2);
                    color:white; font-weight:700; font-size:0.88em;
                    border-radius:10px; letter-spacing:0.3px;
                    box-shadow:0 4px 12px rgba(102,126,234,0.35);
                    transition:all 0.2s; white-space:nowrap; width:100%;
                ">🗺️ Map</button>
                <button id="btn-voteshare" onclick="showView('voteshare')" style="
                    padding:12px 16px; border:none; cursor:pointer;
                    background:#e9ecef; color:#555;
                    font-weight:600; font-size:0.88em;
                    border-radius:10px; letter-spacing:0.3px;
                    box-shadow:0 2px 6px rgba(0,0,0,0.08);
                    transition:all 0.2s; white-space:nowrap; width:100%;
                ">📊 Vote Share</button>
                <button id="btn-trends" onclick="showView('trends')" style="
                    padding:12px 16px; border:none; cursor:pointer;
                    background:#e9ecef; color:#555;
                    font-weight:600; font-size:0.88em;
                    border-radius:10px; letter-spacing:0.3px;
                    box-shadow:0 2px 6px rgba(0,0,0,0.08);
                    transition:all 0.2s; white-space:nowrap; width:100%;
                ">📈 Trends</button>
                <button id="btn-swing" onclick="showView('swing')" style="
                    padding:12px 16px; border:none; cursor:pointer;
                    background:#e9ecef; color:#555;
                    font-weight:600; font-size:0.88em;
                    border-radius:10px; letter-spacing:0.3px;
                    box-shadow:0 2px 6px rgba(0,0,0,0.08);
                    transition:all 0.2s; white-space:nowrap; width:100%;
                ">🔄 Swings</button>
            </div>
        </div>
        <style>
        @media (max-width: 768px) {{
            #views-wrapper {{
                flex-direction: column !important;
            }}
            #view-toggle-strip {{
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                overflow-x: auto !important;
                align-self: stretch !important;
                border-left: none !important;
                border-top: 1px solid #e0e4ff !important;
                padding: 10px 8px !important;
                min-width: unset !important;
                gap: 8px !important;
                order: -1;
            }}
            #view-toggle-strip button {{
                flex: 0 0 auto !important;
                width: auto !important;
            }}
        }}
        </style>

        <footer>
            <p>Data Source: Election Commission of India (ECI)</p>
        </footer>
    </div>
    
    <script>
        const _views = ['map', 'voteshare', 'trends', 'swing'];
        function showView(view) {{
            _views.forEach(v => {{
                const el  = document.getElementById('view-' + v);
                const btn = document.getElementById('btn-' + (v === 'voteshare' ? 'voteshare' : v));
                const active = v === view;
                if (el)  el.style.display = active ? 'flex' : 'none';
                if (btn) {{
                    btn.style.background  = active ? 'linear-gradient(135deg,#667eea,#764ba2)' : '#e9ecef';
                    btn.style.color       = active ? 'white' : '#555';
                    btn.style.fontWeight  = active ? '700' : '600';
                    btn.style.boxShadow   = active ? '0 4px 12px rgba(102,126,234,0.35)' : '0 2px 6px rgba(0,0,0,0.08)';
                }}
            }});
        }}

        // Mobile layout fix: Move filters below map on mobile devices
        function reorganizeLayoutForMobile() {{
            const isMobile = window.innerWidth <= 768;
            const bokehRow = document.querySelector('.bk-root .bk-layout-row');
            
            if (bokehRow && isMobile) {{
                const children = Array.from(bokehRow.children);
                if (children.length === 2) {{
                    // Map is first child, selectors is second
                    const map = children[0];
                    const selectors = children[1];
                    
                    // Make it column layout
                    bokehRow.style.flexDirection = 'column';
                    bokehRow.style.display = 'flex';
                    
                    // Set full width for both
                    map.style.width = '100%';
                    map.style.maxWidth = '100%';
                    selectors.style.width = '100%';
                    selectors.style.maxWidth = '100%';
                    
                    // Move selectors before map
                    bokehRow.insertBefore(selectors, map);
                }}
            }}
        }}
        
        // Disable pan/zoom on mobile so touch gestures scroll the page
        function disableMapDragOnMobile() {{
            const isMobile = window.innerWidth <= 768 || 'ontouchstart' in window;
            if (isMobile && window.Bokeh && window.Bokeh.documents && window.Bokeh.documents.length > 0) {{
                const doc = window.Bokeh.documents[0];
                const models = doc._all_models;
                if (models) {{
                    for (const [, model] of models) {{
                        if (model.type === 'PanTool' || model.type === 'WheelZoomTool') {{
                            model.active = false;
                        }}
                    }}
                }}
                // Also block touch events on the Bokeh canvas so they pass through to page scroll
                const canvases = document.querySelectorAll('.bk-canvas-events');
                canvases.forEach(function(canvas) {{
                    canvas.style.touchAction = 'auto';
                }});
            }}
        }}

        // Run on load and resize
        window.addEventListener('DOMContentLoaded', reorganizeLayoutForMobile);
        window.addEventListener('load', function() {{
            setTimeout(reorganizeLayoutForMobile, 500); // Wait for Bokeh to fully render
            setTimeout(disableMapDragOnMobile, 600);
        }});
        window.addEventListener('resize', reorganizeLayoutForMobile);
        
        // Previous election comparison helpers
        window._partyColors = {json.dumps(sc['party_colors'])};
        window._allianceColors = {json.dumps(get_alliance_colors(sc))};
        window._partyToAlliance = {json.dumps(get_party_to_alliance(sc))};
        window._savedResults = {{}};
        window._prevData = {_prev_data_json};

        window._loadPrevResults = function(acNo) {{
            const box = document.getElementById('results-box-' + acNo);
            if (!box) return;
            const data = (window._prevData || {{}})[String(acNo)];
            if (!data || !data.win_party) {{
                box.innerHTML = '<div style="padding:24px;text-align:center;color:#888;font-size:14px;">No {sc.get("prev_year", "previous")} results available.<br><small style="color:#bbb;">Run scrape_prev_results.py {state_code} to fetch them.</small></div>';
                return;
            }}
            const colors = window._partyColors ;
            const alColors = window._allianceColors || {{}};
            const p2a = window._partyToAlliance || {{}};
            function prevColor(party) {{
                return alColors[p2a[party]] || colors[party] || '#95A5A6';
            }}
            const c1 = prevColor(data.win_party);
            const c2 = prevColor(data.sec_party);
            let html = '';
            html += '<div style="margin-bottom:12px;padding:15px;background:linear-gradient(to right,' + c1 + '15,white);border-radius:10px;border-left:5px solid ' + c1 + ';box-shadow:0 2px 8px rgba(0,0,0,0.08);display:flex;justify-content:space-between;align-items:center;">';
            html += '<div><div style="font-size:16px;font-weight:bold;color:' + c1 + ';margin-bottom:4px;">' + data.win_party + '</div><div style="color:#666;font-size:14px;">' + data.win_cand + '</div></div>';
            html += '<div style="text-align:right;"><div style="background:' + c1 + ';color:white;padding:4px 10px;border-radius:5px;font-size:11px;font-weight:bold;margin-bottom:6px;display:inline-block;">WON BY ' + data.margin.toLocaleString() + '</div><div style="font-size:20px;font-weight:bold;color:#333;">' + data.win_votes.toLocaleString() + '</div><div style="font-size:16px;font-weight:bold;color:' + c1 + ';">' + data.win_pct + '%</div></div>';
            html += '</div>';
            if (data.sec_party) {{
                html += '<div style="margin-bottom:12px;padding:15px;background:linear-gradient(to right,' + c2 + '10,white);border-radius:10px;border-left:5px solid ' + c2 + ';box-shadow:0 2px 8px rgba(0,0,0,0.05);display:flex;justify-content:space-between;align-items:center;">';
                html += '<div><div style="font-size:16px;font-weight:bold;color:' + c2 + ';margin-bottom:4px;">' + data.sec_party + '</div><div style="color:#666;font-size:14px;">' + data.sec_cand + '</div></div>';
                html += '<div style="text-align:right;"><div style="font-size:20px;font-weight:bold;color:#333;">' + data.sec_votes.toLocaleString() + '</div><div style="font-size:16px;font-weight:bold;color:' + c2 + ';">' + data.sec_pct + '%</div></div>';
                html += '</div>';
            }}
            box.innerHTML = html;
        }};

        window._restoreCurResults = function(acNo) {{
            const box = document.getElementById('results-box-' + acNo);
            const saved = (window._savedResults || {{}})[acNo];
            if (box && saved !== undefined) box.innerHTML = saved;
        }};
        
        let currentFilter = null;
        
        // Alliance to parties mapping
        const allianceParties = {_alliance_parties_js};
        
        function toggleBreakdown(card, allianceName) {{
            const breakdown = card.querySelector('.breakdown');
            const icon = card.querySelector('.expand-icon');
            
            if (breakdown.style.display === 'none' || breakdown.style.display === '') {{
                breakdown.style.display = 'block';
                icon.style.transform = 'rotate(180deg)';
            }} else {{
                breakdown.style.display = 'none';
                icon.style.transform = 'rotate(0deg)';
            }}
        }}
        
        function filterByAlliance(allianceName) {{
            try {{
                // Get the Bokeh document - wait for it to be ready
                if (!window.Bokeh || !window.Bokeh.documents || window.Bokeh.documents.length === 0) {{
                    console.error('Bokeh not ready yet');
                    setTimeout(() => filterByAlliance(allianceName), 100);
                    return;
                }}
                
                const bokehDoc = Bokeh.documents[0];
                const filter_type = bokehDoc.get_model_by_name('filter_type_select');
                const filter_value = bokehDoc.get_model_by_name('filter_value_select');
                
                if (!filter_type || !filter_value) {{
                    console.error('Filter dropdowns not found');
                    return;
                }}
                
                // Set filter type to Party
                filter_type.value = 'Party';
                filter_type.change.emit();
                
                // Wait a bit for options to populate, then set the value
                setTimeout(() => {{
                    filter_value.value = allianceName;
                    filter_value.change.emit();
                }}, 50);
            }} catch (error) {{
                console.error('Error filtering by alliance:', error);
            }}
        }}
        
        function filterByParty(partyName) {{
            try {{
                // Get the Bokeh document - wait for it to be ready
                if (!window.Bokeh || !window.Bokeh.documents || window.Bokeh.documents.length === 0) {{
                    console.error('Bokeh not ready yet');
                    setTimeout(() => filterByParty(partyName), 100);
                    return;
                }}
                
                const bokehDoc = Bokeh.documents[0];
                const filter_type = bokehDoc.get_model_by_name('filter_type_select');
                const filter_value = bokehDoc.get_model_by_name('filter_value_select');
                
                if (!filter_type || !filter_value) {{
                    console.error('Filter dropdowns not found');
                    return;
                }}
                
                // Set filter type to Party
                filter_type.value = 'Party';
                filter_type.change.emit();
                
                // Wait a bit for options to populate, then set the value
                setTimeout(() => {{
                    filter_value.value = partyName;
                    filter_value.change.emit();
                }}, 50);
            }} catch (error) {{
                console.error('Error filtering by party:', error);
            }}
        }}
    </script>
    {_district_data_script}
    {_district_pie_js}
</body>
</html>
"""
        
        print(f"{state_name} map generated successfully with {total_seats} constituencies")
        return final_html
        
    except Exception as e:
        print(f"Error generating {state_name} map: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<h1>Error</h1><pre>{str(e)}</pre>", 500

@app.route('/test')
def test():
    """Test endpoint"""
    return jsonify({'status': 'working', 'message': 'Backend is responding!'})

@app.route('/view_map', methods=['POST'])
def view_map():
    """Generate map and return HTML fragment"""
    print("=== View Map Request Received ===")
    
    data = request.json
    state_name = data.get('state')
    map_type = data.get('map_type', 'basic')
    
    print(f"State: {state_name}, Map Type: {map_type}")
    
    if not state_name:
        print("ERROR: No state name provided")
        return jsonify({'error': 'State name is required'}), 400
    
    try:
        if map_type == 'election':
            print(f"Creating election map for {state_name}...")
            plot, result = create_election_map(state_name)
            if plot is None:
                print(f"ERROR: {result}")
                return jsonify({'error': result}), 400
            
            # Generate complete HTML using file_html
            html = file_html(plot, CDN, f"{state_name} - Election Results")
            print(f"SUCCESS: Generated election map HTML")
            return jsonify({
                'html': html,
                'summary': result,
                'success': True
            })
        else:
            print(f"Creating basic map for {state_name}...")
            plot, result = create_state_map(state_name)
            if plot is None:
                print(f"ERROR: {result}")
                return jsonify({'error': result}), 400
            
            # Generate complete HTML using file_html
            html = file_html(plot, CDN, f"{state_name} - Map")
            print(f"SUCCESS: Generated basic map HTML")
            return jsonify({
                'html': html,
                'constituencies': result,
                'success': True
            })
            
    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}', 'success': False}), 500

@app.route('/get_states')
def get_states():
    """API endpoint to get available states"""
    states = get_available_states()
    return jsonify({'states': states})

if __name__ == '__main__':
    import os
    # Use PORT from environment (for Render/Railway) or default to 5080
    port = int(os.environ.get('PORT', 5087))
    # Set debug=False for production
    app.run(host='0.0.0.0', port=port, debug=False)
