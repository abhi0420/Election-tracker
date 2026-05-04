import argparse
import concurrent.futures
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import sys
from datetime import datetime
import logging
from state_config import get_state_config, normalize_party_name as _normalize_party, ALL_STATES, DEFAULT_STATE

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def get_chrome_driver():
    """Initialize Chrome driver with proper options for GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--disable-crash-reporter")  # Prevent crash dumps
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-in-process-stack-traces")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--log-level=3")  # Suppress logs
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36")
    
    # Use system Chrome (works on GitHub Actions)
    return webdriver.Chrome(options=chrome_options)

def get_constituency_data(option_value, option_text, ac_no, election_event):
    driver = None
    try:
        logging.info(f"Processing constituency {ac_no}: {option_text}")

        driver = get_chrome_driver()
        driver.set_page_load_timeout(60)

        # Go directly to the table view page — skip the intermediate candidateswise page
        # URL pattern: Constituencywise{state_code}{ac_no}.htm
        table_url = f"https://results.eci.gov.in/{election_event}/Constituencywise{option_value}.htm"
        driver.get(table_url)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//table"))
        )
        table = driver.find_element(By.XPATH, "//table")

        header = [th.text for th in table.find_elements(By.TAG_NAME, "th")]
        rows = table.find_elements(By.TAG_NAME, "tr")
        table_data = [
            [td.text for td in row.find_elements(By.TAG_NAME, "td")]
            for row in rows if row.find_elements(By.TAG_NAME, "td")
        ]

        if not table_data:
            logging.warning(f"No table data for {option_text}, skipping")
            return ac_no, option_text, None, None

        return ac_no, option_text, header, table_data

    except Exception as e:
        logging.error(f"Error processing constituency {option_text}: {e}")
        return ac_no, option_text, None, None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def main(state_code=None, ac_start=None, ac_end=None):
    chunk_mode = ac_start is not None and ac_end is not None
    if state_code is None:
        state_code = DEFAULT_STATE
    
    sc = get_state_config(state_code)
    if sc is None:
        logging.error(f"Unknown state code: {state_code}")
        return
    
    election_event = sc['election_event']
    eci_state_code = sc['eci_state_code']
    total_pages = sc['total_pages']
    csv_file = sc['csv_file']
    electors_file = sc['electors_file']
    
    start = time.time()
    if chunk_mode:
        logging.info(f"Starting chunked scraper for {sc['name']} ACs {ac_start}-{ac_end}...")
    else:
        logging.info(f"Starting election data scraper for {sc['name']}...")

    # Build constituency list from known AC range — avoids slow statewise page entirely
    # Load names from electors/CSV file if available, fall back to AC number as label
    ac_names = {}
    for name_file in [electors_file, csv_file]:
        if name_file and os.path.exists(name_file):
            try:
                ndf = pd.read_csv(name_file)
                if 'AC_NO' in ndf.columns:
                    col = next((c for c in ['Constituency', 'AC_NAME', 'AC_Name'] if c in ndf.columns), None)
                    if col:
                        ac_names = {int(r['AC_NO']): str(r[col]) for _, r in ndf.iterrows() if pd.notna(r[col])}
                        logging.info(f"Loaded {len(ac_names)} constituency names from {name_file}")
                        break
            except Exception as e:
                logging.warning(f"Could not load names from {name_file}: {e}")

    ac_range = range(ac_start, ac_end + 1) if chunk_mode else range(1, sc['total_seats'] + 1)
    all_constituencies = [
        {"name": ac_names.get(n, f"AC {n}"), "number": str(n)}
        for n in ac_range
    ]
    logging.info(f"Built constituency list: {len(all_constituencies)} ACs")

    driver = None
    try:
        # Dictionary to store results
        results = {}

        # Use ThreadPoolExecutor for concurrent scraping
        # Reduced workers to prevent crashes and timeouts (8 workers for stability)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for constituency in all_constituencies:
                # New URL format: candidateswise-{eci_state_code}{number}.htm
                constituency_value = f"{eci_state_code}{constituency['number']}"
                futures.append(executor.submit(
                    get_constituency_data, 
                    constituency_value, 
                    constituency['name'],
                    int(constituency['number']),
                    election_event
                ))

            # Collect the results
            for future in concurrent.futures.as_completed(futures):
                ac_no, option_text, header, data = future.result()
                if header and data:
                    results[ac_no] = {
                        "name": option_text,
                        "header": header,
                        "data": data,
                    }
                    logging.info(f"✓ Data successfully retrieved for AC {ac_no}: {option_text}")

        # Convert results to election_results.csv format (for map)
        election_data = []
        for ac_no in sorted(results.keys()):
            result = results[ac_no]
            
            try:
                # Get table data rows
                table_rows = result["data"]
                if not table_rows or len(table_rows) == 0:
                    continue
                
                # Determine the number of columns from first row
                num_cols = len(table_rows[0])
                
                # Create appropriate column names based on number of columns
                if num_cols >= 7:
                    # Standard format: SNo, Candidate, Party, EVM Votes, Postal Votes, Total Votes, % of Votes
                    col_names = ['SNo', 'Candidate', 'Party', 'EVM Votes', 'Postal Votes', 'Total Votes', '% of Votes'][:num_cols]
                else:
                    # Fallback: generic column names
                    col_names = [f'Col{i}' for i in range(num_cols)]
                
                # Create DataFrame
                df = pd.DataFrame(table_rows, columns=col_names)
                
                # Find the columns we need
                candidate_col = 'Candidate' if 'Candidate' in df.columns else None
                party_col = 'Party' if 'Party' in df.columns else None
                votes_col = 'Total Votes' if 'Total Votes' in df.columns else None
                
                # Skip if we don't have required columns
                if not all([candidate_col, party_col, votes_col]):
                    logging.warning(f"Skipping AC {ac_no}: Missing required columns. Columns: {df.columns.tolist()}")
                    continue
                
                # Clean votes column
                df[votes_col] = df[votes_col].apply(lambda x: int(str(x).replace(',', '')) if x and str(x).strip() and str(x) != '-' else 0)
                
                # Sort by total votes
                df = df.sort_values(by=votes_col, ascending=False)
                
                # Get top 3 candidates
                if len(df) >= 3:
                    win_cand = df[candidate_col].iloc[0]
                    win_party = _normalize_party(df[party_col].iloc[0], sc)
                    win_votes = df[votes_col].iloc[0]
                    
                    sec_cand = df[candidate_col].iloc[1]
                    sec_party = _normalize_party(df[party_col].iloc[1], sc)
                    sec_votes = df[votes_col].iloc[1]
                    
                    thi_cand = df[candidate_col].iloc[2]
                    thi_party = _normalize_party(df[party_col].iloc[2], sc)
                    thi_votes = df[votes_col].iloc[2]
                    
                    margin = win_votes - sec_votes
                    total_votes = df[votes_col].sum()

                    # Skip if no votes counted yet — ECI shows candidate lists before counting
                    if total_votes == 0:
                        logging.info(f"Skipping AC {ac_no} {result['name']}: no votes counted yet")
                        continue

                    election_data.append({
                        'AC_NO': ac_no,
                        'Constituency': result['name'],
                        'win_cand': win_cand,
                        'win_party': win_party,
                        'win_votes': win_votes,
                        'sec_cand': sec_cand,
                        'sec_party': sec_party,
                        'sec_votes': sec_votes,
                        'thi_cand': thi_cand,
                        'thi_party': thi_party,
                        'thi_votes': thi_votes,
                        'margin': margin,
                        'tot_votes': total_votes
                    })
                else:
                    logging.warning(f"Skipping AC {ac_no}: Less than 3 candidates")
                    
            except Exception as e:
                logging.warning(f"Error processing data for AC {ac_no}: {e}")
                continue

        # Save results
        if len(election_data) > 0:
            election_df = pd.DataFrame(election_data)
            election_df = election_df.sort_values('AC_NO').reset_index(drop=True)

            if chunk_mode:
                # Chunk mode: save raw data to chunks/ — no electors merge, no JSON
                # Merge job will handle combining and finalization
                os.makedirs('chunks', exist_ok=True)
                chunk_file = f"chunks/{state_code}_{ac_start}_{ac_end}.csv"
                election_df.to_csv(chunk_file, index=False)
                logging.info(f"✓ Chunk CSV saved: {chunk_file} ({len(election_df)} constituencies)")
            else:
                # Full mode: merge with electors and save final CSV + JSON
                election_df = _merge_electors(election_df, electors_file)
                election_df.to_csv(csv_file, index=False)
                logging.info(f"✓ CSV saved: {csv_file} ({len(election_df)} constituencies)")

                # Legacy seat.csv
                seat_df = pd.DataFrame({
                    'Seat': election_df['Constituency'],
                    'Leading': election_df['win_party'],
                    'Trailing': election_df['sec_party'],
                    '3rd Place': election_df['thi_party'],
                    '1': election_df['win_votes'],
                    '2': election_df['sec_votes'],
                    '3': election_df['thi_votes'],
                    'Rest': election_df['tot_votes'] - election_df['win_votes'] - election_df['sec_votes'] - election_df['thi_votes']
                })
                seat_df.to_csv("seat.csv", index=False)
                logging.info("✓ Legacy CSV saved: seat.csv")

                timestamp = datetime.utcnow().isoformat() + 'Z'
                json_data = {
                    "last_updated": timestamp,
                    "total_seats": len(election_df),
                    "data": election_df.to_dict(orient='records')
                }
                json_file = csv_file.replace('.csv', '.json')
                with open(json_file, "w") as f:
                    json.dump(json_data, f, indent=2)
                logging.info(f"✓ JSON saved: {json_file}")
        else:
            logging.error("No election data collected! Check if constituencies have data available.")
            if chunk_mode:
                # Write empty chunk so merge job knows this chunk ran
                os.makedirs('chunks', exist_ok=True)
                chunk_file = f"chunks/{state_code}_{ac_start}_{ac_end}.csv"
                pd.DataFrame(columns=['AC_NO', 'Constituency', 'win_cand', 'win_party', 'win_votes',
                                      'sec_cand', 'sec_party', 'sec_votes', 'thi_cand', 'thi_party',
                                      'thi_votes', 'margin', 'tot_votes']).to_csv(chunk_file, index=False)
            else:
                pd.DataFrame(columns=['AC_NO', 'Constituency', 'win_cand', 'win_party', 'win_votes',
                                      'sec_cand', 'sec_party', 'sec_votes', 'thi_cand', 'thi_party',
                                      'thi_votes', 'margin', 'tot_votes', 'votes_pct']).to_csv(csv_file, index=False)
            election_df = pd.DataFrame()
        
        # Print summary
        end = time.time()
        logging.info(f"✓ Scraping completed in {end - start:.2f} seconds")
        logging.info(f"✓ Total constituencies processed: {len(results)}/{len(all_constituencies)}")
        
        # Show sample
        if len(election_data) > 0:
            sample_df = pd.DataFrame(election_data).head(3)
            logging.info("\nSample results:")
            logging.info(sample_df[['AC_NO', 'Constituency', 'win_party', 'win_votes', 'sec_party', 'sec_votes', 'margin']].to_string())
        
    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
        raise
    finally:
        if driver is not None:
            driver.quit()


def _merge_electors(election_df, electors_file):
    """Merge election results with electors data to compute votes_pct."""
    try:
        electors_df = pd.read_csv(electors_file)
        # Support two formats:
        # Old (Bihar): AC_No, Total Votes
        # New: AC_NO, Total_Electors, Turnout_Pct  ->  total_votes_cast = Total_Electors * Turnout_Pct / 100
        electors_df = electors_df.rename(columns={'AC_No': 'AC_NO', 'Total Votes': 'total_votes_cast'})
        if 'total_votes_cast' not in electors_df.columns:
            if 'Total_Electors' in electors_df.columns and 'Turnout_Pct' in electors_df.columns:
                electors_df['total_votes_cast'] = (
                    electors_df['Total_Electors'] * electors_df['Turnout_Pct'] / 100
                ).round(0).astype('Int64')
            elif 'Total_Electors' in electors_df.columns:
                # Fallback: use tot_votes directly as a % of Total_Electors
                electors_df = electors_df.rename(columns={'Total_Electors': 'total_votes_cast'})
        election_df = election_df.merge(electors_df[['AC_NO', 'total_votes_cast']], on='AC_NO', how='left')
        election_df['votes_pct'] = (
            (election_df['tot_votes'] / election_df['total_votes_cast'] * 100)
            .fillna(0).clip(upper=99.9).round(2)
        )
        election_df = election_df.drop(columns=['total_votes_cast'])
        logging.info("✓ Merged with electors data and calculated votes_pct")
    except FileNotFoundError:
        logging.warning(f"{electors_file} not found - using 100% as default")
        election_df['votes_pct'] = 100
    except Exception as e:
        logging.warning(f"Error merging electors data: {e} - using 100% as default")
        election_df['votes_pct'] = 100
    return election_df


if __name__ == "__main__":
    # Mode 1 (legacy):  python scraper.py tn
    # Mode 2 (chunk):   python scraper.py --state tn --start 1 --end 117
    parser = argparse.ArgumentParser(description='ECI election data scraper')
    parser.add_argument('state_positional', nargs='?', default=None, help='State code (positional, legacy)')
    parser.add_argument('--state', dest='state_flag', default=None, help='State code')
    parser.add_argument('--start', type=int, default=None, help='First AC number (inclusive)')
    parser.add_argument('--end', type=int, default=None, help='Last AC number (inclusive)')
    args = parser.parse_args()

    target_state = args.state_flag or args.state_positional or DEFAULT_STATE
    main(target_state, ac_start=args.start, ac_end=args.end)
