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

def main(scraper_name, was_successful_str, _, __): # Expecting only the relevant success
    info_file = './beauty4/scrape_info.json'
    now_taiwan = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d')
    was_successful = was_successful_str.lower() == 'true'

    scrape_info = {}
    try:
        with open(info_file, 'r') as f:
            scrape_info = json.load(f)
    except FileNotFoundError:
        scrape_info = {}
    except json.JSONDecodeError:
        scrape_info = {}

    if was_successful:
        scrape_info[f'{scraper_name}_last_scrape'] = now_taiwan
        scrape_info[f'{scraper_name}_item_count'] = get_product_count(f'./beauty4/{scraper_name}_products.json')

    with open(info_file, 'w') as f:
        json.dump(scrape_info, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        scraper_name = sys.argv[1]
        was_successful = sys.argv[2] if len(sys.argv) > 2 else 'false'
        main(scraper_name, was_successful, '', '') # We only care about the current scraper's success
    else:
        print("Error: Scraper name and success status not provided.")
        sys.exit(1)