from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import json
import argparse
from selenium.webdriver.chrome.options import Options

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def scrape_watsons_product_selenium(product_url):
    """
    Scrapes product details from a Watson's product page using Selenium in headless mode with User-Agent.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Enable headless mode
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(product_url)
        wait = WebDriverWait(driver, 10)
        name_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'product-name')))
        product_name = name_element.text.strip() if name_element else None
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        price_element = soup.find('span', class_='price')
        price = price_element.text.strip() if price_element else None
        image_element = soup.select_one('div[data-swiper-slide-index="0"] e2-media img')
        image_url = image_element['src'] if image_element and 'src' in image_element.attrs else None
        brand_element_h2 = soup.find('h2', class_='product-brand')
        brand_element_a = brand_element_h2.find('a') if brand_element_h2 else None
        brand = brand_element_a.text.strip() if brand_element_a else None
        driver.quit()
        return {
            'name': product_name,
            'price': price,
            'image_url': image_url,
            'brand': brand,
            'url': product_url,
            'retailer': 'Watsons'
        }
    except Exception as e:
        print(f"Error scraping {product_url} with Selenium: {e}")
        if 'driver' in locals():
            driver.quit()
        return None

def get_product_links_from_category(category_url):
    """
    Extracts product page links by waiting for at least one product link in headless mode with User-Agent.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Enable headless mode
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    product_links = []
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(category_url)
        wait = WebDriverWait(driver, 20)  # Increased timeout

        # Wait for at least one product link to be present within the product container
        product_links_elements = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.cx-product-container h2.productName a.gtmAlink'))
        )

        for link_element in product_links_elements:
            try:
                product_url = link_element.get_attribute('href')
                if product_url:
                    product_links.append(product_url)
            except Exception as e:
                print(f"Error extracting link from an element on {category_url}: {e}")

        driver.quit()

    except Exception as e:
        print(f"Error fetching {category_url}: {e}")
        if 'driver' in locals():
            driver.quit()
    return product_links

