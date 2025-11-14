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
    
    return webdriver.Chrome(options=chrome_options)

def extract_candidate_info(text):
    """Extract candidate name and party from text like 'SHRI RAMCHANDRA PASWAN\n(JDU)'"""
    if not text or '\n' not in text:
        return '', ''
    parts = text.split('\n')
    candidate = parts[0].strip()
    party = parts[1].strip('()') if len(parts) > 1 else ''
    return candidate, party

def clean_votes(text):
    """Convert vote text to integer, handling commas and zeros"""
    if not text or text == '-':
        return 0
    # Remove commas and convert to int
    return int(text.replace(',', ''))

def main():
    start = time.time()
    logging.info("Starting FAST election data scraper...")
    logging.info("Scraping summary tables directly from all 13 pages...")

    driver = get_chrome_driver()
    all_results = []
    
    try:
        # Scrape all 13 pages of constituency summary tables
        for page_num in range(1, 14):
            url = f"https://results.eci.gov.in/ResultAcGenNov2025/statewiseS04{page_num}.htm"
            
            logging.info(f"Fetching page {page_num}/13: {url}")
            driver.get(url)
            
            # Wait for table
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            # Find the main table with all constituencies
            table = driver.find_element(By.TAG_NAME, "table")
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            # Process each row (skip header)
            for row in rows[1:]:  # Skip header row
                cells = row.find_elements(By.TAG_NAME, "td")
                
                # Check if this is a valid data row
                if len(cells) >= 6:
                    try:
                        # Extract data from cells
                        constituency_name = cells[0].text.strip()
                        ac_no = cells[1].text.strip()
                        
                        # Leading candidate (column 2)
                        leading_text = cells[2].text.strip()
                        leading_cand, leading_party = extract_candidate_info(leading_text)
                        
                        # Leading votes (column 3)
                        leading_votes = clean_votes(cells[3].text.strip())
                        
                        # Trailing candidate (column 4)
                        trailing_text = cells[4].text.strip()
                        trailing_cand, trailing_party = extract_candidate_info(trailing_text)
                        
                        # Trailing votes (column 5)
                        trailing_votes = clean_votes(cells[5].text.strip())
                        
                        # Calculate margin
                        margin = leading_votes - trailing_votes
                        
                        # Only add if we have valid data
                        if constituency_name and ac_no.isdigit():
                            all_results.append({
                                'AC_NO': int(ac_no),
                                'Constituency': constituency_name,
                                'win_cand': leading_cand,
                                'win_party': leading_party,
                                'win_votes': leading_votes,
                                'sec_cand': trailing_cand,
                                'sec_party': trailing_party,
                                'sec_votes': trailing_votes,
                                'margin': margin
                            })
                            
                    except Exception as e:
                        logging.warning(f"Error processing row: {e}")
                        continue
            
            logging.info(f"✓ Extracted {len([r for r in all_results if r])} constituencies so far")
        
        # Create DataFrame
        df = pd.DataFrame(all_results)
        
        # Sort by AC_NO
        df = df.sort_values('AC_NO').reset_index(drop=True)
        
        # Save to CSV - format for election_results.csv (matches our map)
        output_df = df[['AC_NO', 'Constituency', 'win_cand', 'win_party', 'win_votes', 
                        'sec_cand', 'sec_party', 'sec_votes', 'margin']]
        
        output_df.to_csv("election_results.csv", index=False)
        logging.info(f"✓ CSV saved: election_results.csv ({len(df)} constituencies)")
        
        # Also create the old format for backward compatibility
        seat_df = pd.DataFrame({
            'Seat': df['Constituency'],
            'Leading': df['win_party'],
            'Trailing': df['sec_party'],
            '3rd Place': '',  # Not available in summary
            '1': df['win_votes'],
            '2': df['sec_votes'],
            '3': 0,  # Not available in summary
            'Rest': 0  # Not available in summary
        })
        seat_df.to_csv("seat.csv", index=False)
        logging.info(f"✓ Legacy CSV saved: seat.csv")
        
        # Save JSON with metadata
        timestamp = datetime.utcnow().isoformat() + 'Z'
        json_data = {
            "last_updated": timestamp,
            "total_seats": len(df),
            "data": df.to_dict(orient='records')
        }
        
        with open("election_results.json", "w") as f:
            json.dump(json_data, f, indent=2)
        logging.info("✓ JSON saved: election_results.json")
        
        # Print summary
        end = time.time()
        logging.info(f"✓ FAST scraping completed in {end - start:.2f} seconds!")
        logging.info(f"✓ Total constituencies: {len(df)}/243")
        
        # Show sample data
        if len(df) > 0:
            logging.info("\nSample results:")
            logging.info(df.head(3).to_string())
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
