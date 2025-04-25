from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import time
import logging
from datetime import datetime
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

def save_webpage(driver, search_query, take_screenshot=True):
    try:
        # Get the absolute path for outputs directory
        current_dir = os.getcwd()
        outputs_dir = os.path.join(current_dir, 'outputs')
        os.makedirs(outputs_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"ticketmaster_{search_query.replace(' ', '_')}_{timestamp}"
        
        # Save HTML
        html_filename = f"{base_filename}.html"
        html_filepath = os.path.join(outputs_dir, html_filename)
        
        logging.info(f"Saving HTML to directory: {outputs_dir}")
        logging.info(f"HTML Filename: {html_filename}")
        
        # Get the complete page source
        page_source = driver.page_source
        
        # Save the HTML with proper encoding
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write('<!DOCTYPE html>\n')
            f.write(page_source)
        
        # Save screenshot if requested
        screenshot_path = None
        if take_screenshot:
            screenshot_filename = f"{base_filename}.png"
            screenshot_path = os.path.join(outputs_dir, screenshot_filename)
            driver.save_screenshot(screenshot_path)
            logging.info(f"Screenshot saved: {screenshot_path}")
        
        # Verify files were saved
        if os.path.exists(html_filepath):
            file_size = os.path.getsize(html_filepath)
            if file_size > 0:
                logging.info(f"HTML file saved successfully! Size: {file_size/1024:.1f} KB")
                logging.info(f"Full path: {html_filepath}")
                return {
                    'html_path': html_filepath,
                    'screenshot_path': screenshot_path
                }
            else:
                logging.warning("HTML file was created but is empty")
                return None
        else:
            logging.error("HTML file was not created")
            return None
            
    except Exception as e:
        logging.error(f"Error saving webpage: {str(e)}")
        return None

def wait_for_page_load(driver, timeout=30):
    """Wait for the page to be fully loaded"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        return True
    except TimeoutException:
        logging.warning("Page load timeout")
        return False

def search_and_save_page(search_query, max_retries=2):
    logging.info(f"Starting search for: {search_query}")
    
    # Setup Chrome with optimized options
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    
    retry_count = 0
    while retry_count <= max_retries:
        try:
            # Go to Ticketmaster
            logging.info("Loading Ticketmaster...")
            driver.get("https://www.ticketmaster.com")
            
            if not wait_for_page_load(driver):
                raise TimeoutException("Page failed to load")
            
            time.sleep(2)  # Additional wait for dynamic content
            
            # Handle cookie consent if present
            try:
                cookie_button = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
                cookie_button.click()
                time.sleep(1)
            except:
                logging.info("No cookie consent popup found")
            
            # Find search box with improved selectors
            search_selectors = [
                'input[aria-label="Search"]',
                'input[placeholder="Search by Artist, Event or Venue"]',
                'input[type="search"]',
                '[data-testid="search-input"]',
                '.search-input'
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    if search_input.is_displayed():
                        break
                except:
                    continue
            
            if not search_input:
                raise NoSuchElementException("Could not find search input")
            
            # Perform search
            logging.info("Entering search query...")
            search_input.clear()
            search_input.send_keys(search_query)
            search_input.send_keys(Keys.RETURN)
            
            # Wait for search results with improved selectors
            result_selectors = [
                '[data-testid="event-card"]',
                '[data-testid="search-results"]',
                '.event-listing',
                '.search-results',
                '.event-list',
                '[class*="event-"]',
                '[class*="result-"]'
            ]
            
            results_found = False
            for selector in result_selectors:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    results_found = True
                    logging.info("Search results found")
                    break
                except:
                    continue
            
            if not results_found:
                logging.warning("Could not confirm results - will try to save anyway")
            
            # Ensure page is fully loaded
            if not wait_for_page_load(driver):
                raise TimeoutException("Search results page failed to load")
            
            # Scroll to load all content
            logging.info("Loading all content...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Save the webpage
            logging.info("Saving webpage...")
            saved_files = save_webpage(driver, search_query)
            
            if saved_files and os.path.exists(saved_files['html_path']):
                logging.info("Success! Files saved:")
                logging.info(f"HTML: {saved_files['html_path']}")
                if saved_files['screenshot_path']:
                    logging.info(f"Screenshot: {saved_files['screenshot_path']}")
                return saved_files
            
            return None
            
        except Exception as e:
            logging.error(f"Attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                logging.info(f"Retrying... (Attempt {retry_count + 1})")
                time.sleep(2)  # Wait before retry
            else:
                logging.error("Max retries reached. Giving up.")
                return None
            
        finally:
            if retry_count == max_retries or not retry_count:
                logging.info("Closing browser...")
                driver.quit()

def execute_crawler():
    """Execute crawler.py after scraper has completed"""
    logging.info("Starting crawler process...")
    try:
        # Get the absolute path of crawler.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        crawler_path = os.path.join(current_dir, 'crawler.py')
        
        # Execute crawler.py
        subprocess.run([sys.executable, crawler_path], check=True)
        logging.info("Crawler process completed successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing crawler: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error while executing crawler: {str(e)}")

if __name__ == "__main__":
    try:
        query = input("\nEnter search query (Artist, Event or Venue): ").strip()
        if query:
            saved_files = search_and_save_page(query)
            if saved_files:
                # Execute crawler only after scraper has completed successfully
                execute_crawler()
            else:
                logging.error("Failed to save the webpage. Please check the logs for details.")
        else:
            logging.error("Search query cannot be empty")
    except KeyboardInterrupt:
        logging.info("\nOperation cancelled by user")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")