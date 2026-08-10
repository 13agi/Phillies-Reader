import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
# =========================================================
# CONFIG
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "news.json"
DAYS = 7
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 20
# =========================================================
# SOURCE CONFIG
#
# 「Phillies専用ページ」そのものを取得する。
# キーワードによる記事判定は行わない。
# =========================================================
SOURCES = [
    {
        "name": "MLB.com",
        "url": "https://www.mlb.com/phillies/news",
        "domain": "mlb.com",
    },
    {
        "name": "NBC Sports Philadelphia",
        "url": "https://www.nbcsportsphiladelphia.com/mlb/philadelphia-phillies/",
        "domain": "nbcsportsphiladelphia.com",
    },
    {
        "name": "CBS Sports",
        "url": "https://www.cbssports.com/mlb/teams/phi/philadelphia-phillies/",
        "domain": "cbssports.com",
    },
    {
        "name": "ESPN",
        "url": "https://www.espn.com/mlb/team/_/name/phi/philadelphia-phillies",
        "domain": "espn.com",
    },
]
# =========================================================
# SESSION
# =========================================================
session = requests.Session()
session.headers.update(HEADERS)
# =========================================================
# HELPERS
# =========================================================
def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value)
    return value.strip()
def normalize_url(url):
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        return url
    parsed = urlparse(url)
    if not parsed.scheme:
        return ""
    # fragment削除
    return url.split("#")[0]
def is_http_url(url):
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")
def fetch_html(url):
    try:
        response = session.get(
            url,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.text
    except Exception as error:
        print(
            f"[ERROR] fetch failed: {url}"
        )
        print(error)
        return None
# =========================================================
# DATE PARSER
# =========================================================
def parse_datetime(value):
    if not value:
        return None
    value = value.strip()
    # ISO 8601
    try:
        normalized = value.replace(
            "Z",
            "+00:00"
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
    # Common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(
                value,
                fmt
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
# JSON-LD DATE
# =========================================================
def get_jsonld_dates(soup):
    dates = []
    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):
        try:
            data = json.loads(
                script.string or
                script.get_text()
            )
        except Exception:
            continue
        objects = []
        if isinstance(data, list):
            objects.extend(data)
        elif isinstance(data, dict):
            if "@graph" in data:
                graph = data["@graph"]
                if isinstance(
                    graph,
                    list
                ):
                    objects.extend(graph)
            objects.append(data)
        for obj in objects:
            if not isinstance(
                obj,
                dict
            ):
                continue
            for key in (
                "datePublished",
                "dateCreated",
                "dateModified",
            ):
                value = obj.get(key)
                dt = parse_datetime(
                    value
                )
                if dt:
                    dates.append(dt)
    if not dates:
        return None
    return min(dates)
# =========================================================
# META DATE
# =========================================================
def get_meta_date(soup):
    candidates = [
        (
            "property",
            "article:published_time"
        ),
        (
            "property",
            "article:modified_time"
        ),
        (
            "name",
            "date"
        ),
        (
            "name",
            "pubdate"
        ),
        (
            "name",
            "publish-date"
        ),
        (
            "itemprop",
            "datePublished"
        ),
    ]
    for attr, value in candidates:
        tag = soup.find(
            "meta",
            attrs={
                attr: value
            }
        )
        if not tag:
            continue
        content = (
            tag.get("content")
            or ""
        )
        dt = parse_datetime(
            content
        )
        if dt:
            return dt
    return None
# =========================================================
# ARTICLE PAGE DATE
# =========================================================
def get_article_date(url):
    html = fetch_html(url)
    if not html:
        return None
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    date = get_jsonld_dates(
        soup
    )
    if date:
        return date
    return get_meta_date(
        soup
    )
# =========================================================
# TITLE
# =========================================================
def get_link_title(link):
    title = clean_text(
        link.get_text(
            " ",
            strip=True
        )
    )
    if title:
        return title
    for attr in (
        "aria-label",
        "title",
    ):
        value = clean_text(
            link.get(attr)
        )
        if value:
            return value
    return ""
# =========================================================
# URL FILTER
# =========================================================
def valid_article_url(
    url,
    source
):
    if not is_http_url(url):
        return False
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if source["domain"] not in domain:
        return False
    return True
# =========================================================
# GENERIC LINK EXTRACTION
#
# 各媒体の「Phillies専用ページ」から
# リンクを取得する。
#
# 記事タイトルのキーワード判定はしない。
# =========================================================
def extract_links(
    html,
    source
):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    results = []
    seen = set()
    base_url = source["url"]
    for link in soup.find_all(
        "a",
        href=True
    ):
        href = normalize_url(
            urljoin(
                base_url,
                link["href"]
            )
        )
        if not valid_article_url(
            href,
            source
        ):
            continue
        title = get_link_title(
            link
        )
        if not title:
            continue
        # ナビゲーション等を最低限除外
        if len(title) < 8:
            continue
        if len(title) > 300:
            continue
        key = (
            href.lower()
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "title": title,
                "url": href,
            }
        )
    return results