# List of category URLs (ensure it's up-to-date)
category_urls = [
   "https://www.watsons.com.tw/臉部保養/lc/1041",
    "https://www.watsons.com.tw/臉部保養/更多臉部保養/c/104110",
    "https://www.watsons.com.tw/臉部保養/超值組-旅行組/c/104107",
    "https://www.watsons.com.tw/臉部保養/保養/c/104103",
    "https://www.watsons.com.tw/臉部保養/化妝水-噴霧/c/10410301",
    "https://www.watsons.com.tw/臉部保養/乳液-乳霜/c/10410302",
    # "https://www.watsons.com.tw/臉部保養/精華液-霜/c/10410303",
    # "httpstps://www.watsons.com.tw/臉部保養/唇部保養/c/10410306",
    # "https://www.watsons.com.tw/臉部保養/眼部保養/c/10410305",
    # "https://www.watsons.com.tw/臉部保養/防曬-隔離/c/104105",
    # "https://www.watsons.com.tw/臉部保養/隔離乳-霜/c/10410501",
    # "https://www.watsons.com.tw/臉部保養/防曬乳-噴霧/c/10410502",
    # "https://www.watsons.com.tw/臉部保養/美容-護理/c/104106",
    # "https://www.watsons.com.tw/臉部保養/保濕-潤澤/c/10410603",
    # "https://www.watsons.com.tw/臉部保養/抗皺-拉提-緊緻/c/10410604",
    # "https://www.watsons.com.tw/臉部保養/抗痘-控油-毛孔調理/c/10410601",
    # "https://www.watsons.com.tw/臉部保養/舒敏-修護/c/10410605",
    # "https://www.watsons.com.tw/臉部保養/美白-淡斑/c/10410602",
    # "https://www.watsons.com.tw/臉部保養/面膜/c/104104",
    # "https://www.watsons.com.tw/臉部保養/高保濕-舒緩修護/c/10410402",
    # "https://www.watsons.com.tw/臉部保養/美白鎖水/c/10410401",
    # "https://www.watsons.com.tw/臉部保養/彈力活膚/c/10410403",
    # "https://www.watsons.com.tw/臉部保養/眼膜/c/10410404",
    # "https://www.watsons.com.tw/臉部保養/凍膜/c/10410405",
    # "https://www.watsons.com.tw/臉部保養/清潔/c/104101",
    # "https://www.watsons.com.tw/臉部保養/洗面乳/c/10410101",
    # "https://www.watsons.com.tw/臉部保養/臉部去角質/c/10410104",
    # "https://www.watsons.com.tw/臉部保養/洗顏慕斯/c/10410103",
    # "https://www.watsons.com.tw/臉部保養/洗面皂/c/10410102",
    # "https://www.watsons.com.tw/臉部保養/美容小家電/c/104108",
    # "https://www.watsons.com.tw/臉部保養/潔膚儀-洗臉機/c/10410801",
    # "https://www.watsons.com.tw/臉部保養/卸妝/c/104102",
    # "https://www.watsons.com.tw/臉部保養/卸妝油-乳-水/c/10410202",
    # "https://www.watsons.com.tw/臉部保養/卸妝棉/c/10410203",
    # "https://www.watsons.com.tw/臉部保養/眼唇卸粧/c/10410201",
    # "https://www.watsons.com.tw/臉部保養/專櫃/c/104109",
    # "https://www.watsons.com.tw/臉部保養/日韓品牌/c/10410904",
    # "https://www.watsons.com.tw/臉部保養/歐美品牌/c/10410903",
    # "https://www.watsons.com.tw/臉部保養/專櫃男性香水/c/10410906",
    # "https://www.watsons.com.tw/臉部保養/專櫃女性香水/c/10410905",
    # "https://www.watsons.com.tw/臉部保養/專櫃其他/c/10410902",
    # "https://www.watsons.com.tw/化妝品/lc/1044",
    # "https://www.watsons.com.tw/化妝品/精選特惠組/c/104404",
    # "https://www.watsons.com.tw/化妝品/美妝用品/c/104406",
    # "https://www.watsons.com.tw/化妝品/海綿-粉撲-粉盒/c/10440602",
    # "https://www.watsons.com.tw/化妝品/彩妝刷具/c/10440601",
    # "https://www.watsons.com.tw/化妝品/彩妝用具其他/c/10440603",
    # "https://www.watsons.com.tw/化妝品/香水-香氛/c/104408",
    # "https://www.watsons.com.tw/化妝品/女性香水/c/10440801",
    # "https://www.watsons.com.tw/化妝品/蠟燭-擴香-香精/c/10440805",
    # "https://www.watsons.com.tw/化妝品/香氛噴霧/c/10440804",
    # "https://www.watsons.com.tw/化妝品/中性香水/c/10440803",
    # "https://www.watsons.com.tw/化妝品/香水禮盒/c/10440806",
    # "https://www.watsons.com.tw/化妝品/男性香水/c/10440802",
    # "https://www.watsons.com.tw/化妝品/其他香水香氛/c/10440807",
    # "https://www.watsons.com.tw/化妝品/更多開架彩妝/c/104407",
    # "https://www.watsons.com.tw/化妝品/眼-眉彩妝/c/104402",
    # "https://www.watsons.com.tw/化妝品/眼影/c/10440204",
    # "https://www.watsons.com.tw/化妝品/眉筆-眉粉-染眉膏/c/10440203",
    # "https://www.watsons.com.tw/化妝品/睫毛膏/c/10440202",
    # "https://www.watsons.com.tw/化妝品/眼線筆-液-膠/c/10440201",
    # "https://www.watsons.com.tw/化妝品/唇部彩妝/c/104403",
    # "https://www.watsons.com.tw/化妝品/唇膏/c/10440301",
    # "https://www.watsons.com.tw/化妝品/唇蜜-唇釉/c/10440302",
    # "https://www.watsons.com.tw/化妝品/指甲彩繪/c/104405",
    # "https://www.watsons.com.tw/化妝品/指甲油-去光水/c/10440501",
    # "https://www.watsons.com.tw/化妝品/指甲貼/c/10440502",
    # "https://www.watsons.com.tw/化妝品/專業美甲/c/10440503",
    # "https://www.watsons.com.tw/化妝品/臉部彩妝/c/104401",
    # "https://www.watsons.com.tw/化妝品/隔離霜-飾底乳/c/10440101",
    # "https://www.watsons.com.tw/化妝品/粉餅-蜜粉/c/10440104",
    # "https://www.watsons.com.tw/化妝品/腮紅-修容-遮瑕膏/c/10440105",
    # "https://www.watsons.com.tw/化妝品/粉底液-霜/c/10440102",
    # "https://www.watsons.com.tw/化妝品/bb霜-cc霜-素顏霜/c/10440103",
    # "https://www.watsons.com.tw/醫美/lc/1043",
    # "https://www.watsons.com.tw/醫美/面膜-凍膜/c/104304",
    # "https://www.watsons.com.tw/醫美/特惠組-體驗組/c/104306",
    # "https://www.watsons.com.tw/醫美/更多醫美/c/104307",
    # "https://www.watsons.com.tw/醫美/抗敏-抗痘/c/104305",
    # "https://www.watsons.com.tw/醫美/醫美保養/c/104302",
    # "https://www.watsons.com.tw/醫美/乳液-乳霜/c/10430203",
    # "https://www.watsons.com.tw/醫美/化妝水-噴霧/c/10430201",
    # "https://www.watsons.com.tw/醫美/凝霜-凝膠/c/10430202",
    # "https://www.watsons.com.tw/醫美/精華液-精華霜/c/10430204",
    # "https://www.watsons.com.tw/醫美/眼部保養/c/10430205",
    # "https://www.watsons.com.tw/醫美/唇部保養/c/10430206",
    # "https://www.watsons.com.tw/醫美/防曬-隔離-bb霜/c/104303",
    # "https://www.watsons.com.tw/醫美/隔離乳-霜/c/10430301",
    # "https://www.watsons.com.tw/醫美/防曬乳-噴霧/c/10430302",
    # "https://www.watsons.com.tw/醫美/清潔-卸妝/c/104301",
    # "https://www.watsons.com.tw/醫美/洗面乳-慕斯/c/10430101",
    # "https://www.watsons.com.tw/醫美/卸妝乳-油-凝露/c/10430102",
    # "https://www.watsons.com.tw/醫美/臉部去角質/c/10430103",
    # "https://www.watsons.com.tw/專櫃/lc/1052",
    # "https://www.watsons.com.tw/專櫃/歐美品牌/c/105205",
    # "https://www.watsons.com.tw/專櫃/日韓品牌/c/105206",
    # "https://www.watsons.com.tw/專櫃/更多專櫃商品/c/105207",
    # "https://www.watsons.com.tw/專櫃/專櫃彩妝/c/105203",
    # "https://www.watsons.com.tw/專櫃/隔離-妝前/c/10520301",
    # "https://www.watsons.com.tw/專櫃/腮紅/c/10520306",
    # "https://www.watsons.com.tw/專櫃/唇彩/c/10520305",
    # "https://www.watsons.com.tw/專櫃/底妝/c/10520302",
    # "https://www.watsons.com.tw/專櫃/眼妝/c/10520304",
    # "https://www.watsons.com.tw/專櫃/其他彩妝/c/10520309",
    # "https://www.watsons.com.tw/專櫃/眉/c/10520303",
    # "https://www.watsons.com.tw/專櫃/化妝用具/c/10520307",
    # "https://www.watsons.com.tw/專櫃/指甲油-指甲保養/c/10520308",
    # "https://www.watsons.com.tw/專櫃/臉部保養/c/105201",
    # "https://www.watsons.com.tw/專櫃/霜/c/10520105",
    # "https://www.watsons.com.tw/專櫃/乳液/c/10520104",
    # "https://www.watsons.com.tw/專櫃/卸妝/c/10520107",
    # "https://www.watsons.com.tw/專櫃/精華液/c/10520102",
    # "https://www.watsons.com.tw/專櫃/化妝水/c/10520101",
    # "https://www.watsons.com.tw/專櫃/洗顏/c/10520108",
    # "https://www.watsons.com.tw/專櫃/眼霜/c/10520106",
    # "https://www.watsons.com.tw/專櫃/防曬/c/10520109",
    # "https://www.watsons.com.tw/專櫃/唇部保養/c/10520110",
    # "https://www.watsons.com.tw/專櫃/面膜/c/10520103",
    # "https://www.watsons.com.tw/專櫃/其他臉部保養/c/10520111",
    # "https://www.watsons.com.tw/專櫃/身體保養/c/105202",
    # "https://www.watsons.com.tw/專櫃/手足保養/c/10520204",
    # "https://www.watsons.com.tw/專櫃/身體乳/c/10520201",
    # "https://www.watsons.com.tw/專櫃/沐浴-髮類保養/c/10520203",
    # "https://www.watsons.com.tw/專櫃/美體霜-油/c/10520202",
    # "https://www.watsons.com.tw/專櫃/其他身體保養/c/10520205",
    # "https://www.watsons.com.tw/專櫃/超值組/c/105204",
    # "https://www.watsons.com.tw/專櫃/保養超值組/c/10520401",
    # "https://www.watsons.com.tw/專櫃/彩妝超值組/c/10520402",
    # "https://www.watsons.com.tw/專櫃/旅行組/c/10520403",
    # "https://www.watsons.com.tw/專櫃/禮盒/c/10520404",
    # "https://www.watsons.com.tw/專櫃/專櫃精品包包-皮夾/c/105208",
    # "https://www.watsons.com.tw/專櫃/斜背包/c/10520804",
    # "https://www.watsons.com.tw/專櫃/中-長夾/c/10520801",
    # "https://www.watsons.com.tw/專櫃/零錢包/c/10520808",
    # "https://www.watsons.com.tw/專櫃/短夾/c/10520802",
    # "https://www.watsons.com.tw/專櫃/其他/c/10520810",
    # "https://www.watsons.com.tw/專櫃/側肩包/c/10520803",
    # "https://www.watsons.com.tw/專櫃/化妝包/c/10520807",
    # "https://www.watsons.com.tw/專櫃/證件夾/c/10520809",
    # "https://www.watsons.com.tw/專櫃/後背包/c/10520805",
    # "https://www.watsons.com.tw/專櫃/托特包/c/10520806",
    # "https://www.watsons.com.tw/專櫃/專櫃精品服飾/c/105210",
    # "https://www.watsons.com.tw/專櫃/鞋款/c/10521006",
    # "https://www.watsons.com.tw/專櫃/外套/c/10521004",
    # "https://www.watsons.com.tw/專櫃/其他/c/10521007",
    # "https://www.watsons.com.tw/專櫃/裙子/c/10521003",
    # "https://www.watsons.com.tw/專櫃/風衣/c/10521005",
    # "https://www.watsons.com.tw/專櫃/褲裝/c/10521002",
    # "https://www.watsons.com.tw/專櫃/上衣/c/10521001",
    # "https://www.watsons.com.tw/專櫃/專櫃精品飾品配件/c/105209",
    # "https://www.watsons.com.tw/專櫃/耳環/c/10520901",
    # "https://www.watsons.com.tw/專櫃/項鍊/c/10520903",
    # "https://www.watsons.com.tw/專櫃/其他/c/10520907",
    # "https://www.watsons.com.tw/專櫃/手鍊/c/10520902",
    # "https://www.watsons.com.tw/專櫃/圍巾-絲巾/c/10520906",
    # "https://www.watsons.com.tw/專櫃/手錶/c/10520905",
    # "https://www.watsons.com.tw/專櫃/戒指/c/10520904",
    # "https://www.watsons.com.tw/保健/lc/1049",
    # "https://www.watsons.com.tw/保健/更多保健/c/104913",
    # "https://www.watsons.com.tw/保健/婦幼照護/c/104907",
    # "https://www.watsons.com.tw/保健/嬰幼童保健食品/c/10490702",
    # "https://www.watsons.com.tw/保健/副食品/c/10490703",
    # "https://www.watsons.com.tw/保健/婦幼照護其他/c/10490704",
    # "https://www.watsons.com.tw/保健/孕媽咪保健食品/c/10490701",
    # "https://www.watsons.com.tw/保健/男性保健/c/104908",
    # "https://www.watsons.com.tw/保健/營養補充品/c/104901",
    # "https://www.watsons.com.tw/保健/基礎營養其他/c/10490106",
    # "https://www.watsons.com.tw/保健/益生菌/c/10490103",
    # "https://www.watsons.com.tw/保健/魚油/c/10490102",
    # "https://www.watsons.com.tw/保健/鈣-葡萄糖胺/c/10490101",
    # "https://www.watsons.com.tw/保健/葉黃素/c/10490105",
    # "https://www.watsons.com.tw/保健/芝麻素/c/10490104",
    # "https://www.watsons.com.tw/保健/醫療器材-用品-乙類成藥/c/104909",
    # "https://www.watsons.com.tw/保健/醫療器材-用品-乙類成藥其他/c/10490905",
    # "https://www.watsons.com.tw/保健/體重計-體脂計/c/10490902",
    # "https://www.watsons.com.tw/保健/口罩-ok-繃/c/10490903",
    # "https://www.watsons.com.tw/保健/乙類成藥/c/10490906",
    # "https://www.watsons.com.tw/保健/隱形眼鏡藥水/c/10490904",
    # "https://www.watsons.com.tw/保健/保險套-按摩棒/c/10490901",
    # "https://www.watsons.com.tw/保健/孅體保健/c/104906",
    # "https://www.watsons.com.tw/保健/低卡代餐/c/10490604",
    # "https://www.watsons.com.tw/保健/酵素-乳酸-益生菌/c/10490601",
    # "https://www.watsons.com.tw/保健/膳食纖維-奇亞籽-機能水/c/10490602",
    # "https://www.watsons.com.tw/保健/油切阻斷/c/10490606",
    # "https://www.watsons.com.tw/保健/基礎代謝/c/10490605",
    # "https://www.watsons.com.tw/保健/紅豆-薏仁-檸檬水/c/10490603",
    # "https://www.watsons.com.tw/保健/運動休閒/c/104911",
    # "https://www.watsons.com.tw/保健/其他/c/10491107",
    # "https://www.watsons.com.tw/保健/運動補給品/c/10491101",
    # "https://www.watsons.com.tw/保健/健身器材/c/10491102",
    # "https://www.watsons.com.tw/保健/按摩器材/c/10491103",
    # "https://www.watsons.com.tw/保健/瑜珈用品/c/10491105",
    # "https://www.watsons.com.tw/保健/運動服飾/c/10491106",
    # "https://www.watsons.com.tw/保健/運動用品/c/10491104",
    # "https://www.watsons.com.tw/保健/女性保健/c/104905",
    # "https://www.watsons.com.tw/保健/女性保健其他/c/10490505",
    # "https://www.watsons.com.tw/保健/膠原蛋白-q10/c/10490501",
    # "https://www.watsons.com.tw/保健/珍珠粉-燕窩/c/10490502",
    # "https://www.watsons.com.tw/保健/大豆異黃酮/c/10490503",
    # "https://www.watsons.com.tw/保健/四物精華/c/10490504",
    # "https://www.watsons.com.tw/保健/維他命/c/104902",
    # "https://www.watsons.com.tw/保健/綜合維他命/c/10490201",
    # "https://www.watsons.com.tw/保健/維他命c/c/10490203",
    # "https://www.watsons.com.tw/保健/維他命d-維他命e/c/10490204",
    # "https://www.watsons.com.tw/保健/維他命b/c/10490202",
    # "https://www.watsons.com.tw/保健/維他命其他/c/10490205",
    # "https://www.watsons.com.tw/保健/保健飲品/c/104903",
    # "https://www.watsons.com.tw/保健/人蔘-靈芝-冬蟲夏草/c/10490302",
    # "https://www.watsons.com.tw/保健/雞精-滴雞精/c/10490301",
    # "https://www.watsons.com.tw/保健/銀髮保健/c/104904",
    # "https://www.watsons.com.tw/保健/魚油-心臟保健/c/10490402",
    # "https://www.watsons.com.tw/保健/銀髮保健其他/c/10490405",
    # "https://www.watsons.com.tw/保健/強骨補鈣/c/10490401",
    # "https://www.watsons.com.tw/保健/成人營養/c/10490403",
    # "https://www.watsons.com.tw/保健/成人紙尿褲/c/10490404",
    # "https://www.watsons.com.tw/保健/熟齡健康鍛鍊/c/104915",
    # "https://www.watsons.com.tw/保健/按摩用具-刮痧/c/10491506",
    # "https://www.watsons.com.tw/保健/護腰-護膝-護肘-護具/c/10491503",
    # "https://www.watsons.com.tw/保健/肌肉訓練小物/c/10491504",
    # "https://www.watsons.com.tw/保健/體脂計-體重計-計步器/c/10491502",
    # "https://www.watsons.com.tw/保健/踏步機-垂直律動機/c/10491501",
    # "https://www.watsons.com.tw/保健/智慧運動配件/c/10491507",
    # "https://www.watsons.com.tw/保健/冷熱敷墊-袋/c/10491505",
    # "https://www.watsons.com.tw/保健/銀髮輔助用品/c/104914",
    # "https://www.watsons.com.tw/保健/助行器/c/10491403",
    # "https://www.watsons.com.tw/保健/行動外出輔具/c/10491405",
    # "https://www.watsons.com.tw/保健/輪椅/c/10491401",
    # "https://www.watsons.com.tw/保健/拐杖-手杖-助行器/c/10491402",
    # "https://www.watsons.com.tw/保健/餐食生活輔具/c/10491406",
    # "https://www.watsons.com.tw/保健/居家生活輔具/c/10491407",
    # "https://www.watsons.com.tw/保健/衛浴安全輔具/c/10491404",
    # "https://www.watsons.com.tw/美體美髮/lc/1048",
    # "https://www.watsons.com.tw/美體美髮/止汗爽身噴霧/c/104807",
    # "https://www.watsons.com.tw/美體美髮/更多美體美髮/c/104810",
    # "https://www.watsons.com.tw/美體美髮/特惠組合-旅行組/c/104808",
    # "https://www.watsons.com.tw/美體美髮/專業美髮品/c/104811",
    # "https://www.watsons.com.tw/美體美髮/沙龍級造型品/c/10481103",
    # "https://www.watsons.com.tw/美體美髮/專櫃沙龍護理/c/10481102",
    # "https://www.watsons.com.tw/美體美髮/天然草本護理/c/10481104",
    # "https://www.watsons.com.tw/美體美髮/專櫃沙龍髮浴/c/10481101",
    # "https://www.watsons.com.tw/美體美髮/身體清潔/c/104801",
    # "https://www.watsons.com.tw/美體美髮/去角質/c/10480103",
    # "https://www.watsons.com.tw/美體美髮/香皂-洗手乳/c/10480101",
    # "https://www.watsons.com.tw/美體美髮/沐浴乳/c/10480102",
    # "https://www.watsons.com.tw/美體美髮/身體清潔其它/c/10480105",
    # "https://www.watsons.com.tw/美體美髮/沐浴用品/c/10480104",
    # "https://www.watsons.com.tw/美體美髮/染髮/c/104806",
    # "https://www.watsons.com.tw/美體美髮/染髮霜-染髮劑/c/10480601",
    # "https://www.watsons.com.tw/美體美髮/泡泡染/c/10480602",
    # "https://www.watsons.com.tw/美體美髮/洗髮-潤髮/c/104804",
    # "https://www.watsons.com.tw/美體美髮/強健髮根-頭皮護理/c/10480404",
    # "https://www.watsons.com.tw/美體美髮/油性-抗屑髮質/c/10480402",
    # "https://www.watsons.com.tw/美體美髮/洗髮-潤髮其它/c/10480405",
    # "https://www.watsons.com.tw/美體美髮/洗髮乳-潤髮乳/c/10480401",
    # "https://www.watsons.com.tw/美體美髮/護色-燙染受損/c/10480403",
    # "https://www.watsons.com.tw/美體美髮/香水-香氛/c/104809",
    # "https://www.watsons.com.tw/美體美髮/女性香水/c/10480901",
    # "https://www.watsons.com.tw/美體美髮/中性香水/c/10480903",
    # "https://www.watsons.com.tw/美體美髮/男性香水/c/10480902",
    # "https://www.watsons.com.tw/美體美髮/身體噴霧-體香劑/c/10480904",
    # "https://www.watsons.com.tw/美體美髮/香水香氛/c/10480905",
    # "https://www.watsons.com.tw/美體美髮/身體保養/c/104802",
    # "https://www.watsons.com.tw/美體美髮/身體乳液/c/10480202",
    # "https://www.watsons.com.tw/美體美髮/手部保養-足部保養/c/10480201",
    # "https://www.watsons.com.tw/美體美髮/身體防曬/c/10480203",
    # "https://www.watsons.com.tw/美體美髮/除毛用具/c/10480204",
    # "https://www.watsons.com.tw/美體美髮/纖體保養/c/10480205",
    # "https://www.watsons.com.tw/美體美髮/頭髮造型/c/104803",
    # "https://www.watsons.com.tw/美體美髮/美髮電器-梳子/c/10480303",
    # "https://www.watsons.com.tw/美體美髮/髮蠟-髮雕-髮膠/c/10480301",
    # "https://www.watsons.com.tw/美體美髮/髮蠟-髮膠/c/10480302",
    # "https://www.watsons.com.tw/美體美髮/護髮-特殊護理/c/104805",
    # "https://www.watsons.com.tw/美體美髮/護髮乳-髮膜/c/10480501",
    # "https://www.watsons.com.tw/美體美髮/免沖洗護髮/c/10480502",
    # "https://www.watsons.com.tw/日用品/lc/1045",
    # "https://www.watsons.com.tw/日用品/更多日用/c/104510",
    # "https://www.watsons.com.tw/日用品/家用百貨/c/104505",
    # "https://www.watsons.com.tw/日用品/餐廚用品/c/10450502",
    # "https://www.watsons.com.tw/日用品/小家電/c/10450501",
    # "https://www.watsons.com.tw/日用品/清潔家電/c/10450505",
    # "https://www.watsons.com.tw/日用品/生活家電/c/10450504",
    # "https://www.watsons.com.tw/日用品/廚房家電/c/10450503",
    # "https://www.watsons.com.tw/日用品/美容家電/c/10450506",
    # "https://www.watsons.com.tw/日用品/口腔保健/c/104507",
    # "https://www.watsons.com.tw/日用品/電動牙刷/c/10450705",
    # "https://www.watsons.com.tw/日用品/漱口水/c/10450702",
    # "https://www.watsons.com.tw/日用品/特殊護理-口腔噴霧/c/10450706",
    # "https://www.watsons.com.tw/日用品/牙膏/c/10450703",
    # "https://www.watsons.com.tw/日用品/牙刷/c/10450704",
    # "https://www.watsons.com.tw/日用品/牙線-牙間刷/c/10450701",
    # "https://www.watsons.com.tw/日用品/食品/c/104508",
    # "https://www.watsons.com.tw/日用品/零食飲料/c/10450802",
    # "https://www.watsons.com.tw/日用品/沖泡式飲品/c/10450801",
    # "https://www.watsons.com.tw/日用品/衛生紙/c/104502",
    # "https://www.watsons.com.tw/日用品/濕紙巾-濕式衛生紙/c/10450205",
    # "https://www.watsons.com.tw/日用品/抽取式/c/10450201",
    # "https://www.watsons.com.tw/日用品/平版-面紙-捲筒紙/c/10450203",
    # "https://www.watsons.com.tw/日用品/袖珍包-紙手帕/c/10450202",
    # "https://www.watsons.com.tw/日用品/廚房紙巾-紙抹布/c/10450204",
    # "https://www.watsons.com.tw/日用品/女性生理用品/c/104501",
    # "https://www.watsons.com.tw/日用品/日用衛生棉/c/10450101",
    # "https://www.watsons.com.tw/日用品/女性私密護理/c/10450105",
    # "https://www.watsons.com.tw/日用品/護墊/c/10450103",
    # "https://www.watsons.com.tw/日用品/夜用衛生棉/c/10450102",
    # "https://www.watsons.com.tw/日用品/衛生棉條/c/10450104",
    # "https://www.watsons.com.tw/日用品/嬰幼兒用品/c/104503",
    # "https://www.watsons.com.tw/日用品/濕紙巾/c/10450302",
    # "https://www.watsons.com.tw/日用品/嬰幼兒用品-食品/c/10450303",
    # "https://www.watsons.com.tw/日用品/玩具-書籍/c/10450304",
    # "https://www.watsons.com.tw/日用品/尿布/c/10450301",
    # "https://www.watsons.com.tw/日用品/媽咪用品/c/10450305",
    # "https://www.watsons.com.tw/日用品/流行生活用品/c/104509",
    # "https://www.watsons.com.tw/日用品/女性內著-襪/c/10450901",
    # "https://www.watsons.com.tw/日用品/毛巾-浴巾/c/10450903",
    # "https://www.watsons.com.tw/日用品/生活雜貨其他/c/10450905",
    # "https://www.watsons.com.tw/日用品/男性內著-襪/c/10450902",
    # "https://www.watsons.com.tw/日用品/飾品/c/10450907",
    # "https://www.watsons.com.tw/日用品/旅行用品/c/10450908",
    # "https://www.watsons.com.tw/日用品/寢具/c/10450904",
    # "https://www.watsons.com.tw/日用品/手錶/c/10450906",
    # "https://www.watsons.com.tw/日用品/家庭清潔/c/104504",
    # "https://www.watsons.com.tw/日用品/衣物清潔/c/10450401",
    # "https://www.watsons.com.tw/日用品/家庭清潔其他/c/10450404",
    # "https://www.watsons.com.tw/日用品/清潔劑-用品/c/10450402",
    # "https://www.watsons.com.tw/日用品/芳香劑-除濕劑/c/10450403",
    # "https://www.watsons.com.tw/日用品/寵物食品/c/104511",
    # "https://www.watsons.com.tw/日用品/貓罐頭-餐包-零食/c/10451104",
    # "https://www.watsons.com.tw/日用品/狗飼料/c/10451101",
    # "https://www.watsons.com.tw/日用品/狗罐頭-餐包-零食/c/10451102",
    # "https://www.watsons.com.tw/日用品/寵物保健用品/c/10451105",
    # "https://www.watsons.com.tw/日用品/貓飼料/c/10451103",
    # "https://www.watsons.com.tw/日用品/寵物用品/c/104512",
    # "https://www.watsons.com.tw/日用品/寵物清潔美容/c/10451204",
    # "https://www.watsons.com.tw/日用品/貓砂-砂盆/c/10451201",
    # "https://www.watsons.com.tw/日用品/寵物衛生用品/c/10451202",
    # "https://www.watsons.com.tw/日用品/寵物環境清潔/c/10451203",
    # "https://www.watsons.com.tw/日用品/寵物配件-居家用品/c/10451206",
    # "https://www.watsons.com.tw/日用品/其他寵物用品/c/10451208",
    # "https://www.watsons.com.tw/日用品/寵物推車-外出用品/c/10451207",
    # "https://www.watsons.com.tw/日用品/寵物玩具-抓板/c/10451205",
    # "https://www.watsons.com.tw/日用品/運動休閒/c/104506",
    # "https://www.watsons.com.tw/日用品/其他/c/10450606",
    # "https://www.watsons.com.tw/日用品/運動用品/c/10450603",
    # "https://www.watsons.com.tw/日用品/按摩器材/c/10450602",
    # "https://www.watsons.com.tw/日用品/體脂計/c/10450605",
    # "https://www.watsons.com.tw/日用品/健身器材/c/10450601",
    # "https://www.watsons.com.tw/日用品/瑜珈用品/c/10450604",
    # "https://www.watsons.com.tw/男性用品/lc/1042",
    # "https://www.watsons.com.tw/男性用品/型男內著-襪-棉織品/c/104206",
    # "https://www.watsons.com.tw/男性用品/更多型男/c/104208",
    # "https://www.watsons.com.tw/男性用品/男士臉部保養/c/104201",
    # "https://www.watsons.com.tw/男性用品/臉部其他/c/10420104",
    # "https://www.watsons.com.tw/男性用品/刮鬍水-刮鬍刀/c/10420103",
    # "https://www.watsons.com.tw/男性用品/男士肌膚保養/c/10420102",
    # "https://www.watsons.com.tw/男性用品/男士洗面乳/c/10420101",
    # "https://www.watsons.com.tw/男性用品/男士身體保養/c/104202",
    # "https://www.watsons.com.tw/男性用品/男士沐浴乳-沐浴露/c/10420202",
    # "https://www.watsons.com.tw/男性用品/男士止汗爽身噴霧/c/10420203",
    # "https://www.watsons.com.tw/男性用品/男士肌膚保養/c/10420201",
    # "https://www.watsons.com.tw/男性用品/性福計畫/c/104207",
    # "https://www.watsons.com.tw/男性用品/情趣用品/c/10420703",
    # "https://www.watsons.com.tw/男性用品/保險套/c/10420702",
    # "https://www.watsons.com.tw/男性用品/潤滑劑/c/10420701",
    # "https://www.watsons.com.tw/男性用品/髮類/c/104203",
    # "https://www.watsons.com.tw/男性用品/男士洗髮精-潤髮/c/10420302",
    # "https://www.watsons.com.tw/男性用品/男士造型髮蠟-染髮/c/10420301",
    # "https://www.watsons.com.tw/男性用品/男性保健食品/c/104204",
    # "https://www.watsons.com.tw/男性用品/蜆精-瑪卡-鋅/c/10420402",
    # "https://www.watsons.com.tw/男性用品/型男保健其他/c/10420403",
    # "https://www.watsons.com.tw/男性用品/維他命b/c/10420401",
    # "https://www.watsons.com.tw/男性用品/美容家電/c/104205",
    # "https://www.watsons.com.tw/男性用品/電動刮鬍刀-刮鬍刀片/c/10420501",
    # "https://www.watsons.com.tw/運動休閒/lc/1051",
    # "https://www.watsons.com.tw/運動休閒/運動服飾/c/105105",
    # "https://www.watsons.com.tw/運動休閒/運動服飾其他/c/10510506",
    # "https://www.watsons.com.tw/運動休閒/運動鞋/c/10510505",
    # "https://www.watsons.com.tw/運動休閒/壓力-運動褲/c/10510502",
    # "https://www.watsons.com.tw/運動休閒/運動內衣/c/10510501",
    # "https://www.watsons.com.tw/運動休閒/運動襪/c/10510504",
    # "https://www.watsons.com.tw/運動休閒/運動上衣-外套/c/10510503",
    # "https://www.watsons.com.tw/運動休閒/按摩器材/c/105102",
    # "https://www.watsons.com.tw/運動休閒/熱敷墊-袋/c/10510207",
    # "https://www.watsons.com.tw/運動休閒/肩頸按摩-眼部按摩/c/10510203",
    # "https://www.watsons.com.tw/運動休閒/按摩椅/c/10510201",
    # "https://www.watsons.com.tw/運動休閒/美體曲線-按摩小物/c/10510206",
    # "https://www.watsons.com.tw/運動休閒/按摩枕-椅墊/c/10510202",
    # "https://www.watsons.com.tw/運動休閒/按摩器材其他/c/10510208",
    # "https://www.watsons.com.tw/運動休閒/足部按摩-美腿機-腳底按摩機/c/10510205",
    # "https://www.watsons.com.tw/運動休閒/泡腳機/c/10510204",
    # "https://www.watsons.com.tw/運動休閒/健身器材/c/105101",
    # "https://www.watsons.com.tw/運動休閒/健身器材其他/c/10510109",
    # "https://www.watsons.com.tw/運動休閒/健腹器-仰臥起坐-倒立機-重量訓練-划船機/c/10510103",
    # "https://www.watsons.com.tw/運動休閒/健身車-飛輪車-橢圓機/c/10510101",
    # "https://www.watsons.com.tw/運動休閒/啞鈴-槓片-壺鈴/c/10510104",
    # "https://www.watsons.com.tw/運動休閒/體脂計-體重計/c/10510105",
    # "https://www.watsons.com.tw/運動休閒/跑步機-健走機/c/10510102",
    # "https://www.watsons.com.tw/運動休閒/搖擺機-跳舞機-美臀機/c/10510108",
    # "https://www.watsons.com.tw/運動休閒/踏步機-美腿機-計步器/c/10510106",
    # "https://www.watsons.com.tw/運動休閒/肩臂雕塑-美胸/c/10510107",
    # "https://www.watsons.com.tw/運動休閒/瑜珈-運動配件/c/105103",
    # "https://www.watsons.com.tw/運動休閒/瑜珈-運動配件其他/c/10510306",
    # "https://www.watsons.com.tw/運動休閒/瑜珈墊-鋪巾/c/10510301",
    # "https://www.watsons.com.tw/運動休閒/瑜珈球-瑜珈磚/c/10510302",
    # "https://www.watsons.com.tw/運動休閒/護腕-護具/c/10510305",
    # "https://www.watsons.com.tw/運動休閒/瑜珈滾輪/c/10510303",
    # "https://www.watsons.com.tw/運動休閒/拉筋-伸展帶-彈力帶/c/10510304",
    # "https://www.watsons.com.tw/運動休閒/個人護理/c/105107",
    # "https://www.watsons.com.tw/運動休閒/止汗爽身/c/10510701",
    # "https://www.watsons.com.tw/運動休閒/助曬-曬後保養/c/10510702",
    # "https://www.watsons.com.tw/運動休閒/穿戴裝置/c/105106",
    # "https://www.watsons.com.tw/運動休閒/運動耳機-攝影機/c/10510604",
    # "https://www.watsons.com.tw/運動休閒/運動手環/c/10510602",
    # "https://www.watsons.com.tw/運動休閒/穿戴裝置其他/c/10510605",
    # "https://www.watsons.com.tw/運動休閒/gps運動手錶/c/10510601",
    # "https://www.watsons.com.tw/運動休閒/心率/c/10510603",
    # "https://www.watsons.com.tw/運動休閒/運動補給品/c/105104",
    # "https://www.watsons.com.tw/運動休閒/bcaa支鏈胺基酸/c/10510403",
    # "https://www.watsons.com.tw/運動休閒/乳清蛋白/c/10510401",
    # "https://www.watsons.com.tw/運動休閒/運動補給品其他/c/10510404",
    # "https://www.watsons.com.tw/運動休閒/cla紅花籽油/c/10510402",
    # "https://www.watsons.com.tw/屈臣氏獨家/lc/1046",
    # "https://www.watsons.com.tw/屈臣氏獨家/更多自有品牌/c/104606",
    # "https://www.watsons.com.tw/屈臣氏獨家/保健/c/104605",
    # "https://www.watsons.com.tw/屈臣氏獨家/保健食品/c/10460502",
    # "https://www.watsons.com.tw/屈臣氏獨家/醫療器材/c/10460503",
    # "https://www.watsons.com.tw/屈臣氏獨家/維他命/c/10460501",
    # "https://www.watsons.com.tw/屈臣氏獨家/美髮造型/c/104603",
    # "https://www.watsons.com.tw/屈臣氏獨家/洗-潤-護髮/c/10460301",
    # "https://www.watsons.com.tw/屈臣氏獨家/染髮/c/10460302",
    # "https://www.watsons.com.tw/屈臣氏獨家/美髮電器-造型/c/10460303",
    # "https://www.watsons.com.tw/屈臣氏獨家/身體保養/c/104602",
    # "https://www.watsons.com.tw/屈臣氏獨家/身體保養/c/10460201",
    # "https://www.watsons.com.tw/屈臣氏獨家/手部保養-足部保養/c/10460202",
    # "https://www.watsons.com.tw/屈臣氏獨家/臉部保養/c/104601",
    # "https://www.watsons.com.tw/屈臣氏獨家/護唇膏/c/10460105",
    # "https://www.watsons.com.tw/屈臣氏獨家/面膜/c/10460107",
    # "https://www.watsons.com.tw/屈臣氏獨家/乳液/c/10460104",
    # "https://www.watsons.com.tw/屈臣氏獨家/化妝水/c/10460103",
    # "https://www.watsons.com.tw/屈臣氏獨家/化妝用品/c/10460108",
    # "https://www.watsons.com.tw/屈臣氏獨家/清潔-卸粧-去角質/c/10460101",
    # "https://www.watsons.com.tw/屈臣氏獨家/精華液/c/10460106",
    # "https://www.watsons.com.tw/屈臣氏獨家/吸油面紙/c/10460102",
    # "https://www.watsons.com.tw/屈臣氏獨家/日常用品/c/104604",
    # "https://www.watsons.com.tw/屈臣氏獨家/衛生紙-棉製品/c/10460404",
    # "https://www.watsons.com.tw/屈臣氏獨家/口腔保健/c/10460402",
    # "https://www.watsons.com.tw/屈臣氏獨家/沐浴清潔/c/10460401",
    # "https://www.watsons.com.tw/屈臣氏獨家/嬰兒用品/c/10460407",
    # "https://www.watsons.com.tw/屈臣氏獨家/生活雜貨/c/10460408",
    # "https://www.watsons.com.tw/屈臣氏獨家/居家清潔用品/c/10460406",
    # "https://www.watsons.com.tw/屈臣氏獨家/男性專區/c/10460405",
    # "https://www.watsons.com.tw/屈臣氏獨家/沐浴用品/c/10460403",
    # "https://www.watsons.com.tw/箱購專區/lc/1047",
    # "https://www.watsons.com.tw/箱購專區/更多箱購用品/c/104708",
    # "https://www.watsons.com.tw/箱購專區/衛生紙/c/104704",
    # "https://www.watsons.com.tw/箱購專區/廚房紙巾/c/10470404",
    # "https://www.watsons.com.tw/箱購專區/抽取衛生紙/c/10470401",
    # "https://www.watsons.com.tw/箱購專區/濕式衛生紙/c/10470403",
    # "https://www.watsons.com.tw/箱購專區/平版衛生紙/c/10470402",
    # "https://www.watsons.com.tw/箱購專區/保健食品/c/104701",
    # "https://www.watsons.com.tw/箱購專區/成人營養品/c/10470101",
    # "https://www.watsons.com.tw/箱購專區/其他保健食品/c/10470103",
    # "https://www.watsons.com.tw/箱購專區/保健飲品/c/10470102",
    # "https://www.watsons.com.tw/箱購專區/食品飲料/c/104707",
    # "https://www.watsons.com.tw/箱購專區/蒸餾水/c/10470701",
    # "https://www.watsons.com.tw/箱購專區/衛生棉/c/104705",
    # "https://www.watsons.com.tw/箱購專區/護墊/c/10470501",
    # "https://www.watsons.com.tw/箱購專區/日用衛生棉/c/10470502",
    # "https://www.watsons.com.tw/箱購專區/夜用衛生棉/c/10470503",
    # "https://www.watsons.com.tw/箱購專區/衛生棉條/c/10470504",
    # "https://www.watsons.com.tw/箱購專區/醫療器材-用品/c/104709",
    # "https://www.watsons.com.tw/箱購專區/隱形眼鏡藥水/c/10470901",
    # "https://www.watsons.com.tw/箱購專區/家庭清潔/c/104706",
    # "https://www.watsons.com.tw/箱購專區/衣物清潔劑/c/10470601",
    # "https://www.watsons.com.tw/箱購專區/口罩/c/10470602",
    # "https://www.watsons.com.tw/箱購專區/尿布-溼巾/c/104703",
    # "https://www.watsons.com.tw/箱購專區/嬰兒尿布/c/10470301",
    # "https://www.watsons.com.tw/箱購專區/溼巾/c/10470303",
    # "https://www.watsons.com.tw/箱購專區/成人紙尿褲/c/10470302",
    # "https://www.watsons.com.tw/箱購專區/護膚保養/c/104702",
    "https://www.watsons.com.tw/箱購專區/面膜/c/10470201",
    "https://www.watsons.com.tw/箱購專區/其他護膚保養/c/10470202"
]

