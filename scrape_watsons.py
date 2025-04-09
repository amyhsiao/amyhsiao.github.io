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
import re  # Import the regular expression library
from tqdm import tqdm

WATSONS_BASE_URL = "https://www.watsons.com.tw"
WATSONS_ALL_PRODUCTS_URL = "https://www.watsons.com.tw/%E5%85%A8%E9%83%A8%E5%95%86%E5%93%81/c/1"
PAGE_SIZE = 64  # Number of items per page. change to 64 for formal

def scrape_watsons_products(base_url, max_pages=2):
    """
    Scrapes product details from Watsons category pages by parsing Schema.org JSON-LD with debugging.
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
        for page_number in range(max_pages):
            page_url = f"{base_url}?pageSize={PAGE_SIZE}&currentPage={page_number}"
            print(f"Fetching page: {page_url}")
            driver.get(page_url)
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'script[type="application/ld+json"].structured-data')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            structured_data_scripts = soup.select('script[type="application/ld+json"].structured-data')

            print(f"Found {len(structured_data_scripts)} structured data scripts on page {page_number + 1}")

            for script in structured_data_scripts:
                try:
                    data = json.loads(script.string)
                    print("--- Structured Data Found ---")
                    # print(json.dumps(data, indent=4, ensure_ascii=False))
                    # print("--- End of Structured Data ---")

                    products_in_script = []
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        products_in_script.append(data)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Product':
                                products_in_script.append(item)

                    for product_data in products_in_script:
                        print("--- Processing Product Data ---")
                        # print(json.dumps(product_data, indent=4, ensure_ascii=False))
                        # print("--- End of Processing Product Data ---")

                        name = product_data.get('name')
                        brand_info = product_data.get('brand')
                        brand = brand_info.get('name') if isinstance(brand_info, dict) else brand_info
                        offers = product_data.get('offers')
                        price = None
                        if isinstance(offers, dict):
                            price = offers.get('lowPrice')
                            if price is not None:
                                price = float(price)
                        image_urls = product_data.get('image')
                        print(f"Image URLs: {image_urls}")  # Debug print
                        image_url = image_urls[0] if isinstance(image_urls, list) and image_urls else image_urls if isinstance(image_urls, str) else None
                        sku = product_data.get('sku')

                        product_url_element = soup.select_one('h2.productName a')
                        print(f"Product URL Element: {product_url_element}") # Debug print
                        url = WATSONS_BASE_URL + product_url_element['href'] if product_url_element and 'href' in product_url_element.attrs else None
                        print(f"Product URL: {url}") # Debug print

                        if name is not None and price is not None and image_url is not None and url is not None and \
                           name != ... and brand != ... and price != ... and image_url != ... and url != ...:
                            products_data.append({
                                'name': name,
                                'brand': brand,
                                'price': price,
                                'image_url': image_url,
                                'url': url,
                                'retailer': 'Watsons'
                            })
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                except Exception as e:
                    print(f"Error processing structured data: {e}")

            time.sleep(1) # Be polite

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        driver.quit()
    return products_data

if __name__ == "__main__":
    start_time = time.time()
    print(f"Scraping product data from Watsons using Schema.org: {WATSONS_ALL_PRODUCTS_URL}")
    watsons_products = scrape_watsons_products(WATSONS_ALL_PRODUCTS_URL)
    end_time = time.time()
    duration = end_time - start_time
    num_items = len(watsons_products)

    print(f"\nScraped {num_items} products from Watsons.")
    print(f"Time taken to scrape: {duration:.2f} seconds")

    # Save the scraped Watsons data to a JSON file in the beauty4 directory
    output_file = './beauty4/watsons_products.json'
    os.makedirs('./beauty4', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(watsons_products, f, ensure_ascii=False, indent=4)
    print(f"\nScraped Watsons data saved to {output_file}")