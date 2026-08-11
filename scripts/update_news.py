import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
# =========================================================
# PHILLIES READER
# update_news.py
#
# MLB.com Phillies News
#
# 取得項目
#   1. 記事タイトル
#   2. 公開日時
#   3. 公開元
#   4. 記事URL
#   5. 日本語訳タイトル
#
# 取得期間
#   実行時点から過去7日間
#
# 公開日時を取得できない記事
#   保存しない
#
# 7日より古い記事
#   news.jsonから削除
#
# =========================================================
# =========================================================
# SETTINGS
# =========================================================
BASE_URL = "https://www.mlb.com"
NEWS_URL = (
    "https://www.mlb.com/phillies/news"
)
OUTPUT_FILE = (
    "data/news.json"
)
KEEP_DAYS = 7
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 0.25
TRANSLATE_SLEEP_SECONDS = 0.35
# =========================================================
# HTTP HEADERS
# =========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "en-US,en;q=0.9"
    ),
}
# =========================================================
# HTTP GET
# =========================================================
def get_html(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
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
        url,
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
    if not url.startswith(
        BASE_URL
    ):
        return False
    if "/phillies/news/" not in url:
        return False
    excluded_paths = (
        "/video/",
        "/gallery/",
        "/photos/",
    )
    for path in excluded_paths:
        if path in url:
            return False
    return True
# =========================================================
# COLLECT ARTICLE URLS
# =========================================================
def collect_article_urls():
    print(
        "MLB.com Phillies News を取得中..."
    )
    html = get_html(
        NEWS_URL
    )
    soup = BeautifulSoup(
        html,
        "html.parser",
    )
    urls = set()
    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = link.get(
            "href"
        )
        url = normalize_url(
            href
        )
        if is_phillies_article(
            url
        ):
            urls.add(url)
    return sorted(urls)
# =========================================================
# JSON-LD
# =========================================================
def iter_jsonld(soup):
    scripts = soup.find_all(
        "script",
        type="application/ld+json",
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
            dict,
        ):
            yield data
            graph = data.get(
                "@graph"
            )
            if isinstance(
                graph,
                list,
            ):
                for item in graph:
                    if isinstance(
                        item,
                        dict,
                    ):
                        yield item
        elif isinstance(
            data,
            list,
        ):
            for item in data:
                if isinstance(
                    item,
                    dict,
                ):
                    yield item
# =========================================================
# DATETIME PARSER
# =========================================================
def parse_datetime(value):
    if not value:
        return None
    value = str(
        value
    ).strip()
    if not value:
        return None
    # ISO 8601
    try:
        normalized = value
        if normalized.endswith(
            "Z"
        ):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )
        dt = datetime.fromisoformat(
            normalized
        )
        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )
        return dt.astimezone(
            timezone.utc
        )
    except Exception:
        pass
    # RFC 3339等に対応
    formats = (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(
                value,
                fmt,
            )
            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )
            return dt.astimezone(
                timezone.utc
            )
        except Exception:
            continue
    return None
# =========================================================
# DATETIME NORMALIZE
# =========================================================
def normalize_datetime(value):
    dt = parse_datetime(
        value
    )
    if not dt:
        return ""
    return dt.isoformat()
# =========================================================
# EXTRACT PUBLISHED DATETIME
# =========================================================
def extract_published_at(
    soup,
    html,
):
    # -----------------------------------------------------
    # 1. JSON-LD datePublished
    # -----------------------------------------------------
    for data in iter_jsonld(
        soup
    ):
        value = data.get(
            "datePublished"
        )
        if value:
            normalized = (
                normalize_datetime(
                    value
                )
            )
            if normalized:
                return normalized
    # -----------------------------------------------------
    # 2. article:published_time
    # -----------------------------------------------------
    meta = soup.find(
        "meta",
        attrs={
            "property":
                "article:published_time"
        },
    )
    if meta:
        value = meta.get(
            "content"
        )
        normalized = (
            normalize_datetime(
                value
            )
        )
        if normalized:
            return normalized
    # -----------------------------------------------------
    # 3. meta[name=publishdate]
    # -----------------------------------------------------
    meta_names = (
        "publishdate",
        "published",
        "published_date",
        "date",
        "datepublished",
    )
    for name in meta_names:
        meta = soup.find(
            "meta",
            attrs={
                "name": name
            },
        )
        if meta:
            value = meta.get(
                "content"
            )
            normalized = (
                normalize_datetime(
                    value
                )
            )
            if normalized:
                return normalized
    # -----------------------------------------------------
    # 4. time[datetime]
    # -----------------------------------------------------
    for tag in soup.find_all(
        "time"
    ):
        value = tag.get(
            "datetime"
        )
        normalized = (
            normalize_datetime(
                value
            )
        )
        if normalized:
            return normalized
    # -----------------------------------------------------
    # 5. HTML内 datePublished
    # -----------------------------------------------------
    patterns = (
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"publishedTime"\s*:\s*"([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
        r'"published_at"\s*:\s*"([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(
            pattern,
            html,
            re.IGNORECASE,
        )
        if match:
            normalized = (
                normalize_datetime(
                    match.group(1)
                )
            )
            if normalized:
                return normalized
    return ""
