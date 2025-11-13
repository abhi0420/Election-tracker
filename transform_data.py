"""
Transform scraper output (seat.csv) to election_results.csv format
Adjust this script based on actual live data structure
"""

import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def transform_data():
    """
    Transform seat.csv to election_results.csv format
    ADJUST THIS FUNCTION BASED ON ACTUAL LIVE DATA
    """
    try:
        # Read the scraper output
        scraper_df = pd.read_csv('seat.csv')
        logging.info(f"✓ Loaded seat.csv with {len(scraper_df)} rows")
        logging.info(f"  Columns: {list(scraper_df.columns)}")
        
        # TODO: Adjust this mapping based on actual data structure tomorrow
        # Current expected columns: Seat, Leading, Trailing, 3rd Place, 1, 2, 3, Rest
        
        # Create constituency number mapping (you'll need to verify this)
        constituency_mapping = create_constituency_mapping(scraper_df)
        
        # Transform to election_results.csv format
        results = []
        for idx, row in scraper_df.iterrows():
            ac_no = constituency_mapping.get(row['Seat'], idx + 1)
            
            # TODO: Adjust these field mappings based on actual data
            result = {
                'AC_NO': ac_no,
                'winning_party': row['Leading'],  # Adjust field name
                'winner_candidate': f"Candidate {ac_no}",  # TODO: Get from live data if available
                'winner_votes': row['1'],  # Adjust field name
                'second_party': row['Trailing'],  # Adjust field name
                'second_candidate': f"Candidate {ac_no + 243}",  # TODO: Get from live data
                'second_votes': row['2'],  # Adjust field name
                'third_party': row['3rd Place'],  # Adjust field name
                'third_candidate': f"Candidate {ac_no + 486}",  # TODO: Get from live data
                'third_votes': row['3'],  # Adjust field name
                'total_votes': row['1'] + row['2'] + row['3'] + row['Rest'],
                'votes_counted_percent': 99.0  # TODO: Get from live data if available
            }
            results.append(result)
        
        # Create DataFrame
        results_df = pd.DataFrame(results)
        
        # Save to election_results.csv
        results_df.to_csv('election_results.csv', index=False)
        logging.info(f"✓ Saved election_results.csv with {len(results_df)} rows")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Error transforming data: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_constituency_mapping(df):
    """
    Create mapping from constituency name to AC_NO
    ADJUST THIS BASED ON ACTUAL CONSTITUENCY NAMES
    """
    # TODO: Replace with actual mapping from constituency names to numbers
    mapping = {}
    for idx, row in df.iterrows():
        mapping[row['Seat']] = idx + 1
    
    logging.info(f"  Created mapping for {len(mapping)} constituencies")
    return mapping


def preview_data():
    """Preview the transformation without saving"""
    try:
        scraper_df = pd.read_csv('seat.csv')
        print("\n" + "="*80)
        print("CURRENT SCRAPER DATA (seat.csv)")
        print("="*80)
        print(scraper_df.head())
        print(f"\nColumns: {list(scraper_df.columns)}")
        print(f"Total rows: {len(scraper_df)}")
        
        if 'election_results.csv' in pd.io.common.file_exists('election_results.csv'):
            results_df = pd.read_csv('election_results.csv')
            print("\n" + "="*80)
            print("TARGET FORMAT (election_results.csv)")
            print("="*80)
            print(results_df.head())
            print(f"\nColumns: {list(results_df.columns)}")
        
    except Exception as e:
        print(f"Error previewing: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'preview':
        preview_data()
    else:
        print("\n🔄 Starting data transformation...")
        print("="*80)
        success = transform_data()
        if success:
            print("\n✅ Transformation complete!")
            print("\nNext steps:")
            print("1. Verify election_results.csv has correct data")
            print("2. Run merge_data.py to update shapefile")
            print("3. Test the map with: python map_app.py")
        else:
            print("\n❌ Transformation failed - check logs above")
