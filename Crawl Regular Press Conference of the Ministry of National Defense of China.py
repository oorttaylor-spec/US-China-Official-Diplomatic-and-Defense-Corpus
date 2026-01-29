# ==============================================================================
# Description (English)
# ------------------------------------------------------------------------------
# This script crawls the "Regular Press Conference" transcripts published on the
# official website of the Ministry of National Defense of China.
#
# It follows a three-level crawling logic:
#   1. Index pages (monthly listings)
#   2. Intermediate pages
#   3. Final "text transcript" pages
#
# For each transcript page, the script:
#   - Collects all paginated content (_2.html, _3.html, ...)
#   - Parses the content into Question–Answer (Q&A) pairs
#   - Writes results incrementally to CSV and JSONL files
#   - Converts the CSV file into an Excel (.xlsx) file at the end
#
# Resume / checkpoint logic:
#   - The script uses the CSV file as a progress record.
#   - If a source_url already exists in the CSV, it will be skipped on rerun.
#
# Output Files
# ------------------------------------------------------------------------------
# 1. mod_regular_press_transcripts.csv
#    - UTF-8 (with BOM)
#    - Tabular format
#    - Columns:
#        * title        : Article title
#        * question     : Question text (or "Full Text" if no Q&A structure)
#        * answer       : Answer text
#        * source_url   : Original article URL
#
# 2. mod_regular_press_transcripts.jsonl
#    - UTF-8 JSON Lines format
#    - One JSON object per line
#    - Same fields as the CSV output
#
# 3. mod_regular_press_transcripts.xlsx
#    - Excel file generated from the CSV output
#
# Dependencies
# ------------------------------------------------------------------------------
# Required Python packages:
#   - requests
#   - beautifulsoup4
#   - pandas
#   - tqdm
#   - openpyxl
#
# Install dependencies with:
#   pip install requests beautifulsoup4 pandas tqdm openpyxl
#
# The script is safe to interrupt (Ctrl+C). Progress is preserved via the CSV
# file, and rerunning the script will continue from where it stopped.
#
# Description (中文)
# ------------------------------------------------------------------------------
# 本脚本用于爬取中国国防部官网“例行记者会”栏目中的文字实录内容。
#
# 爬取流程采用三级结构：
#   1. 索引页（按月份）
#   2. 中间页
#   3. 最终“文字实录”页面
#
# 对每一篇实录文章，脚本会：
#   - 自动处理多页正文（如 _2.html、_3.html）
#   - 将正文解析为“问—答”结构
#   - 实时写入 CSV 和 JSONL 文件
#   - 在任务结束后将 CSV 转换为 Excel 文件
#
# 断点续爬说明：
#   - 脚本以 CSV 文件作为进度记录
#   - 若某个 source_url 已存在于 CSV 中，则该文章会被跳过
#
# 输出文件说明
# ------------------------------------------------------------------------------
# 1. mod_regular_press_transcripts.csv
#    - UTF-8（含 BOM）
#    - 表格格式
#    - 字段包括：
#        * title        ：文章标题
#        * question     ：提问内容（若无问答结构则为“Full Text”）
#        * answer       ：回答正文
#        * source_url   ：原始页面链接
#
# 2. mod_regular_press_transcripts.jsonl
#    - JSON Lines 格式（一行一条记录）
#    - UTF-8 编码
#    - 字段与 CSV 完全一致
#
# 3. mod_regular_press_transcripts.xlsx
#    - 由 CSV 转换生成的 Excel 文件
#
# 脚本支持中途手动中断，重新运行后将自动从已完成进度继续。
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
# China Ministry of National Defense - Regular Press Conference Transcripts
# Source: http://www.mod.gov.cn/gfbw/xwfyr/lxjzhzt/index.html
# ==============================================================================
TASKS = [
    {
        "name": "Regular Press Conference Transcripts",
        "base_url": "http://www.mod.gov.cn/gfbw/xwfyr/lxjzhzt/",
        "num_pages": 4,  # index.html to index_3.html (4 pages total)
        "csv_filename": "mod_regular_press_transcripts.csv",
        "jsonl_filename": "mod_regular_press_transcripts.jsonl",
        "excel_filename": "mod_regular_press_transcripts.xlsx",
        "task_type": "transcript",  # Use the existing 3-level crawling logic
    },
]