# =========================================================
# EXTRACT TITLE
# =========================================================
def extract_title(soup):
    # -----------------------------------------------------
    # 1. JSON-LD headline
    # -----------------------------------------------------
    for data in iter_jsonld(
        soup
    ):
        headline = data.get(
            "headline"
        )
        if isinstance(
            headline,
            str,
        ):
            headline = headline.strip()
            if headline:
                return headline
    # -----------------------------------------------------
    # 2. og:title
    # -----------------------------------------------------
    meta = soup.find(
        "meta",
        attrs={
            "property": "og:title"
        },
    )
    if meta:
        title = meta.get(
            "content"
        )
        if title:
            return title.strip()
    # -----------------------------------------------------
    # 3. twitter:title
    # -----------------------------------------------------
    meta = soup.find(
        "meta",
        attrs={
            "name": "twitter:title"
        },
    )
    if meta:
        title = meta.get(
            "content"
        )
        if title:
            return title.strip()
    # -----------------------------------------------------
    # 4. HTML title
    # -----------------------------------------------------
    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True,
        )
        if title:
            return title
    return ""
# =========================================================
# GET ARTICLE
# =========================================================
def get_article(url):
    try:
        html = get_html(
            url
        )
    except Exception as error:
        print(
            "記事取得失敗:",
            url,
        )
        print(
            "ERROR:",
            error,
        )
        return None
    soup = BeautifulSoup(
        html,
        "html.parser",
    )
    title = extract_title(
        soup
    )
    published_at = (
        extract_published_at(
            soup,
            html,
        )
    )
    # -----------------------------------------------------
    # 公開日時がない記事は保存しない
    # -----------------------------------------------------
    if not published_at:
        print(
            "公開日時なし → 除外:",
            url,
        )
        return None
    # -----------------------------------------------------
    # タイトルがない記事も保存しない
    # -----------------------------------------------------
    if not title:
        print(
            "タイトルなし → 除外:",
            url,
        )
        return None
    return {
        "title": title,
        "published_at": published_at,
        "source": "MLB.com",
        "url": normalize_url(
            url
        ),
        "title_ja": "",
    }
# =========================================================
# LOAD NEWS.JSON
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
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )
        if isinstance(
            data,
            list,
        ):
            return data
        # もし {"articles": [...]} 型だった場合
        if isinstance(
            data,
            dict,
        ):
            articles = data.get(
                "articles"
            )
            if isinstance(
                articles,
                list,
            ):
                return articles
    except Exception as error:
        print(
            "news.json読み込み失敗:",
            error,
        )
    return []
# =========================================================
# MERGE ARTICLES
# =========================================================
def merge_articles(
    existing,
    fetched,
):
    articles = {}
    # -----------------------------------------------------
    # Existing
    # -----------------------------------------------------
    for article in existing:
        if not isinstance(
            article,
            dict,
        ):
            continue
        url = normalize_url(
            article.get(
                "url"
            )
        )
        if not url:
            continue
        title = article.get(
            "title",
            "",
        )
        published_at = (
            article.get(
                "published_at",
                "",
            )
        )
        title_ja = article.get(
            "title_ja",
            "",
        )
        articles[url] = {
            "title": title,
            "published_at":
                published_at,
            "source": "MLB.com",
            "url": url,
            "title_ja": title_ja,
        }
    # -----------------------------------------------------
    # Fetched
    # -----------------------------------------------------
    for article in fetched:
        if not isinstance(
            article,
            dict,
        ):
            continue
        url = normalize_url(
            article.get(
                "url"
            )
        )
        if not url:
            continue
        if url in articles:
            # 既存の日本語訳は保持
            old_translation = (
                articles[url].get(
                    "title_ja",
                    "",
                )
            )
            articles[url] = {
                "title":
                    article.get(
                        "title",
                        "",
                    ),
                "published_at":
                    article.get(
                        "published_at",
                        "",
                    ),
                "source":
                    "MLB.com",
                "url":
                    url,
                "title_ja":
                    old_translation,
            }
        else:
            articles[url] = {
                "title":
                    article.get(
                        "title",
                        "",
                    ),
                "published_at":
                    article.get(
                        "published_at",
                        "",
                    ),
                "source":
                    "MLB.com",
                "url":
                    url,
                "title_ja":
                    article.get(
                        "title_ja",
                        "",
                    ),
            }
    return list(
        articles.values()
    )
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
        now
        - timedelta(
            days=KEEP_DAYS
        )
    )
    result = []
    for article in articles:
        published = parse_datetime(
            article.get(
                "published_at"
            )
        )
        # 日時がない記事は除外
        if not published:
            continue
        # 未来の日付も除外
        if published > now:
            continue
        # 7日より古い記事を除外
        if published < cutoff:
            continue
        result.append(
            article
        )
    return result
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
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if (
            not isinstance(
                data,
                list,
            )
            or len(data) == 0
            or not isinstance(
                data[0],
                list,
            )
        ):
            return ""
        translated = ""
        for item in data[0]:
            if (
                isinstance(
                    item,
                    list,
                )
                and len(item) > 0
                and item[0]
            ):
                translated += str(
                    item[0]
                )
        return translated.strip()
    except Exception as error:
        print(
            "翻訳失敗:",
            error,
        )
        return ""
