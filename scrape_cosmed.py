from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
import time
import json
import os
import re
from tqdm import tqdm

COSMED_BASE_URL = "https://shop.cosmed.com.tw"
COSMED_ALL_PRODUCTS_URL = "https://shop.cosmed.com.tw/v2/official/SalePageCategory/0"

def scrape_cosmed_products(base_url, all_products_url, scroll_delay=3, num_scrolls=2, debug_limit=None):
    """
    Scrapes product details from COSMED's all products page by simulating scrolling
    and attempts to extract the brand name.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    chrome_options.add_argument(f"user-agent={user_agent}")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    products_data = []

    try:
        driver.get(all_products_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.product-card__vertical')))

        previous_height = driver.execute_script("return document.body.scrollHeight;")
        no_new_content_count = 0
        max_no_new_content = 10  # Increased the tolerance
        scroll_attempts = 0
        max_scroll_attempts = 100 # Added a maximum scroll limit as a safety

        while no_new_content_count < max_no_new_content and scroll_attempts < min(max_scroll_attempts, num_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_delay)
            current_height = driver.execute_script("return document.body.scrollHeight;")

            if current_height == previous_height:
                no_new_content_count += 1
            else:
                previous_height = current_height
                no_new_content_count = 0
            scroll_attempts += 1
            print(f"Scroll attempt: {scroll_attempts}, Current height: {current_height}, No new content count: {no_new_content_count}")

        time.sleep(scroll_delay * 3)  # Extra time to ensure final content loads

        # Get page source after scrolling is complete
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product_cards = soup.select('a.product-card__vertical')
        print(f"Number of product cards found after scrolling: {len(product_cards)}")

        
        # Get all product links and IDs
        product_links = {}
        # First get all links using JavaScript
        js_links = driver.execute_script("""
            var links = document.querySelectorAll('a.product-card__vertical');
            var results = {};
            for (var i = 0; i < links.length; i++) {
                results[i] = links[i].getAttribute('href');
            }
            return results;
        """)
        
        print(f"Number of links from JavaScript: {len(js_links)}")
        
        count = 0
        for i, card in enumerate(tqdm(product_cards, desc="Processing products")):
            if debug_limit and count >= debug_limit:
                break  # Limit the loop for debugging
                
            try:
                # Get URL from JavaScript results
                url = None
                if str(i) in js_links:
                    url = base_url + js_links[str(i)]
                    # print(f"URL: {url}")
                
                name_element = card.select_one('[data-qe-id="body-sale-page-title-text"]')
                name = name_element.text.strip() if name_element else None
                # print(f"Name: {name}")
                
                brand = None
                if name:
                    match_brackets = re.search(r'【(.*?)】', name)
                    if match_brackets:
                        brand = match_brackets.group(1).strip()
                        name = re.sub(r'【.*?】\s*', '', name).strip()
                    if not brand and ' ' in name:
                        brand = name.split(' ', 1)[0].strip()
                # print(f"Brand: {brand}")

                image_element = card.select_one('figure.product-card__vertical__frame img.product-card__vertical__media')
                image_url = image_element['src'] if image_element and 'src' in image_element.attrs else None
                image_url = image_url.replace('//', 'https://') if image_url and image_url.startswith('//') else image_url
                # print(f"Image URL: {image_url}")

                price_element = card.select_one('[data-qe-id="body-price-text"]')
                price_text = price_element.text.replace('NT$', '').replace(',', '').strip() if price_element else None
                price = float(price_text) if price_text else None
                # print(f"Price: {price}")

                if name and price is not None and image_url and url:
                    products_data.append({
                        'name': name,
                        'brand': brand,
                        'price': price,
                        'image_url': image_url,
                        'url': url,
                        'retailer': 'Cosmed'
                    })
                    count += 1
                else:
                    print("--- Missing data for this product ---")

            except Exception as e:
                print(f"Error extracting data from card {i}: {e}")

        print(f"Number of products collected: {len(products_data)}")

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        driver.quit()
    return products_data

if __name__ == "__main__":
    start_time = time.time()
    print(f"Scraping product data from COSMED: {COSMED_ALL_PRODUCTS_URL}")
    cosmed_products = scrape_cosmed_products(COSMED_BASE_URL, COSMED_ALL_PRODUCTS_URL, debug_limit=None)
    end_time = time.time()
    duration = end_time - start_time
    num_items = len(cosmed_products)

    print(f"\nScraped {num_items} products from COSMED.")
    print(f"Time taken to scrape: {duration:.2f} seconds")

    output_file = './beauty4/cosmed_products.json'
    os.makedirs('./beauty4', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cosmed_products, f, ensure_ascii=False, indent=4)
    print(f"\nScraped COSMED data saved to {output_file}")

# scrolls 
# 1 -> 3s; 300 / h=23865
# 2 -> 500 / 400 3s: 500
# 3 -> 900
# 4 -> 600
# 5 -> 700