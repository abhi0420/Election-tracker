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

def get_constituency_data(option_value, option_text):
    driver = None
    try:
        logging.info(f"Processing constituency: {option_text}")
        # Initialize WebDriver
        driver = get_chrome_driver()

        # Construct the URL for the constituency (new format for November 2025)
        constituency_url = f"https://results.eci.gov.in/ResultAcGenNov2025/candidateswise-{option_value}.htm"
        driver.get(constituency_url)

        # Wait for the "Constituency Wise Table View" link
        table_view_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'Constituencywise')]"))
        )
        table_view_link.click()

        # Wait for the new page to load and locate the table
        WebDriverWait(driver, 4).until(
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

        # Extract columns of interest
        indices_of_interest = [2, 5, 6]  # Adjust these indices based on your table structure
        filtered_header = [header[i] for i in indices_of_interest]
        filtered_data = [[row[i] for i in indices_of_interest] for row in table_data]

        # Return the extracted data
        return option_text, filtered_header, filtered_data

    except Exception as e:
        logging.error(f"Error processing constituency {option_text}: {e}")
        return option_text, None, None
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
            
            logging.info(f"Fetching page {page_num}/13...")
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

        # Dictionary to store results
        results = {}

        # Use ThreadPoolExecutor for concurrent scraping
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for constituency in all_constituencies:
                # New URL format: candidateswise-S04{number}.htm
                constituency_value = f"S04{constituency['number']}"
                futures.append(executor.submit(
                    get_constituency_data, 
                    constituency_value, 
                    constituency['name']
                ))

            # Collect the results
            for future in concurrent.futures.as_completed(futures):
                option_text, header, data = future.result()
                if header and data:
                    results[option_text] = {
                        "header": header,
                        "data": data,
                    }
                    logging.info(f"✓ Data successfully retrieved for {option_text}")

        # Convert results to DataFrame
        final_df = pd.DataFrame([], columns=['Seat', 'Leading', 'Trailing', '3rd Place', '1', '2', '3', 'Rest'])
        for constituency, result in results.items():
            df = pd.DataFrame(result["data"], columns=result["header"])
            df['Total Votes'] = df['Total Votes'].astype(int)
            df = df.sort_values(by="Total Votes", ascending=False)
            final_df.loc[len(final_df)] = [
                constituency, df['Party'].iloc[0], df['Party'].iloc[1], df['Party'].iloc[2],
                df['Total Votes'].iloc[0], df['Total Votes'].iloc[1], df['Total Votes'].iloc[2],
                df['Total Votes'].iloc[3:].sum()
            ]

        # Save to CSV
        final_df.to_csv("seat.csv", index=False)
        logging.info("✓ CSV file saved: seat.csv")
        
        # Convert to JSON with metadata
        timestamp = datetime.utcnow().isoformat() + 'Z'
        json_data = {
            "last_updated": timestamp,
            "total_seats": len(final_df),
            "data": final_df.to_dict(orient='records')
        }
        
        with open("seat.json", "w") as f:
            json.dump(json_data, f, indent=2)
        logging.info("✓ JSON file saved: seat.json")
        
        # Print summary
        end = time.time()
        logging.info(f"✓ Scraping completed in {end - start:.2f} seconds")
        logging.info(f"✓ Total constituencies processed: {len(results)}/{len(all_constituencies)}")
        
    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