# =========================================================
# TRANSLATE TITLES
# =========================================================
def translate_titles(
    articles
):
    targets = []
    for article in articles:
        title = article.get(
            "title",
            "",
        )
        title_ja = article.get(
            "title_ja",
            "",
        )
        if title and not title_ja:
            targets.append(
                article
            )
    print(
        "日本語訳対象:",
        len(targets),
        "件",
    )
    for index, article in enumerate(
        targets,
        start=1,
    ):
        print(
            f"日本語訳 {index}/{len(targets)}"
        )
        print(
            article["title"]
        )
        translated = (
            translate_title(
                article["title"]
            )
        )
        if translated:
            article[
                "title_ja"
            ] = translated
        time.sleep(
            TRANSLATE_SLEEP_SECONDS
        )
    return articles
# =========================================================
# SORT
# =========================================================
def sort_articles(
    articles
):
    def sort_key(article):
        dt = parse_datetime(
            article.get(
                "published_at"
            )
        )
        if dt:
            return dt
        return datetime.min.replace(
            tzinfo=timezone.utc
        )
    articles.sort(
        key=sort_key,
        reverse=True,
    )
    return articles
# =========================================================
# SAVE
# =========================================================
def save_articles(
    articles
):
    directory = os.path.dirname(
        OUTPUT_FILE
    )
    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            articles,
            file,
            ensure_ascii=False,
            indent=2,
        )
    print(
        "保存完了:",
        OUTPUT_FILE,
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
        "MLB.com NEWS UPDATE"
    )
    print(
        "========================================"
    )
    print(
        "取得期間: 過去7日間"
    )
    # -----------------------------------------------------
    # 1. URL収集
    # -----------------------------------------------------
    try:
        urls = collect_article_urls()
    except Exception as error:
        print()
        print(
            "MLB.comニュース一覧の取得に失敗しました。"
        )
        print(
            error
        )
        return
    print()
    print(
        "記事URL候補:",
        len(urls),
    )
    # -----------------------------------------------------
    # 2. 記事取得
    # -----------------------------------------------------
    fetched = []
    for index, url in enumerate(
        urls,
        start=1,
    ):
        print(
            f"[{index}/{len(urls)}] {url}"
        )
        article = get_article(
            url
        )
        if article:
            fetched.append(
                article
            )
        time.sleep(
            SLEEP_SECONDS
        )
    print()
    print(
        "取得成功:",
        len(fetched),
        "件",
    )
    # -----------------------------------------------------
    # 3. 既存データ
    # -----------------------------------------------------
    existing = load_existing()
    print(
        "既存記事:",
        len(existing),
        "件",
    )
    # -----------------------------------------------------
    # 4. 統合
    # -----------------------------------------------------
    merged = merge_articles(
        existing,
        fetched,
    )
    print(
        "統合後:",
        len(merged),
        "件",
    )
    # -----------------------------------------------------
    # 5. 過去7日間に限定
    # -----------------------------------------------------
    articles = filter_last_7_days(
        merged
    )
    print(
        "過去7日以内:",
        len(articles),
        "件",
    )
    # -----------------------------------------------------
    # 6. 日本語タイトル
    # -----------------------------------------------------
    articles = translate_titles(
        articles
    )
    # -----------------------------------------------------
    # 7. 新しい順
    # -----------------------------------------------------
    articles = sort_articles(
        articles
    )
    # -----------------------------------------------------
    # 8. 保存
    # -----------------------------------------------------
    save_articles(
        articles
    )
    # -----------------------------------------------------
    # 9. 完了
    # -----------------------------------------------------
    print()
    print(
        "========================================"
    )
    print(
        "UPDATE COMPLETE"
    )
    print(
        f"最終記事数: {len(articles)}"
    )
    print(
        "========================================"
    )
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
