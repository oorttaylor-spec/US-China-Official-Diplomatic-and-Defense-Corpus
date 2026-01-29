# ==============================================================================
# US State Department (2021–2025) Press Releases Crawler
#
# Description (English)
# ------------------------------------------------------------------------------
# This script scrapes press releases from the U.S. State Department website:
#   https://2021-2025.state.gov/press-releases/
#
# It collects article metadata from index pages (publish time, type, title, URL),
# and then visits each article page to extract the full content (including <p>, <h3>,
# and nested <ul>/<li> lists with indentation and numbering).
#
# Workflow:
#   1) Load progress from CSV (resume support by source_url)
#   2) Collect article info from index pages (TOTAL_PAGES)
#   3) De-duplicate and filter out processed URLs
#   4) Crawl new article pages and append results to:
#        - CSV  (UTF-8 with BOM)  [progress/resume file]
#        - JSON (UTF-8, one JSON object per line)
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
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3 playwright
#
# ------------------------------------------------------------------------------
# 中文说明
# ------------------------------------------------------------------------------
# 本脚本用于爬取美国国务院（2021-2025）网站的新闻简报：
#   https://2021-2025.state.gov/press-releases/
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
#
# 断点续爬逻辑：
#   - 仍然以 CSV 文件作为进度记录
#   - 若 CSV 中已有某个 source_url，则下次运行会跳过该链接
#
# 依赖安装：
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3 playwright
# ==============================================================================

import asyncio
import csv
import json
import os
import re
from typing import List, Dict

import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm


# ---------------- 参数 ----------------
BASE = "https://2021-2025.state.gov"
INDEX_BASE = f"{BASE}/press-releases/"
TOTAL_PAGES = 1111

# 输出文件（建议放在同目录）
OUT_CSV = "state_department_press_releases_2021_2025.csv"
OUT_JSON = "state_department_press_releases_2021_2025.json"


