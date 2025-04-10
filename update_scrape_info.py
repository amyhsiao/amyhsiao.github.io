import json
import datetime
import os
import sys

def get_product_count(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return len(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0

def main(scraper_name, watsons_success_str, poya_success_str, cosmed_success_str):
    info_file = './beauty4/scrape_info.json'
    now_taiwan = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d')

    watsons_success = watsons_success_str.lower() == 'true'
    poya_success = poya_success_str.lower() == 'true'
    cosmed_success = cosmed_success_str.lower() == 'true'

    scrape_info = {}
    try:
        with open(info_file, 'r') as f:
            scrape_info = json.load(f)
    except FileNotFoundError:
        scrape_info = {}
    except json.JSONDecodeError:
        scrape_info = {}

    if scraper_name == 'watsons' and watsons_success:
        scrape_info['watsons_last_scrape'] = now_taiwan
        scrape_info['watsons_item_count'] = get_product_count('./beauty4/watsons_products.json')
    elif scraper_name == 'poya' and poya_success:
        scrape_info['poya_last_scrape'] = now_taiwan
        scrape_info['poya_item_count'] = get_product_count('./beauty4/poya_products.json')
    elif scraper_name == 'cosmed' and cosmed_success:
        scrape_info['cosmed_last_scrape'] = now_taiwan
        scrape_info['cosmed_item_count'] = get_product_count('./beauty4/cosmed_products.json')

    with open(info_file, 'w') as f:
        json.dump(scrape_info, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        scraper_name = sys.argv[1]
        watsons_success = sys.argv[2] if len(sys.argv) > 2 else 'false'
        poya_success = sys.argv[3] if len(sys.argv) > 3 else 'false'
        cosmed_success = sys.argv[4] if len(sys.argv) > 4 else 'false'
        main(scraper_name, watsons_success, poya_success, cosmed_success)
    else:
        print("Error: Scraper name not provided as argument.")
        sys.exit(1)