import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
# =========================================================
# SETTINGS
# =========================================================
BASE_URL = "https://www.mlb.com"
NEWS_URL = "https://www.mlb.com/phillies/news"
OUTPUT_FILE = "data/news.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 30
# 一度に翻訳するタイトル数
TRANSLATION_BATCH_SIZE = 20
# =========================================================
# HTTP
# =========================================================
def fetch_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.text
# =========================================================
# URL
# =========================================================
def normalize_url(url):
    if not url:
        return ""
    url = urljoin(
        BASE_URL,
        url
    )
    url = url.split("?")[0]
    url = url.split("#")[0]
    if url.endswith("/"):
        url = url[:-1]
    return url
def is_article_url(url):
    if not url:
        return False
    if not url.startswith(BASE_URL):
        return False
    if "/phillies/news/" not in url:
        return False
    excluded = [
        "/video/",
        "/gallery/",
        "/photos/",
        "/schedule/",
        "/stats/"
    ]
    for item in excluded:
        if item in url:
            return False
    return True
# =========================================================
# JSON-LD
# =========================================================
def get_jsonld(soup):
    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )
    for script in scripts:
        raw = (
            script.string
            or script.get_text()
        )
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            yield data
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
# =========================================================
# ARTICLE
# =========================================================
def get_article(url):
    try:
        html = fetch_html(url)
    except Exception as error:
        print(
            "ARTICLE FETCH ERROR:",
            url,
            error
        )
        return None
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    title = ""
    published_at = ""
    # -----------------------------------------------------
    # JSON-LD
    # -----------------------------------------------------
    for data in get_jsonld(soup):
        if not title:
            value = data.get(
                "headline"
            )
            if isinstance(
                value,
                str
            ):
                title = value.strip()
        if not published_at:
            value = data.get(
                "datePublished"
            )
            if isinstance(
                value,
                str
            ):
                published_at = value.strip()
    # -----------------------------------------------------
    # OG TITLE
    # -----------------------------------------------------
    if not title:
        meta = soup.find(
            "meta",
            property="og:title"
        )
        if meta:
            title = (
                meta.get(
                    "content",
                    ""
                )
                .strip()
            )
    # -----------------------------------------------------
    # HTML TITLE
    # -----------------------------------------------------
    if not title and soup.title:
        title = soup.title.get_text(
            " ",
            strip=True
        )
    # -----------------------------------------------------
    # PUBLISHED TIME
    # -----------------------------------------------------
    if not published_at:
        meta = soup.find(
            "meta",
            property="article:published_time"
        )
        if meta:
            published_at = (
                meta.get(
                    "content",
                    ""
                )
                .strip()
            )
    # -----------------------------------------------------
    # TIME TAG
    # -----------------------------------------------------
    if not published_at:
        for tag in soup.find_all("time"):
            value = tag.get(
                "datetime"
            )
            if value:
                published_at = value.strip()
                break
    # -----------------------------------------------------
    # RAW FALLBACK
    # -----------------------------------------------------
    if not published_at:
        match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"',
            html
        )
        if match:
            published_at = match.group(1)
    if not title:
        print(
            "TITLE NOT FOUND:",
            url
        )
        return None
    return {
        "title": title,
        "published_at": published_at,
        "source": "MLB.com",
        "url": url,
        "title_ja": ""
    }
# =========================================================
# DISCOVER NEWS
# =========================================================
def get_news_urls():
    html = fetch_html(
        NEWS_URL
    )
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    urls = set()
    for a in soup.find_all(
        "a",
        href=True
    ):
        href = a.get(
            "href",
            ""
        ).strip()
        url = normalize_url(
            href
        )
        if is_article_url(url):
            urls.add(url)
    return list(urls)
# =========================================================
# LOAD EXISTING
# =========================================================
def load_existing():
    if not os.path.exists(
        OUTPUT_FILE
    ):
        return []
    try:
        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)
        if isinstance(
            data,
            list
        ):
            return data
    except Exception as error:
        print(
            "NEWS JSON LOAD ERROR:",
            error
        )
    return []
# =========================================================
# MERGE
# =========================================================
def merge_articles(
    existing,
    fetched
):
    result = {}
    # -----------------------------------------------------
    # EXISTING
    # -----------------------------------------------------
    for article in existing:
        url = article.get(
            "url"
        )
        if not url:
            continue
        result[url] = {
            "title":
                article.get(
                    "title",
                    ""
                ),
            "published_at":
                article.get(
                    "published_at",
                    ""
                ),
            "source":
                "MLB.com",
            "url":
                url,
            "title_ja":
                article.get(
                    "title_ja",
                    ""
                )
        }
    # -----------------------------------------------------
    # NEW
    # -----------------------------------------------------
    for article in fetched:
        url = article.get(
            "url"
        )
        if not url:
            continue
        if url in result:
            if article.get("title"):
                result[url]["title"] = (
                    article["title"]
                )
            if article.get(
                "published_at"
            ):
                result[url][
                    "published_at"
                ] = article[
                    "published_at"
                ]
        else:
            result[url] = article
    return list(
        result.values()
    )
# =========================================================
# DATETIME
# =========================================================
def parse_datetime(value):
    if not value:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )
    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )
    except Exception:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )
# =========================================================
# GOOGLE TRANSLATE
#
# API KEY不要
# タイトルをまとめて翻訳する
# =========================================================
def translate_batch_google(
    titles
):
    if not titles:
        return []
    # Google Translateの非公式エンドポイント
    url = (
        "https://translate.googleapis.com/"
        "translate_a/single"
    )
    # 複数タイトルを一つの文章として送る。
    # タイトル間に特殊な区切り文字を入れる。
    separator = "\n<<<PHILLIES_TITLE_SEPARATOR>>>\n"
    text = separator.join(
        titles
    )
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "ja",
        "dt": "t",
        "q": text
    }
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except Exception as error:
        print(
            "TRANSLATION REQUEST ERROR:",
            error
        )
        return [
            ""
            for _ in titles
        ]
    # -----------------------------------------------------
    # Google Translate response
    # -----------------------------------------------------
    translated_parts = []
    try:
        for item in data[0]:
            if (
                isinstance(item, list)
                and len(item) >= 1
            ):
                translated_parts.append(
                    item[0]
                )
    except Exception as error:
        print(
            "TRANSLATION RESPONSE ERROR:",
            error
        )
        return [
            ""
            for _ in titles
        ]
    translated_text = "".join(
        translated_parts
    )
    # -----------------------------------------------------
    # 分割
    # -----------------------------------------------------
    translated = [
        x.strip()
        for x in translated_text.split(
            "<<<PHILLIES_TITLE_SEPARATOR>>>"
        )
    ]
    # -----------------------------------------------------
    # 件数が一致しない場合
    # -----------------------------------------------------
    if len(translated) != len(titles):
        print(
            "TRANSLATION COUNT MISMATCH:",
            len(titles),
            "->",
            len(translated)
        )
        return [
            ""
            for _ in titles
        ]
    return translated
# =========================================================
# TRANSLATE ALL NEW TITLES
# =========================================================
def translate_new_titles(
    articles
):
    # -----------------------------------------------------
    # 日本語タイトルがない記事だけ
    # -----------------------------------------------------
    targets = []
    for article in articles:
        if article.get(
            "title_ja"
        ):
            continue
        title = article.get(
            "title",
            ""
        ).strip()
        if not title:
            continue
        targets.append(
            article
        )
    if not targets:
        print(
            "No titles require translation."
        )
        return articles
    print()
    print(
        "========================================"
    )
    print(
        "BATCH TRANSLATION"
    )
    print(
        f"Titles to translate: {len(targets)}"
    )
    print(
        "========================================"
    )
    # -----------------------------------------------------
    # 20件ずつまとめて翻訳
    # -----------------------------------------------------
    for start in range(
        0,
        len(targets),
        TRANSLATION_BATCH_SIZE
    ):
        batch = targets[
            start:
            start + TRANSLATION_BATCH_SIZE
        ]
        titles = [
            article["title"]
            for article in batch
        ]
        print(
            f"Translating "
            f"{start + 1}-"
            f"{start + len(batch)}"
        )
        translated = (
            translate_batch_google(
                titles
            )
        )
        for article, japanese in zip(
            batch,
            translated
        ):
            if japanese:
                article[
                    "title_ja"
                ] = japanese
                print(
                    "EN:",
                    article["title"]
                )
                print(
                    "JA:",
                    japanese
                )
            else:
                print(
                    "Translation failed:",
                    article["title"]
                )
        # Google側への連続アクセスを少し避ける
        if (
            start + TRANSLATION_BATCH_SIZE
            < len(targets)
        ):
            time.sleep(1)
    return articles
# =========================================================
# SAVE
# =========================================================
def save_articles(
    articles
):
    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True
    )
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            articles,
            file,
            ensure_ascii=False,
            indent=2
        )
# =========================================================
# MAIN
# =========================================================
def main():
    print()
    print(
        "========================================"
    )
    print(
        "PHILLIES READER"
    )
    print(
        "MLB.COM NEWS UPDATE"
    )
    print(
        "========================================"
    )
    print()
    # =====================================================
    # 1. MLB.comから記事URLを取得
    # =====================================================
    print(
        "Searching MLB.com Phillies news..."
    )
    try:
        urls = get_news_urls()
    except Exception as error:
        print(
            "NEWS DISCOVERY ERROR:"
        )
        print(error)
        return
    print(
        f"Found {len(urls)} article candidates."
    )
    # =====================================================
    # 2. 個別記事から5項目のうち4項目を取得
    # =====================================================
    fetched_articles = []
    for index, url in enumerate(
        urls,
        start=1
    ):
        print(
            f"[{index}/{len(urls)}]"
        )
        article = get_article(
            url
        )
        if article:
            fetched_articles.append(
                article
            )
        time.sleep(
            0.25
        )
    print()
    print(
        f"Fetched {len(fetched_articles)} articles."
    )
    # =====================================================
    # 3. 既存記事と統合
    # =====================================================
    existing_articles = (
        load_existing()
    )
    articles = merge_articles(
        existing_articles,
        fetched_articles
    )
    # =====================================================
    # 4. 日本語タイトルをまとめて取得
    # =====================================================
    articles = translate_new_titles(
        articles
    )
    # =====================================================
    # 5. 公開日時順
    # =====================================================
    articles.sort(
        key=lambda article:
            parse_datetime(
                article.get(
                    "published_at",
                    ""
                )
            ),
        reverse=True
    )
    # =====================================================
    # 6. 保存
    # =====================================================
    save_articles(
        articles
    )
    print()
    print(
        "========================================"
    )
    print(
        "UPDATE COMPLETE"
    )
    print(
        f"TOTAL ARTICLES: {len(articles)}"
    )
    print(
        f"OUTPUT: {OUTPUT_FILE}"
    )
    print(
        "========================================"
    )
    print()
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
