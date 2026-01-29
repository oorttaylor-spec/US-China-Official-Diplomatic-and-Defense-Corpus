# ==============================================================================
# Script Name
#
# Description (English)
# ------------------------------------------------------------------------------
# This script crawls the archived White House "Briefing Room" pages from:
#   https://bidenwhitehouse.archives.gov/briefing-room/
#
# It uses multiprocessing to split index pages into two groups (odd/even) and
# crawls them in parallel. For each article found on an index page, it fetches
# the full content and splits long text into multiple columns to avoid Excel cell
# character limits.
#
# Workflow:
#   1) Build index page URLs (total pages = TOTAL_PAGES)
#   2) Split index URLs into odd/even lists for parallel processing
#   3) Each process writes to its own temporary CSV and JSONL file
#   4) Merge temporary files, de-duplicate, sort by publish time (desc),
#      and output final CSV/JSONL/Excel
#
# Resume / checkpoint logic:
#   - The script reads existing temp/final CSV files to build processed_urls
#     (based on 'source_url'). Already processed articles are skipped.
#
# Output Files
# ------------------------------------------------------------------------------
# Temporary (per process):
#   - _temp_biden_briefing_room_odd.csv
#   - _temp_biden_briefing_room_even.csv
#   - _temp_biden_briefing_room_odd.jsonl
#   - _temp_biden_briefing_room_even.jsonl
#
# Final:
#   - biden_briefing_room_data_final.csv
#   - biden_briefing_room_data_final.jsonl
#   - biden_briefing_room_data_final.xlsx
#
# Dependencies
# ------------------------------------------------------------------------------
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3
#
# ------------------------------------------------------------------------------
# 中文说明
# ------------------------------------------------------------------------------
# 本脚本用于爬取拜登政府白宫档案站点 “Briefing Room” 的内容：
#   https://bidenwhitehouse.archives.gov/briefing-room/
#
# 采用多进程并行：将索引页按奇偶页拆分为两组并行抓取。
# 对每篇文章抓取正文，并按 Excel 单元格字符限制拆分为多列输出。
#
# 流程：
#   1）生成索引页 URL（总页数 TOTAL_PAGES）
#   2）按奇偶拆分索引页列表并行处理
#   3）每个进程分别写入自己的临时 CSV + JSONL
#   4）合并临时文件、去重、按发布时间倒序排序，输出最终 CSV/JSONL/Excel
#
# 断点续爬逻辑：
#   - 仍然基于已有临时/最终 CSV 的 source_url 字段加载已爬取 URL
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
import random
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from multiprocessing import Pool

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ARCHIVE_BASE_DOMAIN = "https://bidenwhitehouse.archives.gov"
BRIEFING_ROOM_BASE_URL = ARCHIVE_BASE_DOMAIN + "/briefing-room/"
TOTAL_PAGES = 1247
NUM_PROCESSES = 2  # Number of parallel processes
CELL_CHAR_LIMIT = 30000  # Excel cell character limit
MAX_CONTENT_COLUMNS = 10  # Maximum number of content columns

# File names (English)
TEMP_ODD_CSV = "_temp_biden_briefing_room_odd.csv"
TEMP_EVEN_CSV = "_temp_biden_briefing_room_even.csv"
TEMP_ODD_JSONL = "_temp_biden_briefing_room_odd.jsonl"
TEMP_EVEN_JSONL = "_temp_biden_briefing_room_even.jsonl"

FINAL_CSV = "biden_briefing_room_data_final.csv"
FINAL_JSONL = "biden_briefing_room_data_final.jsonl"
FINAL_EXCEL = "biden_briefing_room_data_final.xlsx"

# Columns
BASE_FIELDNAMES = ["publish_time", "type", "title", "source_url"]
CONTENT_FIELDNAMES = [f"content_part_{i + 1}" for i in range(MAX_CONTENT_COLUMNS)]
FINAL_FIELDNAMES = BASE_FIELDNAMES + CONTENT_FIELDNAMES


# ==============================================================================
# SHARED UTILITIES
# ==============================================================================

def create_retriable_session():
    """Create a requests session with retry behavior (unchanged logic)."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[403, 500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def split_text_into_chunks(text, chunk_size):
    """Split a long text into fixed-size chunks."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def write_jsonl_line(fp, record):
    """Write one JSON object as a JSONL line (UTF-8, keep non-ASCII characters)."""
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


# ==============================================================================
# CORE SCRAPING FUNCTIONS
# ==============================================================================