# =========================================================
# SOURCE SCRAPER
# =========================================================
def scrape_source(source):
    print(
        f"\n[INFO] {source['name']}"
    )
    html = fetch_html(
        source["url"]
    )
    if not html:
        return []
    links = extract_links(
        html,
        source
    )
    print(
        f"[INFO] links found: {len(links)}"
    )
    articles = []
    now = datetime.now(
        timezone.utc
    )
    cutoff = (
        now -
        timedelta(
            days=DAYS
        )
    )
    for index, item in enumerate(
        links
    ):
        # 取りすぎ防止
        if index >= 80:
            break
        print(
            f"[INFO] checking "
            f"{index + 1}/{min(len(links), 80)}"
        )
        published = get_article_date(
            item["url"]
        )
        if not published:
            continue
        # 直近7日だけ
        if published < cutoff:
            continue
        # 未来日時の異常データは除外
        if published > now + timedelta(
            minutes=10
        ):
            continue
        articles.append(
            {
                "title": item["title"],
                "url": item["url"],
                "source": source["name"],
                "published": published.isoformat(),
            }
        )
        # サーバー負荷を抑える
        time.sleep(
            0.15
        )
    return articles
# =========================================================
# DEDUPLICATE
# =========================================================
def deduplicate(
    articles
):
    unique = {}
    for article in articles:
        url = article.get(
            "url",
            ""
        ).strip()
        if not url:
            continue
        key = url.lower()
        if key not in unique:
            unique[key] = article
            continue
        # 同一URLなら
        # より情報が揃っている方を優先
        old = unique[key]
        if (
            not old.get("published")
            and
            article.get("published")
        ):
            unique[key] = article
    return list(
        unique.values()
    )
# =========================================================
# SORT
# =========================================================
def sort_articles(
    articles
):
    return sorted(
        articles,
        key=lambda x:
            x.get(
                "published",
                ""
            ),
        reverse=True
    )
# =========================================================
# SAVE
# =========================================================
def save_news(
    articles
):
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    payload = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),
        "days": DAYS,
        "articles": articles,
    }
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2
        )
    print(
        f"\n[SAVED] {OUTPUT_FILE}"
    )
    print(
        f"[ARTICLES] {len(articles)}"
    )
# =========================================================
# MAIN
# =========================================================
def main():
    print(
        "========================================"
    )
    print(
        " Phillies News Updater"
    )
    print(
        " Last 7 Days"
    )
    print(
        "========================================"
    )
    all_articles = []
    for source in SOURCES:
        try:
            articles = scrape_source(
                source
            )
            all_articles.extend(
                articles
            )
        except Exception as error:
            print(
                f"[ERROR] "
                f"{source['name']} failed"
            )
            print(error)
    all_articles = deduplicate(
        all_articles
    )
    all_articles = sort_articles(
        all_articles
    )
    save_news(
        all_articles
    )
    print(
        "\n[DONE]"
    )
if __name__ == "__main__":
    main()
