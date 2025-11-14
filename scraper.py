import concurrent.futures
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Party name mapping - convert full names to short codes
PARTY_NAME_MAP = {
    'Bharatiya Janata Party': 'BJP',
    'Janata Dal (United)': 'JDU',
    'Lok Janshakti Party (Ram Vilas)': 'LJP',
    'Hindustani Awam Morcha (Secular)': 'HAM',
    'Rashtriya Janata Dal': 'RJD',
    'Indian National Congress': 'INC',
    'Communist Party of India (Marxist)': 'CPIM',
    'Communist Party of India (Marxist-Leninist) (Liberation)': 'CPIM',
    'Communist Party of India': 'CPIM',
    'CPI': 'CPIM',
    'CPI(M)': 'CPIM',
    'CPIM': 'CPIM',
    'Jharkhand Mukti Morcha': 'OTH',
    'Bahujan Samaj Party': 'OTH',
    'BSP': 'OTH',
    'Samajwadi Party': 'OTH',
    'Aam Aadmi Party': 'OTH',
    'All India Majlis-E-Ittehadul Muslimeen': 'OTH',
    'AIMIM': 'OTH',
    'Independent': 'OTH',
    'IND': 'OTH',
    'None of the Above': 'OTH',
    'NOTA': 'OTH'
}

def normalize_party_name(party_name):
    """Convert full party name to short code"""
    if not party_name or pd.isna(party_name):
        return 'OTH'
    
    party_name = str(party_name).strip()
    
    # Direct match
    if party_name in PARTY_NAME_MAP:
        return PARTY_NAME_MAP[party_name]
    
    # Partial match for variations
    party_upper = party_name.upper()
    if 'BJP' in party_upper or 'BHARATIYA JANATA' in party_upper:
        return 'BJP'
    elif 'JD(U)' in party_upper or 'JANATA DAL (UNITED)' in party_upper:
        return 'JDU'
    elif 'LJP' in party_upper or 'LOK JANSHAKTI' in party_upper:
        return 'LJP'
    elif 'HAM' in party_upper or 'HINDUSTANI AWAM' in party_upper:
        return 'HAM'
    elif 'RJD' in party_upper or 'RASHTRIYA JANATA' in party_upper:
        return 'RJD'
    elif 'INC' in party_upper or 'CONGRESS' in party_upper:
        return 'INC'
    elif 'CPI(M)' in party_upper or ('COMMUNIST' in party_upper and 'MARXIST' in party_upper):
        return 'CPIM'
    elif 'CPI' in party_upper or 'COMMUNIST' in party_upper:
        return 'CPIM'  # Map all CPI variants to CPIM for our display
    elif 'JSP' in party_upper or 'JANSATTA' in party_upper:
        return 'JSP'
    elif 'BSP' in party_upper or 'BAHUJAN SAMAJ' in party_upper:
        return 'BSP'
    elif 'SP' in party_upper or 'SAMAJWADI' in party_upper:
        return 'OTH'  # Map to OTH as not in our display list
    elif 'AAP' in party_upper or 'AAM AADMI' in party_upper:
        return 'OTH'  # Map to OTH as not in our display list
    elif 'AIMIM' in party_upper or 'MAJLIS' in party_upper:
        return 'OTH'  # Map AIMIM to OTH
    elif 'BSP' in party_upper or 'BAHUJAN SAMAJ' in party_upper:
        return 'OTH'  # Map BSP to OTH
    elif 'INDEPENDENT' in party_upper or 'IND' == party_upper:
        return 'OTH'  # Map independents to OTH
    elif 'NOTA' in party_upper or 'NONE OF THE ABOVE' in party_upper:
        return 'OTH'  # Map NOTA to OTH
    else:
        # Unknown party - map to OTH
        return 'OTH'


