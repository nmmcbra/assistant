import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import parsel
from prettytable import PrettyTable
import json
import time

def crawl_amazon(keyword, max_pages=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
        "Referer": "https://www.amazon.com/"
    }
    goods = []
    for page in range(1, max_pages + 1):
        url = f"https://www.amazon.com/s?k={quote(keyword)}&page={page}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
        except Exception:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", {"data-component-type": "s-search-result"})
        for item in items:
            h2 = item.find("h2")
            if not h2:
                continue
            a_tag = h2.find("a")
            if not a_tag:
                continue
            name = a_tag.get_text().strip()
            rel_url = a_tag.get("href")
            if not rel_url:
                continue
            link = "https://www.amazon.com" + rel_url
            price = None
            whole = item.find("span", class_="a-price-whole")
            fraction = item.find("span", class_="a-price-fraction")
            if whole and fraction:
                price = whole.get_text().strip() + fraction.get_text().strip()
            else:
                offscreen = item.find("span", class_="a-offscreen")
                if offscreen:
                    price = offscreen.get_text().strip()
            if name and price:
                goods.append({
                    "site": "Amazon",
                    "good_text": name,
                    "price": price,
                    "url": link
                })
        time.sleep(1)
    return goods

def crawl_jd(keyword, max_pages=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0"
    }
    goods = []
    for page in range(1, max_pages + 1):
        jd_page = page * 2 - 1
        url = f"https://search.jd.com/Search?keyword={quote(keyword)}&enc=utf-8&page={jd_page}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
        except Exception:
            continue
        selector = parsel.Selector(response.text)
        items = selector.xpath('//div[@class="gl-i-wrap"]')
        for item in items:
            name = item.xpath('string(.//div[@class="p-name p-name-type-2"]/a/em)').get(default="").strip().replace("\n", "")
            if not name or "拍拍" in name or "爱心东东" in name:
                continue
            raw_url = item.xpath('.//div[@class="p-name p-name-type-2"]/a/@href').get(default="")
            link = "https:" + raw_url if raw_url and not raw_url.startswith("http") else raw_url
            price = item.xpath('string(.//div[@class="p-price"])').get(default="").strip()
            if name and price and link:
                goods.append({
                    "site": "JD",
                    "good_text": name,
                    "price": price,
                    "url": link
                })
        time.sleep(1)
    return goods

def crawler(keyword, max_pages=3):
    amazon_goods = crawl_amazon(keyword, max_pages)
    jd_goods = crawl_jd(keyword, max_pages)
    goods_data = amazon_goods + jd_goods

    table = PrettyTable(["网站", "商品名称", "价格", "链接"])
    for item in goods_data:
        table.add_row([item["site"], item["good_text"], item["price"], item["url"]])
    print(table)
    return goods_data

if __name__ == "__main__":
    keyword = input("请输入要搜索的关键词：")
    data = crawler(keyword, max_pages=3)
    with open("goods_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
