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

def scrape_watsons_products(url, max_pages=50):  # Limiting max pages for testing
    """
    Scrapes product details from Watsons category pages with pagination,
    correctly extracting brand from span and name from the a tag.
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
    current_url = url
    page_number = 1

    try:
        while current_url and page_number <= max_pages:
            print(f"Fetching page: {current_url}")
            driver.get(current_url)
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'productContainer')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            product_containers = soup.select('div.productContainer.gridMode')

            for container in tqdm(product_containers, desc=f"Scraping page {page_number}"):
                name_link_element = container.select_one('h2.productName a')
                price_element = container.select_one('div.productPrice div.formatted-value span.afterPromo-price')
                image_element = container.select_one('div.productImage a e2-product-thumbnail e2-media img')

                product_url = WATSONS_BASE_URL + name_link_element['href'] if name_link_element and 'href' in name_link_element.attrs else None
                brand_span = name_link_element.select_one('span')
                full_text = name_link_element.get_text(strip=True)

                brand = brand_span.text.strip() if brand_span else None
                product_name = full_text.replace(brand if brand else '', '', 1).strip() if full_text else None

                price_text = price_element.text.replace('$', '').replace(',', '').strip() if price_element else None

                # Extract only the numeric part of the price using regex
                if price_text:
                    match = re.search(r'(\d+\.?\d*)', price_text)
                    if match:
                        price = float(match.group(1))
                    else:
                        price = None
                else:
                    price = None

                image_url = image_element['src'] if image_element and 'src' in image_element.attrs else None

                if product_name and price is not None and image_url and product_url:
                    products_data.append({
                        'name': product_name,
                        'brand': brand,
                        'price': price,
                        'image_url': image_url,
                        'url': product_url,
                        'retailer': 'Watsons'
                    })

            # Find the "next page" button
            next_button = None
            next_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.page-link i.icon-arrow-right')
            if next_buttons:
                next_button_parent = next_buttons[-1].find_element(By.XPATH, '..')
                if next_button_parent.get_attribute('href') != current_url:
                    current_url = next_button_parent.get_attribute('href')
                    page_number += 1
                else:
                    current_url = None # No more new pages
            else:
                current_url = None # No next button found

            time.sleep(1) # Be polite

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        driver.quit()
    return products_data

if __name__ == "__main__":
    start_time = time.time()
    print(f"Scraping product data from Watsons: {WATSONS_ALL_PRODUCTS_URL}")
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
