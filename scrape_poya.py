from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
import time
import json
import os
from tqdm import tqdm  # For the loading bar

POYA_BASE_URL = "https://www.poyabuy.com.tw"
ALL_PRODUCTS_CATEGORY_URL = "https://www.poyabuy.com.tw/v2/official/SalePageCategory/0"

def scrape_poya_products_from_category(category_url, num_scrolls=3):
    """
    Scrapes product details directly from the main Poya category page with infinite scrolling and a loading bar.
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
        driver.get(category_url)
        wait = WebDriverWait(driver, 10)

        print("Scrolling to load products...")
        for _ in tqdm(range(num_scrolls), desc="Loading"):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for new content to load

        print("Extracting product information...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product_card_elements = soup.select('div.product-card__vertical__wrapper')

        for card in tqdm(product_card_elements, desc="Scraping"):
            name_element = card.select_one('div[data-qe-id="body-meta-field-text"]')
            price_element = card.select_one('div[data-qe-id="body-price-text"]')
            image_element = card.select_one('img.product-card__vertical__media')
            link_element = card.find_parent('a', class_='sc-hqiKlG')

            name = name_element.text.strip() if name_element else None
            price_text = price_element.text.replace('NT$', '').replace(',', '').strip() if price_element else None
            price = float(price_text) if price_text else None
            image_url = image_element['src'] if image_element and 'src' in image_element.attrs else None
            product_url = POYA_BASE_URL + link_element['href'] if link_element and 'href' in link_element.attrs else None

            if name and price and image_url and product_url:
                products_data.append({
                    'name': name,
                    'price': price,
                    'image_url': image_url,
                    'url': product_url,
                    'retailer': 'Poya'
                })

    except Exception as e:
        print(f"Error fetching or scraping {category_url}: {e}")
    finally:
        driver.quit()
    return products_data

if __name__ == "__main__":
    start_time = time.time()
    print(f"Fetching and scraping product data from Poya main category: {ALL_PRODUCTS_CATEGORY_URL}")
    scraped_data_poya = scrape_poya_products_from_category(ALL_PRODUCTS_CATEGORY_URL)
    end_time = time.time()
    duration = end_time - start_time

    num_items = len(scraped_data_poya)
    print(f"\nScraped {num_items} products from Poya main category.")
    print(f"Time taken to scrape: {duration:.2f} seconds")

    if scraped_data_poya:
        # Save the scraped Poya data to a JSON file in the beauty4 directory
        beauty4_dir = 'beauty4'
        os.makedirs(beauty4_dir, exist_ok=True)
        output_file = os.path.join(beauty4_dir, 'poya_products.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(scraped_data_poya, f, ensure_ascii=False, indent=4)
        print(f"\nScraped Poya data saved to {output_file}")
    else:
        print("No Poya product data found.")