def get_brief_info_from_index(index_url):
    try:
        session = create_retriable_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/10{random.randint(0, 8)}.0.0.0 Safari/537.36"
            ),
            "Referer": BRIEFING_ROOM_BASE_URL
        }
        response = session.get(index_url, headers=headers, timeout=20)

        # Force response encoding to UTF-8 (unchanged behavior)
        response.encoding = "utf-8"

        if response.status_code == 404:
            return []
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        articles_info = []
        for item in soup.select("article.news-item"):
            title_tag = item.select_one("a.news-item__title")
            time_tag = item.select_one("time.posted-on")
            type_tag = item.select_one("span.cat-links a")
            if all([title_tag, time_tag, type_tag, title_tag.has_attr("href")]):
                articles_info.append({
                    "url": urljoin(ARCHIVE_BASE_DOMAIN, title_tag["href"]),
                    "title": title_tag.get_text(strip=True),
                    "publish_time": time_tag.get("datetime", time_tag.get_text(strip=True)),
                    "type": type_tag.get_text(strip=True),
                })
        return articles_info
    except Exception as e:
        print(f"\n[SEVERE] Index page failed {index_url}: {e}")
        return []


def get_article_full_content(article_url):
    try:
        session = create_retriable_session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/10{random.randint(0, 8)}.0.0.0 Safari/537.36"
            ),
            "Referer": BRIEFING_ROOM_BASE_URL
        }
        response = session.get(article_url, headers=headers, timeout=20)

        # Force response encoding to UTF-8 (unchanged behavior)
        response.encoding = "utf-8"

        if response.status_code == 404:
            return "CONTENT_NOT_FOUND"
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        content_section = soup.select_one("section.body-content div.container")
        if not content_section:
            return "CONTENT_NOT_FOUND"
        # Use spaces to avoid CSV formatting issues from line breaks (unchanged behavior)
        return content_section.get_text(separator=" ", strip=True) or "CONTENT_NOT_FOUND"
    except Exception as e:
        print(f"\n[SEVERE] Detail page failed {article_url}: {e}")
        return "CONTENT_FETCH_FAILED"


def worker_process(urls_to_process, processed_urls, temp_csv_filename, temp_jsonl_filename, process_id):
    """
    Worker for a single process:
    - Crawl assigned index URLs
    - Append results into its own temporary CSV and JSONL file
    """
    # Ensure temp CSV exists and has a header
    if not os.path.exists(temp_csv_filename) or os.path.getsize(temp_csv_filename) == 0:
        pd.DataFrame(columns=FINAL_FIELDNAMES).to_csv(temp_csv_filename, index=False, encoding="utf-8-sig")

    # Ensure temp JSONL exists (append mode will create if missing)
    if not os.path.exists(temp_jsonl_filename):
        open(temp_jsonl_filename, "a", encoding="utf-8").close()

    with tqdm(urls_to_process, desc=f"  -> Process {process_id}", position=process_id, unit="page") as pbar:
        for index_url in pbar:
            brief_info_on_page = get_brief_info_from_index(index_url)

            if not brief_info_on_page:
                pbar.write(f"    Index page {index_url} failed or empty; skipped.")
                time.sleep(random.uniform(3, 5))
                continue

            current_page_info_to_scrape = [info for info in brief_info_on_page if info["url"] not in processed_urls]

            page_data_batch = []
            jsonl_batch = []
            if current_page_info_to_scrape:
                for item in current_page_info_to_scrape:
                    full_content = get_article_full_content(item["url"])

                    # Keep original skip logic semantics ("failed/not found" => skip)
                    if "FAILED" not in full_content and "NOT_FOUND" not in full_content:
                        content_chunks = split_text_into_chunks(full_content, CELL_CHAR_LIMIT)

                        row_data = {
                            "publish_time": item["publish_time"],
                            "type": item["type"],
                            "title": item["title"],
                            "source_url": item["url"],
                        }

                        for i, chunk in enumerate(content_chunks[:MAX_CONTENT_COLUMNS]):
                            row_data[f"content_part_{i + 1}"] = chunk

                        page_data_batch.append(row_data)
                        jsonl_batch.append(row_data)
                    else:
                        pbar.write(f"    [Warning] Skipped article {item['url']}, reason: {full_content}")

                    time.sleep(random.uniform(0.5, 1.5))

            if page_data_batch:
                df_batch = pd.DataFrame(page_data_batch)
                df_batch.to_csv(temp_csv_filename, mode="a", header=False, index=False, encoding="utf-8-sig")

            if jsonl_batch:
                with open(temp_jsonl_filename, "a", encoding="utf-8") as f_jsonl:
                    for rec in jsonl_batch:
                        write_jsonl_line(f_jsonl, rec)

            time.sleep(random.uniform(1, 3))