# Output schema (CSV header)
FIELDNAMES = ["title", "question", "answer", "source_url"]


# ==============================================================================
# CORE SCRAPING FUNCTIONS
# ==============================================================================

def get_links_from_index(index_url, selector):
    """Generic helper: extract links from an index page with a CSS selector."""
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

        links = []
        for a_tag in soup.select(selector):
            if a_tag.has_attr("href"):
                full_url = urljoin(index_url, a_tag["href"])
                links.append(full_url)
        return links
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Failed to request index page {index_url}: {e}")
        return []


def get_transcript_base_url(intermediate_url):
    """For transcript tasks: from an intermediate page, get the final transcript page URL."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = requests.get(intermediate_url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the "文字实录" button link (unchanged logic)
        link_tag = soup.select_one("a.button.chinese")
        if link_tag and link_tag.has_attr("href"):
            return urljoin(intermediate_url, link_tag["href"])
        return None
    except requests.exceptions.RequestException:
        return None


def parse_qna_from_paragraphs(paragraphs):
    """Parse a list of <p> tags into a list of Q&A dicts."""
    qna_list = []
    current_qna = {}

    for p in paragraphs:
        text = p.get_text(" ", strip=True)
        if not text:
            continue

        speaker_tag = p.find("strong")
        is_question = speaker_tag and any(
            keyword in speaker_tag.get_text() for keyword in ["问：", "记者"]
        )

        if is_question:
            # Save the previous complete Q&A
            if current_qna and current_qna.get("answer"):
                qna_list.append(current_qna)
            current_qna = {"question": text, "answer": ""}
        elif current_qna:
            # Append answer text
            current_qna["answer"] += ("\n" + text) if current_qna["answer"] else text

    # Append the last Q&A
    if current_qna and current_qna.get("answer"):
        qna_list.append(current_qna)

    # If not in Q&A format, store full content as one record
    if not qna_list and paragraphs:
        full_content = "\n".join(
            [p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True)]
        )
        qna_list.append({"question": "Full Text", "answer": full_content})

    return qna_list


def get_article_details(page_url, task_type):
    """
    Fetch article details.
    Supports transcript pages with pagination via suffix _2.html, _3.html, ...
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    all_paragraphs = []
    title = "Untitled"

    try:
        page_num = 1
        while True:
            if page_num == 1:
                current_url = page_url
            else:
                # Build next page URL (e.g., .../xxxx_2.html)
                base, ext = os.path.splitext(page_url)
                current_url = f"{base}_{page_num}{ext}"

            response = requests.get(current_url, headers=headers, timeout=15)

            # If request fails (e.g., 404), treat as end of pagination
            if response.status_code != 200:
                if page_num == 1:
                    raise requests.exceptions.RequestException(
                        f"Initial request failed, status code: {response.status_code}"
                    )
                else:
                    break

            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            # Title only on the first page
            if page_num == 1:
                title_tag = soup.select_one("div.article-header h1")
                if title_tag:
                    title = title_tag.get_text(strip=True)

            content_div = soup.select_one("div#article-content")
            if content_div:
                all_paragraphs.extend(content_div.find_all("p"))

            page_num += 1

    except requests.exceptions.RequestException as e:
        tqdm.write(f"\n[ERROR] Failed to crawl page {page_url}: {e}")
        return "REQUEST_FAILED", []

    qna_list = parse_qna_from_paragraphs(all_paragraphs)
    return title, qna_list


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def write_jsonl_line(fp, record: dict):
    """Write one JSON line (UTF-8, keep Chinese characters)."""
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    """Main entry: iterate tasks and run the crawler."""
    print("--- MOD crawler started ---")
    total_start_time = time.time()

    for task in TASKS:
        print("\n" + "=" * 80)
        print(f"Processing category: {task['name']}")
        print("=" * 80)
        task_start_time = time.time()

        # 1) Load progress for resume (unchanged logic: based on CSV)
        processed_urls = set()
        if os.path.exists(task["csv_filename"]):
            try:
                if os.path.getsize(task["csv_filename"]) > 0:
                    with open(task["csv_filename"], "r", newline="", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if "source_url" in row:
                                processed_urls.add(row["source_url"])
                print(f"[1/4] Progress file found. Loaded {len(processed_urls)} processed URLs.")
            except Exception as e:
                print(
                    f"[WARNING] Failed to read progress file '{task['csv_filename']}': {e}. Start fresh."
                )
        else:
            print(f"[1/4] No progress file. Start fresh for '{task['name']}'.")

        # 2) Collect final article URLs
        print("[2/4] Collecting final article URLs from all index pages...")
        index_urls = [task["base_url"] + "index.html"] + [
            f"{task['base_url']}index_{i}.html" for i in range(1, task["num_pages"])
        ]
        final_article_urls = []

        # Transcript: 3-level crawling flow (unchanged)
        intermediate_links = []
        selector = "ul#main-news-list li.article h2.title a"
        for url in tqdm(index_urls, desc="  -> L1: Collect month links", unit="page"):
            intermediate_links.extend(get_links_from_index(url, selector))

        for url in tqdm(list(set(intermediate_links)), desc="  -> L2: Get transcript URLs", unit="month"):
            base_url = get_transcript_base_url(url)
            if base_url:
                final_article_urls.append(base_url)
            time.sleep(0.2)

        unique_links = sorted(list(set(final_article_urls)))
        links_to_scrape = [link for link in unique_links if link not in processed_urls]

        print(f"    Found total: {len(unique_links)} articles")
        print(f"    Already crawled: {len(processed_urls)}")
        print(f"    New to crawl: {len(links_to_scrape)}")

        # 3) Crawl and write CSV + JSONL (new: JSONL output; CSV logic unchanged)
        if not links_to_scrape:
            print("[3/4] No new articles to crawl.")
        else:
            print(
                f"[3/4] Crawling {len(links_to_scrape)} new articles and writing to "
                f"'{task['csv_filename']}' and '{task['jsonl_filename']}'..."
            )
            try:
                # Open CSV (append) + JSONL (append)
                with open(task["csv_filename"], "a", newline="", encoding="utf-8-sig") as f_csv, \
                     open(task["jsonl_filename"], "a", encoding="utf-8") as f_jsonl:

                    writer = csv.DictWriter(f_csv, fieldnames=FIELDNAMES)

                    # Write CSV header if file is empty
                    if f_csv.tell() == 0:
                        writer.writeheader()

                    for link in tqdm(links_to_scrape, desc=f"  -> Crawling {task['name']}", unit="article"):
                        title, qna_data = get_article_details(link, task["task_type"])
                        if title == "REQUEST_FAILED":
                            continue

                        for qna in qna_data:
                            row = {
                                "title": title,
                                "question": qna["question"],
                                "answer": qna["answer"],
                                "source_url": link,
                            }
                            # Write CSV row (existing behavior)
                            writer.writerow(row)
                            # Write JSONL record (new)
                            write_jsonl_line(f_jsonl, row)

                        time.sleep(0.3)

            except KeyboardInterrupt:
                print("\n[INTERRUPTED] User stopped the script. Progress saved. Re-run to continue.")
                return
            except Exception as e:
                print(f"\n[ERROR] Unexpected error: {e}. Progress saved.")

        # 4) Convert CSV to Excel (unchanged)
        print(f"[4/4] Converting CSV to Excel: '{task['excel_filename']}'")
        try:
            if os.path.exists(task["csv_filename"]) and os.path.getsize(task["csv_filename"]) > 0:
                df = pd.read_csv(task["csv_filename"])
                df.to_excel(task["excel_filename"], index=False, engine="openpyxl")
                print(f"    Excel created: '{task['excel_filename']}'.")
            else:
                print("    No data available to create Excel.")
        except Exception as e:
            print(
                f"    [ERROR] Failed to create Excel: {e}. "
                f"All data is still saved in '{task['csv_filename']}'."
            )

        task_duration = time.time() - task_start_time
        print(f"--- Finished '{task['name']}' in {task_duration:.2f} seconds. ---")

    total_duration = time.time() - total_start_time
    print(f"\n{'=' * 60}\nAll tasks finished. Total time: {total_duration:.2f} seconds.\n{'=' * 60}")


if __name__ == "__main__":
    main()
