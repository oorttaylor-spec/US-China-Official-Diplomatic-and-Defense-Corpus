# ==============================================================================
# Script Name
#
# Description (English)
# ------------------------------------------------------------------------------
# This script scrapes multiple "Press & Spokesperson" categories from the official
# website of the Ministry of National Defense of China (mod.gov.cn).
#
# For each configured category, the script:
#   1) Visits index pages (index.html, index_1.html, ...)
#   2) Extracts article URL + publish time from each index listing
#   3) Visits each article page and parses content into Q&A pairs
#   4) Appends results to:
#        - CSV  (UTF-8 with BOM)
#        - JSONL (UTF-8, one JSON object per line)
#   5) Converts the CSV output into an Excel (.xlsx) file
#
# Resume / checkpoint logic:
#   - The script uses the CSV output as the progress file.
#   - If a source_url already exists in the CSV, it will be skipped on rerun.
#
# Output Schema (per record)
# ------------------------------------------------------------------------------
#   publish_time, title, question, answer, source_url
#
# Dependencies
# ------------------------------------------------------------------------------
#   pip install requests beautifulsoup4 pandas tqdm openpyxl
#
# Notes
# ------------------------------------------------------------------------------
# - This version only adds JSONL output + English file names/comments.
# - Core scraping logic and behavior are intentionally kept unchanged.
#
# ------------------------------------------------------------------------------
# 中文说明
# ------------------------------------------------------------------------------
# 本脚本用于爬取国防部官网多个“新闻发言人/记者会”相关栏目。
#
# 每个栏目任务流程如下：
#   1）访问索引页（index.html、index_1.html ...）
#   2）从索引列表提取文章链接和发布时间
#   3）进入文章页解析“问答”内容
#   4）结果追加写入：
#        - CSV（UTF-8 带 BOM）
#        - JSONL（UTF-8，每行一条 JSON 记录）
#   5）将 CSV 转换为（.xlsx）Excel 文件
#
# 断点续爬逻辑：
#   - 仍然以 CSV 作为进度文件
#   - 若 CSV 中已有某个 source_url，则下次运行会跳过该链接
#
# 依赖安装：
#   pip install requests beautifulsoup4 pandas tqdm openpyxl
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

# ==============================================================================
# CONFIGURATION: Define all scraping tasks here
# ==============================================================================
TASKS = [
    {
        "name": "Spokesperson Remarks and Q&A",
        "base_url": "http://www.mod.gov.cn/gfbw/xwfyr/fyrthhdjzw/",
        "num_pages": 5,  # index.html + index_1.html to index_4.html
        "csv_filename": "mod_spokesperson_remarks_qna.csv",
        "jsonl_filename": "mod_spokesperson_remarks_qna.jsonl",
        "excel_filename": "mod_spokesperson_remarks_qna.xlsx",
    },
    {
        "name": "Regular News Briefings",
        "base_url": "http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/",
        "num_pages": 10,  # index.html + index_1.html to index_9.html
        "csv_filename": "mod_regular_news_briefings.csv",
        "jsonl_filename": "mod_regular_news_briefings.jsonl",
        "excel_filename": "mod_regular_news_briefings.xlsx",
    },
    {
        "name": "Regular Press Conferences",
        "base_url": "http://www.mod.gov.cn/gfbw/xwfyr/lxjzh_246940/",
        "num_pages": 11,  # index.html + index_1.html to index_10.html
        "csv_filename": "mod_regular_press_conferences.csv",
        "jsonl_filename": "mod_regular_press_conferences.jsonl",
        "excel_filename": "mod_regular_press_conferences.xlsx",
    },
    {
        "name": "Special Press Conferences",
        "base_url": "http://www.mod.gov.cn/gfbw/xwfyr/ztjzh/",
        "num_pages": 3,  # index.html + index_1.html to index_2.html
        "csv_filename": "mod_special_press_conferences.csv",
        "jsonl_filename": "mod_special_press_conferences.jsonl",
        "excel_filename": "mod_special_press_conferences.xlsx",
    },
]

# Output header (CSV columns)
FIELDNAMES = ["publish_time", "title", "question", "answer", "source_url"]


# ==============================================================================
# CORE SCRAPING FUNCTIONS
# ==============================================================================

def get_article_info_from_index(index_url):
    """From an index page, get a list of dicts: {'url': article_url, 'time': publish_time}."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = requests.get(index_url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        articles_info = []
        # Select the parent 'li' tag to access both link and time
        article_items = soup.select("ul#main-news-list li")
        for item in article_items:
            link_tag = item.find("a")
            time_tag = item.select_one("small.time")

            if link_tag and link_tag.has_attr("href") and time_tag:
                full_url = urljoin(index_url, link_tag["href"])
                publish_time = time_tag.get_text(strip=True)
                articles_info.append({"url": full_url, "time": publish_time})
        return articles_info

    except requests.exceptions.RequestException as e:
        print(f"\n[Error] Failed to request index page {index_url}: {e}")
        return []


def get_article_details(page_url):
    """From an article page, extract the title and Q&A content."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = requests.get(page_url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.select_one("div.article-header h1")
        title = title_tag.get_text(strip=True) if title_tag else "No Title Found"

        content_div = soup.select_one("div#article-content")
        if not content_div:
            return title, []

        qna_list = []
        paragraphs = content_div.find_all("p")

        current_qna = {}
        for p in paragraphs:
            speaker_tag = p.find("strong")
            if speaker_tag and any(keyword in speaker_tag.get_text() for keyword in ["问：", "记者"]):
                if current_qna:
                    qna_list.append(current_qna)
                current_qna = {"question": p.get_text(" ", strip=True), "answer": ""}
            elif current_qna:
                current_qna["answer"] += (
                    "\n" + p.get_text(" ", strip=True)
                    if current_qna["answer"]
                    else p.get_text(" ", strip=True)
                )

        if current_qna:
            qna_list.append(current_qna)

        if not qna_list and paragraphs:
            full_content = "\n".join([p.get_text(" ", strip=True) for p in paragraphs])
            qna_list.append({"question": "Full Text", "answer": full_content})

        return title, qna_list

    except requests.exceptions.RequestException as e:
        return f"Request Failed for {page_url}", []


