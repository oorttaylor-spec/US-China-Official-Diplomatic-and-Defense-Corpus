# ==============================================================================
# Script Name
#
# Description (English)
# ------------------------------------------------------------------------------
# This script scrapes news items from the White House website:
#   https://www.whitehouse.gov/news/
#
# It collects article metadata from index pages (publish time, type, title, URL),
# then visits each article page to extract the full content (including <p>, <h3>,
# and nested <ul>/<li> lists with indentation and numbering).
#
# Workflow:
#   1) Load progress from CSV (resume support by source_url)
#   2) Collect article info from index pages (TOTAL_PAGES)
#   3) De-duplicate and filter out processed URLs
#   4) Crawl new article pages and append results to:
#        - CSV  (UTF-8 with BOM)  [progress/resume file]
#        - JSONL (UTF-8, one JSON object per line)
#   5) Convert CSV to Excel (.xlsx)
#
# Resume / checkpoint logic:
#   - The script uses the CSV file as the progress record.
#   - If a source_url already exists in the CSV, it will be skipped on rerun.
#
# Output schema (per record)
# ------------------------------------------------------------------------------
#   publish_time, type, title, content, source_url
#
# Dependencies
# ------------------------------------------------------------------------------
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3
#
# ------------------------------------------------------------------------------
# 中文说明
# ------------------------------------------------------------------------------
# 本脚本用于爬取白宫网站 News 栏目：
#   https://www.whitehouse.gov/news/
#
# 从索引页收集文章信息（发布时间、类型、标题、链接），并进入详情页提取正文
# （包括 p、h3 以及 ul/li 嵌套列表，带缩进和编号格式化）。
#
# 流程：
#   1）从 CSV 读取进度（按 source_url 断点续爬）
#   2）从多个索引页（TOTAL_PAGES）收集文章信息
#   3）去重并过滤已爬取链接
#   4）爬取新文章详情并追加写入：
#        - CSV（UTF-8 带 BOM）【同时作为断点续爬进度文件】
#        - JSONL（UTF-8，每行一条 JSON 记录）
#   5）将 CSV 转换为 Excel（.xlsx）
#
# 断点续爬逻辑：
#   - 仍然以 CSV 文件作为进度记录
#   - 若 CSV 中已有某个 source_url，则下次运行会跳过该链接
#
# 依赖安装：
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3
# ==============================================================================

import requests
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
from tqdm import tqdm
import time
import os
import csv
import json
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ARCHIVE_BASE_DOMAIN = "https://www.whitehouse.gov"
NEWS_BASE_URL = ARCHIVE_BASE_DOMAIN + "/news/"
TOTAL_PAGES = 150

CSV_FILENAME = "trump_whitehouse_news_data.csv"
JSONL_FILENAME = "trump_whitehouse_news_data.jsonl"
EXCEL_FILENAME = "trump_whitehouse_news_data.xlsx"

# Output header (CSV columns)
FIELDNAMES = ["publish_time", "type", "title", "content", "source_url"]


# ==============================================================================
# SHARED UTILITIES
# ==============================================================================