def merge_and_finalize():
    """Merge all temp files, sort, and generate final CSV/JSONL/Excel outputs."""
    print("\n[4/4] All processes finished. Merging, sorting, and generating final files...")

    all_dfs = []
    for temp_file in [TEMP_ODD_CSV, TEMP_EVEN_CSV]:
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 50:
            try:
                df_temp = pd.read_csv(temp_file, header=0, encoding="utf-8-sig")
                all_dfs.append(df_temp)
            except Exception as e:
                print(f"[Warning] Failed to read temp file {temp_file}: {e}")

    if not all_dfs:
        print("No data to merge.")
        return

    final_df = pd.concat(all_dfs, ignore_index=True).drop_duplicates(subset=["source_url"])

    # Sort by publish time descending (unchanged behavior)
    final_df["publish_time_dt"] = pd.to_datetime(final_df["publish_time"], errors="coerce")
    final_df.sort_values(by="publish_time_dt", ascending=False, inplace=True)
    final_df.drop(columns=["publish_time_dt"], inplace=True)

    final_df = final_df.reindex(columns=FINAL_FIELDNAMES)

    try:
        # Final CSV
        final_df.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
        print(f"    Created merged CSV: {FINAL_CSV}")

        # Final Excel
        final_df.to_excel(FINAL_EXCEL, index=False, engine="openpyxl")
        print(f"    Created Excel: {FINAL_EXCEL}")

        # Final JSONL (new)
        with open(FINAL_JSONL, "w", encoding="utf-8") as f_jsonl:
            for _, row in final_df.iterrows():
                record = {col: ("" if pd.isna(row[col]) else row[col]) for col in FINAL_FIELDNAMES}
                write_jsonl_line(f_jsonl, record)
        print(f"    Created JSONL: {FINAL_JSONL}")

        # Cleanup temp files (including JSONL)
        for temp_file in [TEMP_ODD_CSV, TEMP_EVEN_CSV, TEMP_ODD_JSONL, TEMP_EVEN_JSONL]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        print("    Temporary files cleaned up.")

    except Exception as e:
        print(f"    [Error] Failed to generate final outputs: {e}")


# ==============================================================================
# MAIN EXECUTION LOGIC
# ==============================================================================
def main():
    """Main entry: start parallel scraping and finalize outputs."""
    print("--- Starting Biden White House Briefing Room Scraper (Parallel Mode) ---")
    total_start_time = time.time()

    processed_urls = set()
    # Resume: read processed URLs from existing CSV progress files (unchanged behavior)
    for filename in [TEMP_ODD_CSV, TEMP_EVEN_CSV, FINAL_CSV]:
        if os.path.exists(filename):
            try:
                if os.path.getsize(filename) > 50:
                    df_existing = pd.read_csv(filename, encoding="utf-8-sig")
                    if "source_url" in df_existing.columns:
                        processed_urls.update(df_existing["source_url"].tolist())
            except Exception as e:
                print(f"[Warning] Failed to read progress file '{filename}': {e}.")
    print(f"[1/4] Progress loaded: {len(processed_urls)} processed URLs found.")

    print(f"[2/4] Assigning {TOTAL_PAGES} index pages to {NUM_PROCESSES} processes...")
    index_urls = [BRIEFING_ROOM_BASE_URL] + [
        f"{BRIEFING_ROOM_BASE_URL}page/{i}/" for i in range(2, TOTAL_PAGES + 1)
    ]

    odd_urls = index_urls[::2]
    even_urls = index_urls[1::2]

    tasks = [
        (odd_urls, processed_urls, TEMP_ODD_CSV, TEMP_ODD_JSONL, 0),
        (even_urls, processed_urls, TEMP_EVEN_CSV, TEMP_EVEN_JSONL, 1),
    ]

    print("[3/4] Starting parallel crawling...")
    with Pool(processes=NUM_PROCESSES) as pool:
        pool.starmap(worker_process, tasks)

    merge_and_finalize()

    total_duration = time.time() - total_start_time
    print(f"\n{'=' * 60}\nAll tasks completed. Total time: {total_duration:.2f} seconds.\n{'=' * 60}")


if __name__ == "__main__":
    main()