all_product_links = []
scraped_data = []

for url in category_urls:
    print(f"Fetching product links from: {url}")
    links = get_product_links_from_category(url)
    if links:
        print(f"Found {len(links)} product links on {url}")
        all_product_links.extend(links)
    else:
        print(f"Could not find product links on {url}")

print("\nTotal product links found:", len(all_product_links))

# Now, scrape details for each product link and store in the list
if all_product_links:
    print("\n--- Scraping Product Details ---")
    for product_url in all_product_links:
        print(f"Scraping details for: {product_url}")
        product_data = scrape_watsons_product_selenium(product_url)
        if product_data:
            scraped_data.append(product_data)
        else:
            print(f"Failed to scrape details for: {product_url}")
else:
    print("No product links found. Skipping product detail scraping.")

# Save the scraped data to a JSON file
if scraped_data:
    with open('./watsons_products.json', 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, ensure_ascii=False, indent=4)
    print("\nScraped data saved to watsons_products.json")
else:
    print("\nNo product data to save.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Watsons product data.")
    parser.add_argument("-o", "--output", default="watsons_products.json", help="Path to the output JSON file.")
    args = parser.parse_args()

    # ... (your scraping logic here, storing data in scraped_data list)

    if scraped_data:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=4)
        print(f"\nScraped data saved to {args.output}")
    else:
        print("\nNo product data to save.")