def get_chrome_driver():
    """Initialize Chrome driver with proper options for GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36")
    
    # Use system Chrome (works on GitHub Actions)
    return webdriver.Chrome(options=chrome_options)

def get_constituency_data(option_value, option_text, ac_no):
    driver = None
    try:
        logging.info(f"Processing constituency {ac_no}: {option_text}")
        # Initialize WebDriver
        driver = get_chrome_driver()

        # Construct the URL for the constituency (new format for November 2025)
        constituency_url = f"https://results.eci.gov.in/ResultAcGenNov2025/candidateswise-{option_value}.htm"
        driver.get(constituency_url)

        # Wait for the "Constituency Wise Table View" link
        table_view_link = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'Constituencywise')]"))
        )
        table_view_link.click()

        # Wait for the new page to load and locate the table
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, "//table"))
        )
        table = driver.find_element(By.XPATH, "//table")

        # Extract header and rows
        header = [th.text for th in table.find_elements(By.TAG_NAME, "th")]
        rows = table.find_elements(By.TAG_NAME, "tr")
        table_data = [
            [td.text for td in row.find_elements(By.TAG_NAME, "td")]
            for row in rows if row.find_elements(By.TAG_NAME, "td")
        ]
        
        # IMPORTANT: Only return if we have data
        if not table_data or len(table_data) == 0:
            logging.warning(f"No table data found for {option_text}")
            return ac_no, option_text, None, None

        # Return the extracted data with AC number
        return ac_no, option_text, header, table_data

    except Exception as e:
        logging.error(f"Error processing constituency {option_text}: {e}")
        return ac_no, option_text, None, None
    finally:
        if driver:
            driver.quit()


def main():
    start = time.time()
    logging.info("Starting election data scraper...")

    # Set up initial WebDriver to get constituency list from table
    driver = get_chrome_driver()
    
    try:
        # New URL for November 2025 elections
        driver.get("https://results.eci.gov.in/ResultAcGenNov2025/statewiseS041.htm")
        
        # Wait for table to load
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        # Get all constituency rows from all pages (there are 13 pages total)
        all_constituencies = []
        
        for page_num in range(1, 14):  # Pages 1-13
            if page_num == 1:
                url = "https://results.eci.gov.in/ResultAcGenNov2025/statewiseS041.htm"
            else:
                url = f"https://results.eci.gov.in/ResultAcGenNov2025/statewiseS04{page_num}.htm"
            
            logging.info(f"Fetching constituency list from page {page_num}/13...")
            driver.get(url)
            time.sleep(1)
            
            # Find all table rows
            table = driver.find_element(By.TAG_NAME, "table")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:  # Has constituency name and number
                    constituency_name = cells[0].text.strip()
                    constituency_num = cells[1].text.strip()
                    
                    if constituency_name and constituency_num and constituency_num.isdigit():
                        all_constituencies.append({
                            "name": constituency_name,
                            "number": constituency_num
                        })
        
        logging.info(f"Found {len(all_constituencies)} constituencies to process")
        
        # TESTING: Only scrape first 25 constituencies for faster testing
        all_constituencies = all_constituencies[:25]
        logging.info(f"[TEST MODE] Limiting to first {len(all_constituencies)} constituencies")

        # Dictionary to store results
        results = {}

        # Use ThreadPoolExecutor for concurrent scraping (MAXIMUM workers for speed)
        # Each worker gets its own Chrome driver instance
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            futures = []
            for constituency in all_constituencies:
                # New URL format: candidateswise-S04{number}.htm
                constituency_value = f"S04{constituency['number']}"
                futures.append(executor.submit(
                    get_constituency_data, 
                    constituency_value, 
                    constituency['name'],
                    int(constituency['number'])
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
                    win_party = normalize_party_name(df[party_col].iloc[0])
                    win_votes = df[votes_col].iloc[0]
                    
                    sec_cand = df[candidate_col].iloc[1]
                    sec_party = normalize_party_name(df[party_col].iloc[1])
                    sec_votes = df[votes_col].iloc[1]
                    
                    thi_cand = df[candidate_col].iloc[2]
                    thi_party = normalize_party_name(df[party_col].iloc[2])
                    thi_votes = df[votes_col].iloc[2]
                    
                    margin = win_votes - sec_votes
                    total_votes = df[votes_col].sum()
                    
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

        # Save to election_results.csv
        if len(election_data) > 0:
            election_df = pd.DataFrame(election_data)
            election_df = election_df.sort_values('AC_NO').reset_index(drop=True)
            
            # Merge with electors data to calculate votes counted percentage
            try:
                electors_df = pd.read_csv('electors_after_deletion.csv')
                electors_df = electors_df.rename(columns={'AC_No': 'AC_NO', 'Total Votes': 'total_votes_cast'})
                
                # Merge on AC_NO
                election_df = election_df.merge(
                    electors_df[['AC_NO', 'total_votes_cast']], 
                    on='AC_NO', 
                    how='left'
                )
                
                # Calculate votes counted percentage
                # tot_votes = votes counted so far
                # total_votes_cast = total votes cast (from electors file)
                election_df['votes_pct'] = (
                    (election_df['tot_votes'] / election_df['total_votes_cast'] * 100)
                    .fillna(0)
                    .round(2)
                )
                
                # Drop total_votes_cast column (we don't need it in final CSV)
                election_df = election_df.drop(columns=['total_votes_cast'])
                
                logging.info(f"✓ Merged with electors data and calculated votes counted %")
                
            except FileNotFoundError:
                logging.warning("electors_after_deletion.csv not found - using 100% as default")
                election_df['votes_pct'] = 100
            except Exception as e:
                logging.warning(f"Error merging electors data: {e} - using 100% as default")
                election_df['votes_pct'] = 100
            
            election_df.to_csv("election_results.csv", index=False)
            logging.info(f"✓ CSV saved: election_results.csv ({len(election_df)} constituencies)")
        else:
            logging.error("No election data collected! Check if constituencies have data available.")
            # Create empty file
            pd.DataFrame(columns=['AC_NO', 'Constituency', 'win_cand', 'win_party', 'win_votes', 
                                  'sec_cand', 'sec_party', 'sec_votes', 'thi_cand', 'thi_party', 
                                  'thi_votes', 'margin', 'tot_votes', 'votes_pct']).to_csv("election_results.csv", index=False)
            election_df = pd.DataFrame()
        
        # Also create legacy seat.csv format
        if len(election_df) > 0:
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
            
            # Save JSON with metadata
            timestamp = datetime.utcnow().isoformat() + 'Z'
            json_data = {
                "last_updated": timestamp,
                "total_seats": len(election_df),
                "data": election_df.to_dict(orient='records')
            }
            
            with open("election_results.json", "w") as f:
                json.dump(json_data, f, indent=2)
            logging.info("✓ JSON saved: election_results.json")
        
        # Print summary
        end = time.time()
        logging.info(f"✓ Scraping completed in {end - start:.2f} seconds")
        logging.info(f"✓ Total constituencies processed: {len(results)}/{len(all_constituencies)}")
        
        # Show sample
        if len(election_df) > 0:
            logging.info("\nSample results:")
            logging.info(election_df.head(3)[['AC_NO', 'Constituency', 'win_party', 'win_votes', 'sec_party', 'sec_votes', 'margin']].to_string())
        
    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