def write_jsonl_line(fp, record):
    """Write one JSON object as a single line (UTF-8, keep Chinese characters)."""
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


# ==============================================================================
# MAIN EXECUTION LOGIC
# ==============================================================================
def main():
    """Main function to iterate through tasks and run the scraper."""
    print("--- Starting Ministry of National Defense Scraper ---")
    total_start_time = time.time()

    for task in TASKS:
        print("\n" + "=" * 80)
        print(f"Processing Category: {task['name']}")
        print("=" * 80)
        task_start_time = time.time()

        # Load progress for resume (unchanged behavior: based on CSV)
        processed_urls = set()
        if os.path.exists(task["csv_filename"]):
            try:
                # Handle empty file case
                if os.path.getsize(task["csv_filename"]) > 0:
                    with open(task["csv_filename"], "r", newline="", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if "source_url" in row:
                                processed_urls.add(row["source_url"])
                print(f"[1/4] Progress file found. Loaded {len(processed_urls)} already scraped URLs.")
            except Exception as e:
                print(f"[Warning] Could not read progress file '{task['csv_filename']}': {e}. Starting fresh.")
                processed_urls = set()
        else:
            print(f"[1/4] No progress file found. Starting fresh for '{task['name']}'.")

        print("[2/4] Collecting article links and times from all index pages...")
        index_urls = [task["base_url"] + "index.html"] + [
            f"{task['base_url']}index_{i}.html" for i in range(1, task["num_pages"])
        ]

        all_articles_info = []
        for url in tqdm(index_urls, desc=f"  -> Collecting from {task['name']}", unit="page"):
            all_articles_info.extend(get_article_info_from_index(url))
            time.sleep(0.3)  # Be polite to the server

        # De-duplicate by URL (unchanged logic)
        unique_articles_map = {item["url"]: item for item in reversed(all_articles_info)}
        unique_info_list = list(unique_articles_map.values())

        # Filter out already processed URLs (unchanged)
        info_to_scrape = [info for info in unique_info_list if info["url"] not in processed_urls]

        print(f"    Total unique articles found: {len(unique_info_list)}")
        print(f"    Already scraped: {len(processed_urls)}")
        print(f"    New articles to scrape: {len(info_to_scrape)}")

        if not info_to_scrape:
            print("[3/4] No new articles to scrape for this category.")
        else:
            print(
                f"[3/4] Scraping {len(info_to_scrape)} new articles and writing to "
                f"'{task['csv_filename']}' and '{task['jsonl_filename']}'..."
            )
            try:
                with open(task["csv_filename"], "a", newline="", encoding="utf-8-sig") as f_csv, \
                     open(task["jsonl_filename"], "a", encoding="utf-8") as f_jsonl:

                    writer = csv.DictWriter(f_csv, fieldnames=FIELDNAMES)
                    if f_csv.tell() == 0:
                        writer.writeheader()

                    for item in tqdm(info_to_scrape, desc=f"  -> Scraping {task['name']}", unit="article"):
                        link = item["url"]
                        publish_time = item["time"]

                        title, qna_data = get_article_details(link)
                        if "Request Failed" in title:
                            tqdm.write(f"[Error] Skipping failed request for URL: {link}")
                            continue

                        for qna in qna_data:
                            row = {
                                "publish_time": publish_time,
                                "title": title,
                                "question": qna["question"],
                                "answer": qna["answer"],
                                "source_url": link,
                            }
                            # Write CSV (existing behavior)
                            writer.writerow(row)
                            # Write JSONL (new)
                            write_jsonl_line(f_jsonl, row)

                        time.sleep(0.3)

            except KeyboardInterrupt:
                print("\n[Interrupted] Script paused by user. Progress is saved. Re-run to resume.")
                return
            except Exception as e:
                print(f"\n[Error] An unexpected error occurred during scraping: {e}. Progress is saved.")
                continue

        print(f"[4/4] Converting data to Excel file: '{task['excel_filename']}'")
        try:
            if os.path.exists(task["csv_filename"]) and os.path.getsize(task["csv_filename"]) > 0:
                df = pd.read_csv(task["csv_filename"])
                # Ensure column order in final Excel file
                df = df[FIELDNAMES]
                df.to_excel(task["excel_filename"], index=False, engine="openpyxl")
                print(f"    Successfully created '{task['excel_filename']}'.")
            else:
                print("    No data available to create Excel file.")
        except Exception as e:
            print(f"    [Error] Failed to create Excel file: {e}")
            print(f"    However, all data is safely stored in '{task['csv_filename']}'.")

        task_duration = time.time() - task_start_time
        print(f"--- Finished '{task['name']}' in {task_duration:.2f} seconds. ---")

    total_duration = time.time() - total_start_time
    print("\n" + "=" * 58)
    print(f"All tasks completed in {total_duration:.2f} seconds.")
    print("=" * 58)


if __name__ == "__main__":
    main()