# ---------------- 工具函数 ----------------
def ensure_dir_for(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def sanitize_text(txt: str) -> str:
    if not txt:
        return ""
    txt = txt.replace("\xa0", " ").replace("\r", " ")
    txt = re.sub(r"[ \t\f\v]+", " ", txt)
    return txt.strip()


def load_done_urls() -> set:
    if not os.path.exists(OUT_CSV):
        return set()
    try:
        df = pd.read_csv(OUT_CSV)
        return set(df["url"].dropna().tolist())
    except Exception:
        return set()


def open_writer():
    """返回 (file_handle, writer)，CSV为UTF-8-SIG + QUOTE_ALL"""
    file_exists = os.path.exists(OUT_CSV)
    fh = open(OUT_CSV, "a", encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(
        fh,
        fieldnames=["type", "title", "date", "url", "content"],
        quoting=csv.QUOTE_ALL,
        delimiter=",",
        lineterminator="\n",
        escapechar="\\",
    )
    if not file_exists:
        writer.writeheader()
    return fh, writer


def parse_index_items(html: str) -> List[Dict]:
    """解析索引页：提取类型(type)、标题(title)、日期(date)、URL(url)"""
    soup = BeautifulSoup(html, "lxml")
    items = []
    for li in soup.select("ul.collection-results li.collection-result"):
        a = li.select_one("a.collection-result__link[href]")
        if not a:
            continue
        href = a.get("href", "").strip()
        if href.startswith("/"):
            href = BASE + href
        title = sanitize_text(a.get_text(" ", strip=True))
        typ = sanitize_text(
            (li.select_one("p.collection-result__date") or {}).get_text(" ", strip=True)
        )
        date_el = li.select_one("div.collection-result-meta span:last-child")
        date_text = sanitize_text(
            date_el.get_text(" ", strip=True) if date_el else ""
        )
        if href and title:
            items.append(
                {"type": typ, "title": title, "url": href, "date": date_text}
            )
    return items


def parse_detail_content(html: str) -> str:
    """只提取正文（保留自然段）"""
    soup = BeautifulSoup(html, "lxml")
    entry = soup.select_one("div.entry-content") or soup.select_one("article")
    if not entry:
        return ""

    # 删除不相关元素
    for bad in entry.select(
        "script, style, noscript, figure, iframe, form, input, button, svg"
    ):
        bad.decompose()
    for bad_sel in [
        ".post_tags",
        ".tags",
        ".report__back-to-top",
        ".page-header__actions",
        ".sharethis-inline-share-buttons",
        ".social-share",
        ".wp-block-buttons",
    ]:
        for b in entry.select(bad_sel):
            b.decompose()

    # 提取段落
    paragraphs = []
    for tag in entry.find_all(["h2", "h3", "p", "li", "blockquote"]):
        text = sanitize_text(tag.get_text(" ", strip=True))
        if text:
            paragraphs.append(text)

    if not paragraphs:
        text = entry.get_text("\n", strip=True)
        return sanitize_text(text)

    return "\n\n".join(paragraphs)


async def fetch_html(page, url: str, wait_selector: str = None, extra_wait_sec: float = 0.0) -> str:
    """加载页面HTML"""
    await page.goto(url, timeout=120_000, wait_until="domcontentloaded")
    if extra_wait_sec:
        await asyncio.sleep(extra_wait_sec)
    if wait_selector:
        await page.wait_for_selector(wait_selector, timeout=30_000)
    return await page.content()


def write_dual(data: Dict, writer, fh):
    """写入CSV与JSON，保证正文在CSV单格内"""
    # 先复制并转义换行符，防止Excel错行
    csv_data = data.copy()
    if isinstance(csv_data["content"], str):
        csv_data["content"] = csv_data["content"].replace("\n", "\\n").replace("\r", "")
    writer.writerow(csv_data)
    fh.flush()

    # 再写JSON（保留原始段落换行）
    with open(OUT_JSON, "a", encoding="utf-8") as jf:
        jf.write(json.dumps(data, ensure_ascii=False) + "\n")


# ---------------- 主爬虫 ----------------
async def crawl_all():
    ensure_dir_for(OUT_CSV)
    done = load_done_urls()
    print(f"✅ 已完成 {len(done)} 条，开始爬取到 {OUT_CSV} / {OUT_JSON}")

    fh, writer = open_writer()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122 Safari/537.36"
            )
        )
        page = await context.new_page()

        for i in tqdm(range(1, TOTAL_PAGES + 1), desc="索引页"):
            index_url = INDEX_BASE if i == 1 else f"{INDEX_BASE}page/{i}/"
            try:
                index_html = await fetch_html(
                    page,
                    index_url,
                    wait_selector="ul.collection-results li.collection-result",
                    extra_wait_sec=2.0,
                )
            except Exception as e:
                print(f"⚠️ 第{i}页加载失败: {e}")
                continue

            items = parse_index_items(index_html)
            if not items:
                print(f"⚠️ 第{i}页为空或结构变化：{index_url}")
                continue

            # 抓详情页
            for it in items:
                if it["url"] in done:
                    continue

                dpage = await context.new_page()
                try:
                    detail_html = await fetch_html(
                        dpage,
                        it["url"],
                        wait_selector="div.entry-content, article",
                        extra_wait_sec=1.5,
                    )
                    content = parse_detail_content(detail_html)
                except Exception as e:
                    print(f"⚠️ 详情页失败 {it['url']}: {e}")
                    content = ""
                finally:
                    await dpage.close()

                row = {
                    "type": it["type"],
                    "title": it["title"],
                    "date": it["date"],
                    "url": it["url"],
                    "content": content,
                }
                write_dual(row, writer, fh)
                done.add(it["url"])
                await asyncio.sleep(1.2)

        await browser.close()
    fh.close()
    print("🏁 全部完成！")


if __name__ == "__main__":
    asyncio.run(crawl_all())
