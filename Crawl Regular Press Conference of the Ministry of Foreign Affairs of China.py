# ==============================================================================
# Script Name
#
# Description (English)
# ------------------------------------------------------------------------------
# This script scrapes the Ministry of Foreign Affairs of China (mfa.gov.cn)
# "Regular Press Conference" pages and extracts Q&A-style content.
#
# Workflow:
#   1) Collect press conference links from multiple index pages
#   2) De-duplicate links and skip already processed URLs (resume support)
#   3) Crawl each press conference page, parse Q&A content
#   4) Append results to:
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
#   title, question, answer, source_url
#
# Dependencies
# ------------------------------------------------------------------------------
#   pip install requests beautifulsoup4 pandas tqdm openpyxl
#
# ------------------------------------------------------------------------------
# 中文说明
# ------------------------------------------------------------------------------
# 本脚本用于爬取外交部官网（mfa.gov.cn）“例行记者会”页面，并提取问答内容。
#
# 流程：
#   1）从多个索引页收集记者会链接
#   2）链接去重，并跳过已爬取链接（支持断点续爬）
#   3）爬取每个记者会页面，解析问答内容
#   4）结果追加写入：
#        - CSV（UTF-8 带 BOM）【同时作为断点续爬进度文件】
#        - JSONL（UTF-8，每行一条 JSON 记录）
#   5）将 CSV 转换为 Excel（.xlsx）
#
# 断点续爬逻辑：
#   - 仍然以 CSV 文件作为进度记录
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
# Configuration
# ==============================================================================
CSV_FILENAME = "mfa_regular_press_conference_data.csv"
JSONL_FILENAME = "mfa_regular_press_conference_data.jsonl"
EXCEL_FILENAME = "mfa_regular_press_conference_data.xlsx"
FIELDNAMES = ["title", "question", "answer", "source_url"]


def get_press_conference_links(index_url):
    """From an index page, collect all regular press conference links."""
    try:
        response = requests.get(index_url, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        links = []
        news_lists = soup.select("div.newsBd ul.list1")
        for ul in news_lists:
            for a_tag in ul.find_all("a", href=True):
                full_url = urljoin(index_url, a_tag["href"])
                links.append(full_url)
        return links
    except requests.exceptions.RequestException as e:
        print(f"Failed to request index page: {index_url}, error: {e}")
        return []


def get_press_conference_details(page_url):
    """From a single press conference page, extract the title and Q&A content."""
    try:
        response = requests.get(page_url, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.select_one("div.news-title h1")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        content_div = soup.select_one("#News_Body_Txt_A")
        if not content_div:
            return title, []

        qna_list = []
        paragraphs = content_div.find_all("p")
        current_question = "NO_QUESTION"
        current_answer_parts = []

        for p in paragraphs:
            text = p.get_text(" ", strip=True)
            strong_tag = p.find("strong")

            # Detect a new question
            if strong_tag and (":" in strong_tag.get_text() or "：" in strong_tag.get_text()):
                # Save the previous Q&A
                if current_question != "NO_QUESTION":
                    qna_list.append(
                        {"question": current_question, "answer": " ".join(current_answer_parts)}
                    )

                # Start a new Q&A
                current_question = strong_tag.get_text(strip=True)
                strong_tag.decompose()  # Remove the <strong> tag from the <p>
                current_answer_parts = [p.get_text(" ", strip=True)]
            else:
                # Continue accumulating answer parts
                current_answer_parts.append(text)

        # Save the last Q&A
        if current_question != "NO_QUESTION":
            qna_list.append({"question": current_question, "answer": " ".join(current_answer_parts)})

        return title, qna_list
    except requests.exceptions.RequestException as e:
        print(f"Failed to request details page: {page_url}, error: {e}")
        return "REQUEST_FAILED", []


def write_jsonl_line(fp, record):
    """Write one JSON object as a single JSONL line (UTF-8, keep Chinese characters)."""
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    """Main entry: run scraping and save results."""
    # Resume: load processed URLs from CSV
    processed_urls = set()
    if os.path.exists(CSV_FILENAME):
        try:
            with open(CSV_FILENAME, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "source_url" in row:
                        processed_urls.add(row["source_url"])
            print(f"Progress file detected. Loaded {len(processed_urls)} processed URLs.")
        except (IOError, csv.Error) as e:
            print(f"Error reading progress file '{CSV_FILENAME}': {e}. Starting fresh.")
            processed_urls = set()

    # Step 1/4: Collect links from all index pages
    base_url = "https://www.mfa.gov.cn/web/wjdt_674879/fyrbt_674889/"
    index_urls = [base_url + "index.shtml"] + [f"{base_url}index_{i}.shtml" for i in range(1, 31)]

    all_conference_links = []
    print("Step 1/4: Collecting all press conference links...")
    for url in tqdm(index_urls, desc="Collecting index pages"):
        all_conference_links.extend(get_press_conference_links(url))
        time.sleep(0.3)

    # De-duplicate and filter new links
    unique_links = sorted(list(set(all_conference_links)))
    links_to_scrape = [link for link in unique_links if link not in processed_urls]

    print(f"Found {len(unique_links)} unique links; {len(links_to_scrape)} are new and will be scraped.")
    if not links_to_scrape:
        print("All links have already been scraped.")

    # Step 2/4: Append scraped data to CSV + JSONL
    print(f"\nStep 2/4: Scraping and appending results to '{CSV_FILENAME}' and '{JSONL_FILENAME}'...")
    try:
        # Append mode; newline='' avoids extra blank lines on some platforms
        with open(CSV_FILENAME, "a", newline="", encoding="utf-8-sig") as f_csv, \
             open(JSONL_FILENAME, "a", encoding="utf-8") as f_jsonl:

            writer = csv.DictWriter(f_csv, fieldnames=FIELDNAMES)

            # Write header if file is empty
            if f_csv.tell() == 0:
                writer.writeheader()

            for link in tqdm(links_to_scrape, desc="Scraping press conference pages"):
                title, qna_data = get_press_conference_details(link)
                if title == "REQUEST_FAILED":
                    continue  # Skip failed requests

                for qna in qna_data:
                    row = {
                        "title": title,
                        "question": qna["question"],
                        "answer": qna["answer"],
                        "source_url": link,
                    }
                    # Write CSV (existing behavior)
                    writer.writerow(row)
                    # Write JSONL (new)
                    write_jsonl_line(f_jsonl, row)

                time.sleep(0.3)  # Polite crawling

    except KeyboardInterrupt:
        print("\nInterrupted by user. Progress saved; rerun to resume.")
        return
    except Exception as e:
        print(f"\nError during scraping: {e}. Progress saved; rerun to resume.")
        return

    # Step 3/4: Convert CSV to Excel
    print(f"\nStep 3/4: Converting CSV to Excel: '{EXCEL_FILENAME}'...")
    try:
        df = pd.read_csv(CSV_FILENAME)
        df.to_excel(EXCEL_FILENAME, index=False, engine="openpyxl")
        print("Excel file created successfully.")
    except Exception as e:
        print(f"Error creating Excel from CSV: {e}")
        print(f"All data is still safely stored in '{CSV_FILENAME}'.")

    # Step 4/4: Done
    print(f"\nStep 4/4: Done. Data saved to '{EXCEL_FILENAME}', '{CSV_FILENAME}', and '{JSONL_FILENAME}'.")


if __name__ == "__main__":
    main()