def create_retriable_session():
    """Create a requests Session with retry support (unchanged logic)."""
    session = requests.Session()
    retries = Retry(
        total=5,  # Retry up to 5 times total
        backoff_factor=1,  # 1s, 2s, 4s, 8s, 16s ...
        status_forcelist=[500, 502, 503, 504, 403, 404],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


global_session = create_retriable_session()


# ==============================================================================
# CORE SCRAPING FUNCTIONS
# ==============================================================================

def get_brief_info_from_index(index_url):
    """
    From an index page, extract brief article info: title, type, publish time, URL.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,"
                "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
            ),
        }
        response = global_session.get(index_url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        articles_info = []
        news_items = soup.select("ul.wp-block-post-template li.wp-block-post")

        for item in news_items:
            title_tag = item.select_one("h2.wp-block-post-title a")
            time_tag = item.select_one("div.wp-block-post-date time")
            type_tags = item.select("div.taxonomy-category.wp-block-post-terms a")

            if title_tag and title_tag.has_attr("href") and time_tag:
                full_url = urljoin(ARCHIVE_BASE_DOMAIN, title_tag["href"])
                title = title_tag.get_text(strip=True).replace("\xa0", " ")
                publish_time = time_tag.get("datetime", time_tag.get_text(strip=True))

                article_type = ", ".join([t.get_text(strip=True) for t in type_tags]) if type_tags else "Unknown Type"

                articles_info.append({
                    "url": full_url,
                    "title": title,
                    "publish_time": publish_time,
                    "type": article_type,
                })
        return articles_info
    except requests.exceptions.RequestException as e:
        print(f"\n[SEVERE] Index page failed after retries: {index_url}: {e}")
        return []


def extract_list_items_with_indent(ul_element, indent_level=0, prefix_char="-"):
    """
    Recursively extract <li> items (including nested <ul>) and add indentation.
    """
    list_output = []
    current_indent = "    " * indent_level  # 4 spaces per indent level

    # Only iterate direct children <li> of the current <ul> to avoid duplicates
    for li_tag in ul_element.find_all("li", recursive=False):
        li_text = li_tag.get_text(strip=True).replace("\xa0", " ")
        if li_text:
            list_output.append(f"{current_indent}{prefix_char} {li_text}")

        # Handle nested lists
        nested_ul = li_tag.find("ul", recursive=False)
        if nested_ul:
            list_output.extend(extract_list_items_with_indent(nested_ul, indent_level + 1, prefix_char))

    return list_output


def get_article_full_content(article_url):
    """
    From an article detail page, extract full content from <p>, <h3>, and <ul>/<li>
    elements. The output is formatted with numbering and indentation.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,"
                "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
            ),
        }
        response = global_session.get(article_url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        content_div = soup.select_one("div.entry-content.wp-block-post-content")
        if not content_div:
            return "正文内容未找到"

        formatted_content_parts = []
        paragraph_count = 0

        # Iterate all direct children of content_div in order
        for element in content_div.children:
            # Skip blank text nodes
            if isinstance(element, str) and not element.strip():
                continue

            # Only handle tags of interest: p, h3, ul
            if element.name == "p":
                text = element.get_text(strip=True).replace("\xa0", " ")
                if text:
                    paragraph_count += 1
                    formatted_content_parts.append(f"{paragraph_count}. {text}")
            elif element.name == "h3":
                text = element.get_text(strip=True).replace("\xa0", " ")
                if text:
                    paragraph_count += 1
                    formatted_content_parts.append(f"\n{paragraph_count}. --- {text} ---")
            elif element.name == "ul":
                list_output = extract_list_items_with_indent(element)
                if list_output:
                    paragraph_count += 1
                    formatted_content_parts.append(f"\n{paragraph_count}. " + "\n".join(list_output))
            # Ignore other tags (<div>, <figure>, <script>, <style>, etc.)

        if not formatted_content_parts:
            # Fallback: extract all visible text if nothing was captured
            full_text_fallback = content_div.get_text(separator="\n\n", strip=True).replace("\xa0", " ")
            if full_text_fallback:
                return f"1. {full_text_fallback}"
            return "正文内容未找到"

        return "\n\n".join(formatted_content_parts).strip()

    except requests.exceptions.RequestException as e:
        print(f"\n[SEVERE] Detail page failed after retries: {article_url}: {e}")
        return "爬取正文失败"


def write_jsonl_line(fp, record):
    """Write one JSON object as a JSONL line (UTF-8, keep non-ASCII characters)."""
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


# ==============================================================================
# MAIN EXECUTION LOGIC
# ==============================================================================
def main():
    """Main entry: run scraping and save results."""
    print("--- Starting Trump White House News Scraper ---")
    total_start_time = time.time()

    processed_urls = set()
    if os.path.exists(CSV_FILENAME):
        try:
            if os.path.getsize(CSV_FILENAME) > 0:
                with open(CSV_FILENAME, "r", newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    if not all(field in reader.fieldnames for field in FIELDNAMES):
                        print(
                            f"[Warning] CSV header mismatch in '{CSV_FILENAME}'. "
                            f"You may need to inspect or delete the old file."
                        )
                        processed_urls = set()
                    else:
                        for row in reader:
                            if "source_url" in row:
                                processed_urls.add(row["source_url"])
            print(f"[1/4] Progress file found. Loaded {len(processed_urls)} processed URLs.")
        except Exception as e:
            print(f"[Warning] Failed to read progress file '{CSV_FILENAME}': {e}. Starting fresh.")
            processed_urls = set()
    else:
        print("[1/4] No progress file found. Starting fresh.")

    print(f"[2/4] Collecting all news links and metadata from {TOTAL_PAGES} index pages...")
    all_brief_info = []

    index_urls = [NEWS_BASE_URL] + [f"{NEWS_BASE_URL}page/{i}/" for i in range(2, TOTAL_PAGES + 1)]

    for url in tqdm(index_urls, desc="  -> Collecting index pages", unit="page"):
        brief_info_on_page = get_brief_info_from_index(url)
        all_brief_info.extend(brief_info_on_page)
        # Intentionally no extra sleep here (kept unchanged)

    unique_articles_map = {item["url"]: item for item in reversed(all_brief_info)}
    unique_info_list = list(unique_articles_map.values())

    info_to_scrape = [info for info in unique_info_list if info["url"] not in processed_urls]

    print(f"    Total unique items found: {len(unique_info_list)}")
    print(f"    Already scraped: {len(processed_urls)}")
    print(f"    New items to scrape: {len(info_to_scrape)}")

    if not info_to_scrape:
        print("[3/4] No new items to scrape.")
    else:
        print(f"[3/4] Scraping {len(info_to_scrape)} new items and writing to '{CSV_FILENAME}' and '{JSONL_FILENAME}'...")
        try:
            with open(CSV_FILENAME, "a", newline="", encoding="utf-8-sig") as f_csv, \
                 open(JSONL_FILENAME, "a", encoding="utf-8") as f_jsonl:

                writer = csv.DictWriter(f_csv, fieldnames=FIELDNAMES)
                if f_csv.tell() == 0:
                    writer.writeheader()

                for item in tqdm(info_to_scrape, desc="  -> Scraping details", unit="item"):
                    article_url = item["url"]
                    title = item["title"]
                    publish_time = item["publish_time"]
                    article_type = item["type"]

                    full_content = get_article_full_content(article_url)

                    row = {
                        "publish_time": publish_time,
                        "type": article_type,
                        "title": title,
                        "content": full_content,
                        "source_url": article_url,
                    }

                    # Write CSV (existing behavior)
                    writer.writerow(row)
                    # Write JSONL (new)
                    write_jsonl_line(f_jsonl, row)

        except KeyboardInterrupt:
            print("\n[Interrupted] User stopped the script. Progress saved; rerun to resume.")
            return
        except Exception as e:
            print(f"\n[Error] Unexpected error: {e}. Progress saved.")
            pass

    print(f"[4/4] Scraping finished. Converting CSV to Excel: '{EXCEL_FILENAME}'...")
    try:
        if os.path.exists(CSV_FILENAME) and os.path.getsize(CSV_FILENAME) > 0:
            df = pd.read_csv(CSV_FILENAME, encoding="utf-8-sig")
            df = df[FIELDNAMES]
            df.to_excel(EXCEL_FILENAME, index=False, engine="openpyxl")
            print(f"    Excel created: '{EXCEL_FILENAME}'.")
        else:
            print("    No data available to create Excel.")
    except Exception as e:
        print(f"    [Error] Failed to create Excel from CSV: {e}")
        print(f"    All data is still safely stored in '{CSV_FILENAME}'.")

    total_duration = time.time() - total_start_time
    print(f"\n{'=' * 60}\nAll tasks completed. Total time: {total_duration:.2f} seconds.\n{'=' * 60}")


if __name__ == "__main__":
    main()
