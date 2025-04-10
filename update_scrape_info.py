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

def main(watsons_success_str, poya_success_str, cosmed_success_str):
    info_file = './beauty4/scrape_info.json'
    now_taiwan = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d')

    watsons_success = watsons_success_str == 'true'
    poya_success = poya_success_str == 'true'
    cosmed_success = cosmed_success_str == 'true'

    scrape_info = {}
    try:
        with open(info_file, 'r') as f:
            scrape_info = json.load(f)
    except FileNotFoundError:
        scrape_info = {}

    if watsons_success:
        scrape_info['watsons_last_scrape'] = now_taiwan
        scrape_info['watsons_item_count'] = get_product_count('./beauty4/watsons_products.json')
    elif 'watsons_last_scrape' not in scrape_info:
        scrape_info['watsons_last_scrape'] = None
        scrape_info['watsons_item_count'] = 0

    if poya_success:
        scrape_info['poya_last_scrape'] = now_taiwan
        scrape_info['poya_item_count'] = get_product_count('./beauty4/poya_products.json')
    elif 'poya_last_scrape' not in scrape_info:
        scrape_info['poya_last_scrape'] = None
        scrape_info['poya_item_count'] = 0

    if cosmed_success:
        scrape_info['cosmed_last_scrape'] = now_taiwan
        scrape_info['cosmed_item_count'] = get_product_count('./beauty4/cosmed_products.json')
    elif 'cosmed_last_scrape' not in scrape_info:
        scrape_info['cosmed_last_scrape'] = None
        scrape_info['cosmed_item_count'] = 0

    with open(info_file, 'w') as f:
        json.dump(scrape_info, f, indent=2)

if __name__ == "__main__":
    watsons_success = sys.argv[1] if len(sys.argv) > 1 else 'false'
    poya_success = sys.argv[2] if len(sys.argv) > 2 else 'false'
    cosmed_success = sys.argv[3] if len(sys.argv) > 3 else 'false'
    main(watsons_success, poya_success, cosmed_success)