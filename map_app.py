from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import geopandas as gpd
from bokeh.plotting import figure
from bokeh.models import HoverTool, GeoJSONDataSource, Legend, LegendItem, Div, TapTool, CustomJS, Select
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



app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# Use Bihar-specific shapefile (local - has geometry, doesn't change)
SHAPEFILE_PATH = "ac/Bihar_AC_with_results.shp"

# Live CSV from GitHub (updates every 5 mins from scraper)
LIVE_CSV_URL = "https://raw.githubusercontent.com/abhi0420/election-tracker/main/election_results.csv"

def auto_merge_election_data():
    """
    Automatically merge election_results.csv with shapefile if needed
    Returns the merged GeoDataFrame or None if merge fails
    """
    try:
        print("[AUTO-MERGE] Starting auto-merge of election data with shapefile...")
        
        # Check if election_results.csv exists
        if not os.path.exists('election_results.csv'):
            print("[AUTO-MERGE] election_results.csv not found, skipping auto-merge")
            return None
        
        # Read shapefile (use clean version without results)
        clean_shapefile = 'ac/Bihar_AC_clean.shp'
        if not os.path.exists(clean_shapefile):
            print(f"[AUTO-MERGE] {clean_shapefile} not found, using current shapefile")
            clean_shapefile = SHAPEFILE_PATH
        
        print(f"[AUTO-MERGE] Reading shapefile: {clean_shapefile}")
        gdf = gpd.read_file(clean_shapefile)
        print(f"[AUTO-MERGE] Shapefile columns: {gdf.columns.tolist()}")
        
        # Read CSV
        print("[AUTO-MERGE] Reading election_results.csv")
        df = pd.read_csv('election_results.csv')
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
        print(f"[AUTO-MERGE] Saving to {SHAPEFILE_PATH}")
        gdf_merged.to_file(SHAPEFILE_PATH)
        
        print(f"[AUTO-MERGE] Complete! {gdf_merged['win_party'].notna().sum() if 'win_party' in gdf_merged.columns else 0} constituencies merged")
        return gdf_merged
        
    except Exception as e:
        import traceback
        print(f"[AUTO-MERGE] Failed with error:")
        traceback.print_exc()
        return None

