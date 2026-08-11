import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
# =========================================================
# SETTINGS
# =========================================================
BASE_URL = "https://www.mlb.com"
NEWS_URL = "https://www.mlb.com/phillies/news"
OUTPUT_FILE = "data/news.json"
DAYS = 7
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
# =========================================================
# HTTP
# =========================================================
def get_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.text
# =========================================================
# URL NORMALIZE
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
    return url.rstrip("/")
# =========================================================
# PHILLIES ARTICLE CHECK
# =========================================================
def is_phillies_article(url):
    if not url:
        return False
    if not url.startswith(BASE_URL):
        return False
    if "/phillies/news/" not in url:
        return False
    excluded = (
        "/video/",
        "/gallery/",
        "/photos/",
    )
    for value in excluded:
        if value in url:
            return False
    return True
# =========================================================
# COLLECT ARTICLE URLS
# =========================================================
def collect_article_urls():
    print("MLB.com Phillies News を取得しています...")
    html = get_html(
        NEWS_URL
    )
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    urls = set()
    for link in soup.find_all(
        "a",
        href=True
    ):
        url = normalize_url(
            link.get("href")
        )
        if is_phillies_article(url):
            urls.add(url)
    return sorted(urls)
# =========================================================
# JSON-LD
# =========================================================
def get_jsonld(soup):
    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )
    for script in scripts:
        text = (
            script.string
            or script.get_text()
        )
        if not text:
            continue
        try:
            data = json.loads(
                text
            )
        except Exception:
            continue
        if isinstance(
            data,
            dict
        ):
            yield data
        elif isinstance(
            data,
            list
        ):
            for item in data:
                if isinstance(
                    item,
                    dict
                ):
                    yield item
        elif isinstance(
            data,
            dict
        ) and "@graph" in data:
            for item in data["@graph"]:
                if isinstance(
                    item,
                    dict
                ):
                    yield item
# =========================================================
# DATETIME NORMALIZE
# =========================================================
def normalize_datetime(value):
    if not value:
        return ""
    value = str(value).strip()
    try:
        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )
        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )
        return dt.astimezone(
            timezone.utc
        ).isoformat()
    except Exception:
        pass
    return value
# =========================================================
# ARTICLE PUBLISHED DATE
# =========================================================
def extract_published_at(
    soup,
    html
):
    # -----------------------------------------------------
    # 1. JSON-LD datePublished
    # -----------------------------------------------------
    for data in get_jsonld(soup):
        date = data.get(
            "datePublished"
        )
        if date:
            return normalize_datetime(
                date
            )
    # -----------------------------------------------------
    # 2. article:published_time
    # -----------------------------------------------------
    meta = soup.find(
        "meta",
        attrs={
            "property":
                "article:published_time"
        }
    )
    if meta:
        value = meta.get(
            "content"
        )
        if value:
            return normalize_datetime(
                value
            )
    # -----------------------------------------------------
    # 3. <time datetime="">
    # -----------------------------------------------------
    for tag in soup.find_all(
        "time"
    ):
        value = tag.get(
            "datetime"
        )
        if value:
            return normalize_datetime(
                value
            )
    # -----------------------------------------------------
    # 4. HTML内のdatePublished
    # -----------------------------------------------------
    patterns = [
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"publishedTime"\s*:\s*"([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(
            pattern,
            html
        )
        if match:
            return normalize_datetime(
                match.group(1)
            )
    return ""
# =========================================================
# ARTICLE TITLE
# =========================================================
def extract_title(
    soup
):
    # -----------------------------------------------------
    # OG TITLE
    # -----------------------------------------------------
    meta = soup.find(
        "meta",
        attrs={
            "property":
                "og:title"
        }
    )
    if meta:
        title = meta.get(
            "content"
        )
        if title:
            return title.strip()
    # -----------------------------------------------------
    # JSON-LD
    # -----------------------------------------------------
    for data in get_jsonld(soup):
        title = data.get(
            "headline"
        )
        if title:
            return str(
                title
            ).strip()
    # -----------------------------------------------------
    # HTML TITLE
    # -----------------------------------------------------
    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True
        )
        if title:
            return title
    return ""
# =========================================================
# ARTICLE
# =========================================================
def get_article(url):
    try:
        html = get_html(
            url
        )
    except Exception as error:
        print(
            "記事取得失敗:",
            url
        )
        print(
            error
        )
        return None
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    title = extract_title(
        soup
    )
    published_at = extract_published_at(
        soup,
        html
    )
    # -----------------------------------------------------
    # 公開日時がない記事は保存しない
    # -----------------------------------------------------
    if not published_at:
        print(
            "公開日時を取得できないため除外:",
            url
        )
        return None
    if not title:
        print(
            "タイトルを取得できないため除外:",
            url
        )
        return None
    return {
        "title": title,
        "published_at": published_at,
        "source": "MLB.com",
        "url": normalize_url(url),
        "title_ja": ""
    }
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
            data = json.load(
                file
            )
        if isinstance(
            data,
            list
        ):
            return data
    except Exception as error:
        print(
            "既存news.jsonの読み込み失敗:",
            error
        )
    return []