def get_live_election_data():
    """Fetch latest election results CSV from GitHub"""
    try:
        response = requests.get(LIVE_CSV_URL, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        print(f"[LIVE DATA] Fetched live data: {len(df)} rows")
        return df
    except Exception as e:
        print(f"[LIVE DATA] Failed to fetch from GitHub: {e}")
        # Fallback to local CSV if available
        try:
            df = pd.read_csv("election_results.csv")
            print(f"[LIVE DATA] Using local fallback data: {len(df)} rows")
            return df
        except:
            print("[LIVE DATA] No data available")
            return None

def get_available_states():
    """Get list of all available states from shapefile"""
    try:
        gdf = gpd.read_file(SHAPEFILE_PATH)
        states = sorted(gdf['ST_NAME'].unique().tolist())
        return states
    except Exception as e:
        print(f"Error reading shapefile: {e}")
        return []

def create_state_map(state_name):
    """Create a Bokeh map for the specified state"""
    try:
        # Read shapefile and filter for the state
        gdf = gpd.read_file(SHAPEFILE_PATH)
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

def create_election_map(state_name):
    """Create election results map with party data - now uses LIVE data from GitHub"""
    try:
        import traceback
        
        # Fetch LIVE election data from GitHub
        live_data = get_live_election_data()
        
        # Read shapefile (has geometry only - doesn't need to update)
        gdf = gpd.read_file(SHAPEFILE_PATH)
        state_gdf = gdf[gdf['ST_NAME'].str.contains(state_name, case=False, na=False)].copy()
        
        if len(state_gdf) == 0:
            return None, f"State '{state_name}' not found!", {}, {}, {}
        
        # If we have live data, merge it with shapefile (replace old data with live data)
        if live_data is not None:
            # Drop old election columns from shapefile
            election_columns = ['AC_NO', 'winning_party', 'winner_candidate', 'winner_votes',
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
            
            # Merge with live data based on AC_NO
            # Assuming shapefile has AC_NO or we can match by name
            if 'AC_NO' in state_gdf.columns:
                state_gdf = state_gdf.merge(live_data, on='AC_NO', how='left')
            else:
                # Create AC_NO from index if needed
                state_gdf['AC_NO'] = range(1, len(state_gdf) + 1)
                state_gdf = state_gdf.merge(live_data, on='AC_NO', how='left')
            
            print("[MERGE] Merged live data with shapefile")
        
        # Define individual parties with their colors
        individual_parties = ['BJP', 'JDU', 'LJP', 'HAM', 'RJD', 'INC', 'CPIM', 'JSP', 'OTH', 'AWAITED']
        individual_party_colors = {
            'BJP': '#FF9900',
            'JDU': '#190061',
            'LJP': '#FFF300',
            'HAM': '#4C007A',
            'RJD': '#006400',
            'INC': '#1471C7',
            'CPIM': '#FF0000',
            'JSP': '#BA06C4',
            'OTH': '#95A5A6',
            'AWAITED': '#CCCCCC'  # Gray for awaiting results
        }
        
        # Party to alliance mapping
        party_to_alliance = {
            'BJP': 'NDA', 'JDU': 'NDA', 'LJP': 'NDA', 'HAM': 'NDA',
            'RJD': 'MGB', 'INC': 'MGB', 'CPIM': 'MGB',
            'JSP': 'JSP',
            'OTH': 'OTH',
            'AWAITED': 'AWAITED'  # Special category
        }
        
        # Check if election data columns exist in shapefile (clean column names from merge_data.py)
        required_columns = ['win_party', 'win_cand', 'win_votes',
                          'sec_party', 'sec_cand', 'sec_votes',
                          'thi_party', 'thi_cand', 'thi_votes',
                          'tot_votes', 'votes_pct']
        
        if not all(col in state_gdf.columns for col in required_columns):
            print("[AUTO-MERGE] Election data columns not found, attempting auto-merge...")
            merged_gdf = auto_merge_election_data()
            
            if merged_gdf is not None:
                # Re-read the shapefile after merge
                gdf = gpd.read_file(SHAPEFILE_PATH)
                state_gdf = gdf[gdf['ST_NAME'].str.contains(state_name, case=False, na=False)].copy()
                print("[AUTO-MERGE] Using auto-merged data")
            else:
                return None, "Error: Election data columns not found and auto-merge failed. Please ensure election_results.csv exists.", {}, {}, {}
        
        print("[DATA] Using election data from shapefile")
        
        # Calculate derived fields using pandas (not stored in shapefile)
        # Ensure numeric columns are proper type first
        state_gdf['win_votes'] = pd.to_numeric(state_gdf['win_votes'], errors='coerce').fillna(0)
        state_gdf['sec_votes'] = pd.to_numeric(state_gdf['sec_votes'], errors='coerce').fillna(0)
        state_gdf['thi_votes'] = pd.to_numeric(state_gdf['thi_votes'], errors='coerce').fillna(0)
        state_gdf['tot_votes'] = pd.to_numeric(state_gdf['tot_votes'], errors='coerce').fillna(0)
        state_gdf['votes_pct'] = pd.to_numeric(state_gdf['votes_pct'], errors='coerce').fillna(0)
        
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
        
        # Create plot
        p = figure(
            title=f"{state_name} - Election Results (Sample Data)",
            width=900,
            height=700,
            tools="pan,wheel_zoom,box_zoom,reset",
            toolbar_location=None,  # Remove toolbar
            x_axis_type="mercator",
            y_axis_type="mercator",
            background_fill_color="#f0f0f0",
            x_range=(x_range[0] - x_pad, x_range[1] + x_pad),
            y_range=(y_range[0] - y_pad, y_range[1] + y_pad)
        )
        
        # Convert to GeoJSON
        geosource = GeoJSONDataSource(geojson=state_gdf.to_json())
        
        # Map party names to colors for the color mapper (default: party-level)
        # Fill any unmapped parties with gray color
        state_gdf['party_color'] = state_gdf['winning_party'].map(individual_party_colors).fillna('#CCCCCC')
        
        # Map alliance colors
        alliance_colors_map = {
            'NDA': '#FF9900',
            'MGB': '#1471C7',
            'JSP': '#BA06C4',
            'OTH': '#95A5A6',
            'AWAITED': '#CCCCCC'  # Gray for awaiting
        }
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
        callback = CustomJS(args=dict(source=geosource), code="""
            const indices = source.selected.indices;
            
            // Check if this is a single-click (for popup) vs multi-select (for filtering)
            if (indices.length === 1) {
                const idx = indices[0];
                const data = source.data;
                
                const constituency = data['AC_NAME'][idx];
                const district = data['DIST_NAME'][idx];
                
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
                const colors = {
                    'BJP': '#FF9900',
                    'JDU': '#190061',
                    'LJP': '#FFF300',
                    'HAM': '#4C007A',
                    'RJD': '#006400',
                    'INC': '#1471C7',
                    'CPIM': '#FF0000',
                    'JSP': '#BA06C4',
                    'OTH': '#95A5A6',
                    'AWAITED': '#CCCCCC'
                };
                
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
                                <p style="margin: 5px 0 0 0; opacity: 0.9;">District: ${district}</p>
                            </div>
                            
                            <!-- Content -->
                            <div style="padding: 25px;">
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
                                                <div style="
                                                    padding: 8px 16px;
                                                    background: linear-gradient(135deg, #FF9900 0%, #FF9900dd 100%);
                                                    color: white;
                                                    border-radius: 20px;
                                                    font-size: 13px;
                                                    font-weight: 600;
                                                    box-shadow: 0 2px 5px rgba(255,153,0,0.3);
                                                ">BJP</div>
                                                <div style="
                                                    padding: 8px 16px;
                                                    background: linear-gradient(135deg, #006400 0%, #006400dd 100%);
                                                    color: white;
                                                    border-radius: 20px;
                                                    font-size: 13px;
                                                    font-weight: 600;
                                                    box-shadow: 0 2px 5px rgba(0,100,0,0.3);
                                                ">RJD</div>
                                                <div style="
                                                    padding: 8px 16px;
                                                    background: linear-gradient(135deg, #190061 0%, #190061dd 100%);
                                                    color: white;
                                                    border-radius: 20px;
                                                    font-size: 13px;
                                                    font-weight: 600;
                                                    box-shadow: 0 2px 5px rgba(25,0,97,0.3);
                                                ">JDU</div>
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
        """)
        
        geosource.selected.js_on_change('indices', callback)
        
        # Calculate summary (seat count) and vote percentages for individual parties
        party_counts = state_gdf['winning_party'].value_counts().to_dict()
        individual_summary = {party: party_counts.get(party, 0) for party in individual_parties}
        
        # Aggregate to alliance level for display
        alliance_list = ['NDA', 'MGB', 'JSP', 'OTH', 'AWAITED']
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
        alliance_colors_map = {
            'NDA': '#FF9900',
            'MGB': '#1471C7',
            'JSP': '#BA06C4',
            'OTH': '#95A5A6',
            'AWAITED': '#CCCCCC'
        }
        sorted_parties = sorted(summary.items(), key=lambda x: x[1], reverse=True)
        
        party_boxes = ""
        for party, seats in sorted_parties:
            party_boxes += f"""
                <div style="background: linear-gradient(135deg, {alliance_colors_map[party]} 0%, {alliance_colors_map[party]}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
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
            <div id="info-content" style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
                {party_boxes}
            </div>
            <div style="margin-top: 12px; padding-top: 10px; border-top: 2px solid #e9ecef; font-size: 11px; color: #495057; text-align: center; width: 100%; background: rgba(102, 126, 234, 0.05); border-radius: 6px; padding: 8px; font-weight: 600;">
                <span style="color: #667eea;">●</span> <strong style="color: #2c3e50;">TOTAL:</strong> <span style="color: #667eea; font-size: 13px; font-weight: 700;">{sum(summary.values())}</span> <span style="color: #6c757d;">seats</span>
            </div>
        </div>
        """
        
        info_div = Div(text=info_html, width=350, height=400)
        
        # Style
        p.title.text_font_size = "16pt"
        p.title.align = "center"
        p.xgrid.visible = False  # Hide gridlines
        p.ygrid.visible = False  # Hide gridlines
        p.xaxis.visible = False  # Hide x-axis
        p.yaxis.visible = False  # Hide y-axis
        p.outline_line_color = None  # Remove border
        
        # Prepare district stats, PC stats, and summary for JavaScript
        import json
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
                    title = `📊 ${{window.currentPartyFilter}}`;
                    summary_to_use = {{}};
                    summary_to_use[window.currentPartyFilter] = window.currentFilteredIndices.length;
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
                        <div onclick="filter_type.value='Party'; filter_type.change.emit(); setTimeout(() => {{ filter_value.value='${{party}}'; filter_value.change.emit(); }}, 50);" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
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
                    const party = window.currentPartyFilter;
                    const alliance = party_to_alliance[party];
                    title = `📊 ${{party}} (${{alliance}})`;
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
                        ${{title}}
                    </h3>
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
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
        individual_parties = ['NDA', 'MGB', 'JSP', 'OTH', 'BJP', 'JDU', 'LJP', 'HAM', 'RJD', 'INC', 'CPIM']
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
            const parties = {json.dumps(individual_parties)};
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 6px 6px; justify-items: start;">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 6px 6px; justify-items: start;">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 6px 6px; justify-items: start;">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 6px 6px; justify-items: start;">
                        ${{district_boxes}}
                    </div>
                    <div style="margin-top: 10px; padding-top: 5px; border-top: 1px solid #ddd; font-size: 9px; color: #666; text-align: center; width: 100%;">
                        <strong>Total:</strong> ${{district_total}} seats
                    </div>
                </div>
                `;
                
            }} else if (filterType === "Party") {{
                // Filter by Party
                window.currentPartyFilter = filterValue;
                const winning_parties = data['winning_party'];
                const selectedIndices = [];
                for (let i = 0; i < winning_parties.length; i++) {{
                    if (winning_parties[i] === filterValue) {{
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
                        <div style="background: ${{alliance_colors[alliance]}}; border-radius: 4px; padding: 8px; text-align: center; margin-bottom: 6px; width: 60px; height: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 6px 6px; justify-items: start;">
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
                        <div onclick="filter_type.value='Party'; filter_type.change.emit(); setTimeout(() => {{ filter_value.value='${{party}}'; filter_value.change.emit(); }}, 50);" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(auto-fill, minmax(70px, 1fr)); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 2px; justify-items: start; padding: 8px 0;">
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
                    <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 6px 6px; justify-items: start;">
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
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
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
                            <div onclick="filter_type.value='Party'; filter_type.change.emit(); setTimeout(() => {{ filter_value.value='${{party}}'; filter_value.change.emit(); }}, 50);" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
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
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
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
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
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
                            <div onclick="filter_type.value='Party'; filter_type.change.emit(); setTimeout(() => {{ filter_value.value='${{party}}'; filter_value.change.emit(); }}, 50);" style="background: linear-gradient(135deg, ${{party_colors[party]}} 0%, ${{party_colors[party]}}dd 100%); border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 6px; width: 70px; height: 70px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 3px 8px rgba(0,0,0,0.15); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer;" onmouseover="this.style.transform='translateY(-2px) scale(1.05)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.25)';" onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.boxShadow='0 3px 8px rgba(0,0,0,0.15)';">
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
                        <div style="font-size: 11px; display: grid; grid-template-columns: repeat(2, 1fr); grid-auto-flow: column; grid-template-rows: repeat(4, auto); gap: 8px 6px; justify-items: start; padding: 8px 0;">
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
        layout = row(p, selectors)
        
        return layout, summary, party_vote_shares, party_vote_totals, individual_summary
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"Error creating election map: {str(e)}", {}, {}, {}

@app.route('/')
def index():
    """Main page - automatically loads Bihar election map"""
    print("Index page loaded - generating Bihar election map")
    
    try:
        # Automatically generate Bihar election map
        plot, summary, party_vote_shares, party_vote_totals, actual_party_seats = create_election_map("Bihar")
        
        if plot is None:
            return f"<h1>Error</h1><p>{summary}</p>", 500
        
        # Generate Bokeh HTML
        bokeh_html = file_html(plot, CDN, "Bihar Election Results")
        
        # Party colors
        party_colors = {
            'NDA': '#FF9900',
            'MGB': '#1471C7',
            'JSP': '#BA06C4',
            'OTH': '#95A5A6'
        }
        
        # Define alliances with constituent parties and their ACTUAL seat allocations
        alliances = {
            'NDA': {
                'parties': ['NDA'],
                'color': '#FF9900',
                'description': 'BJP, JDU, LJP, HAM',
                'breakdown': {
                    'BJP': {'seats': actual_party_seats['BJP'], 'color': '#FF9900'},
                    'JDU': {'seats': actual_party_seats['JDU'], 'color': '#190061'},
                    'LJP': {'seats': actual_party_seats['LJP'], 'color': '#FFF300'},
                    'HAM': {'seats': actual_party_seats['HAM'], 'color': '#4C007A'}
                }
            },
            'MGB': {
                'parties': ['MGB'],
                'color': '#1471C7',
                'description': 'RJD, INC, CPIM',
                'breakdown': {
                    'RJD': {'seats': actual_party_seats['RJD'], 'color': '#006400'},
                    'INC': {'seats': actual_party_seats['INC'], 'color': '#1471C7'},
                    'CPIM': {'seats': actual_party_seats['CPIM'], 'color': '#FF0000'}
                }
            },
            'JSP': {
                'parties': ['JSP'],
                'color': '#BA06C4',
                'description': 'Janta Dal (Socialist)',
                'breakdown': {
                    'JSP': {'seats': actual_party_seats['JSP'], 'color': '#BA06C4'}
                }
            },
            'Others': {
                'parties': ['OTH'],
                'color': '#95A5A6',
                'description': 'Other Parties',
                'breakdown': {
                    'OTH': {'seats': actual_party_seats['OTH'], 'color': '#95A5A6'}
                }
            }
        }
        
        total_seats = sum(summary.values())
        
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
        final_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bihar Election Results - Interactive Map</title>
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
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🗺️ Bihar Election Results</h1>
            <p class="subtitle">Interactive Constituency Map with Sample Data</p>
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

        <div class="map-container">
            {bokeh_html}
        </div>

        <footer>
            <p>Data Source: India Assembly Constituencies Shapefile</p>
            <p class="note">Note: Election data is randomly generated for demonstration purposes</p>
        </footer>
    </div>
    
    <script>
        let currentFilter = null;
        
        // Alliance to parties mapping
        const allianceParties = {{
            'NDA': ['NDA'],
            'MGB': ['MGB'],
            'JSP': ['JSP'],
            'Others': ['OTH']
        }};
        
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
</body>
</html>
"""
        
        print(f"Bihar map generated successfully with {total_seats} constituencies")
        return final_html
        
    except Exception as e:
        print(f"Error generating Bihar map: {str(e)}")
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
    # Use PORT from environment (for Render/Railway) or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Set debug=False for production
    app.run(host='0.0.0.0', port=port, debug=False)