# =========================================================
# PARSE DATETIME
# =========================================================
def parse_datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )
        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )
        return dt.astimezone(
            timezone.utc
        )
    except Exception:
        return None
# =========================================================
# FILTER LAST 7 DAYS
# =========================================================
def filter_last_7_days(
    articles
):
    now = datetime.now(
        timezone.utc
    )
    cutoff = (
        now -
        timedelta(
            days=DAYS
        )
    )
    result = []
    for article in articles:
        published = parse_datetime(
            article.get(
                "published_at"
            )
        )
        if not published:
            continue
        if (
            cutoff
            <= published
            <= now
        ):
            result.append(
                article
            )
    return result
# =========================================================
# MERGE
# =========================================================
def merge_articles(
    existing,
    fetched
):
    articles = {}
    # -----------------------------------------------------
    # Existing
    # -----------------------------------------------------
    for article in existing:
        url = normalize_url(
            article.get(
                "url"
            )
        )
        if not url:
            continue
        articles[url] = {
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
    # New
    # -----------------------------------------------------
    for article in fetched:
        url = normalize_url(
            article.get(
                "url"
            )
        )
        if not url:
            continue
        if url in articles:
            if article.get(
                "title"
            ):
                articles[url][
                    "title"
                ] = article[
                    "title"
                ]
            if article.get(
                "published_at"
            ):
                articles[url][
                    "published_at"
                ] = article[
                    "published_at"
                ]
        else:
            articles[url] = article
    return list(
        articles.values()
    )
# =========================================================
# TRANSLATE TITLE
# =========================================================
def translate_title(
    title
):
    endpoint = (
        "https://translate.googleapis.com/"
        "translate_a/single"
    )
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "ja",
        "dt": "t",
        "q": title,
    }
    try:
        response = requests.get(
            endpoint,
            params=params,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        translated = ""
        if (
            isinstance(data, list)
            and len(data) > 0
            and isinstance(
                data[0],
                list
            )
        ):
            for part in data[0]:
                if (
                    isinstance(
                        part,
                        list
                    )
                    and len(part) > 0
                    and part[0]
                ):
                    translated += str(
                        part[0]
                    )
        return translated.strip()
    except Exception as error:
        print(
            "日本語翻訳失敗:",
            error
        )
        return ""
# =========================================================
# TRANSLATE NEW TITLES
# =========================================================
def translate_new_titles(
    articles
):
    targets = []
    for article in articles:
        if (
            article.get(
                "title"
            )
            and not article.get(
                "title_ja"
            )
        ):
            targets.append(
                article
            )
    print(
        "日本語訳対象:",
        len(targets),
        "件"
    )
    for index, article in enumerate(
        targets,
        start=1
    ):
        print(
            f"翻訳 {index}/{len(targets)}:",
            article["title"]
        )
        translated = translate_title(
            article["title"]
        )
        if translated:
            article[
                "title_ja"
            ] = translated
        time.sleep(
            0.3
        )
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
    print(
        "========================================"
    )
    print(
        "PHILLIES READER NEWS UPDATE"
    )
    print(
        "対象期間：過去7日間"
    )
    print(
        "========================================"
    )
    # -----------------------------------------------------
    # 1. MLB.comから記事URL取得
    # -----------------------------------------------------
    try:
        urls = collect_article_urls()
    except Exception as error:
        print(
            "ニュース一覧取得失敗:"
        )
        print(
            error
        )
        return
    print(
        "記事URL候補:",
        len(urls)
    )
    # -----------------------------------------------------
    # 2. 記事情報取得
    # -----------------------------------------------------
    fetched = []
    for index, url in enumerate(
        urls,
        start=1
    ):
        print(
            f"記事取得 {index}/{len(urls)}"
        )
        article = get_article(
            url
        )
        if article:
            fetched.append(
                article
            )
        time.sleep(
            0.25
        )
    print(
        "記事取得成功:",
        len(fetched)
    )
    # -----------------------------------------------------
    # 3. Existing
    # -----------------------------------------------------
    existing = load_existing()
    # -----------------------------------------------------
    # 4. Merge
    # -----------------------------------------------------
    merged = merge_articles(
        existing,
        fetched
    )
    # -----------------------------------------------------
    # 5. 7日以内だけ残す
    # -----------------------------------------------------
    articles = filter_last_7_days(
        merged
    )
    print(
        "過去7日以内:",
        len(articles)
    )
    # -----------------------------------------------------
    # 6. 日本語タイトル
    # -----------------------------------------------------
    articles = translate_new_titles(
        articles
    )
    # -----------------------------------------------------
    # 7. 新しい順
    # -----------------------------------------------------
    articles.sort(
        key=lambda article:
            parse_datetime(
                article.get(
                    "published_at"
                )
            ) or datetime.min.replace(
                tzinfo=timezone.utc
            ),
        reverse=True
    )
    # -----------------------------------------------------
    # 8. Save
    # -----------------------------------------------------
    save_articles(
        articles
    )
    print(
        "========================================"
    )
    print(
        "UPDATE COMPLETE"
    )
    print(
        "記事数:",
        len(articles)
    )
    print(
        "保存:",
        OUTPUT_FILE
    )
    print(
        "========================================"
    )
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
