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


# =========================================================
# HTTP
# =========================================================

def fetch_html(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
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
        "/stats/",
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

            data = json.loads(
                raw
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


# =========================================================
# ARTICLE
# =========================================================

def get_article(url):

    try:

        html = fetch_html(
            url
        )

    except Exception as error:

        print(
            "記事取得失敗:",
            error
        )

        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    title = None
    published_at = None

    # -----------------------------------------------------
    # JSON-LD
    # -----------------------------------------------------

    for data in get_jsonld(
        soup
    ):

        article_type = data.get(
            "@type"
        )

        if isinstance(
            article_type,
            list
        ):

            article_type = " ".join(
                str(x)
                for x in article_type
            )

        if article_type:

            article_type = str(
                article_type
            )

        if (
            article_type
            and
            "Article" not in article_type
            and
            "News" not in article_type
        ):

            continue

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

        for tag in soup.find_all(
            "time"
        ):

            value = tag.get(
                "datetime"
            )

            if value:

                published_at = (
                    value.strip()
                )

                break

    # -----------------------------------------------------
    # RAW HTML
    # -----------------------------------------------------

    if not published_at:

        match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"',
            html
        )

        if match:

            published_at = (
                match.group(1)
            )

    if not title:

        return None

    return {
        "title": title,
        "published_at": published_at,
        "source": "MLB.com",
        "url": url,
        "title_ja": ""
    }


# =========================================================
# NEWS URLS
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

        if is_article_url(
            url
        ):

            urls.add(
                url
            )

    return list(
        urls
    )


# =========================================================
# EXISTING DATA
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
            "既存データ読み込み失敗:",
            error
        )

    return []


# =========================================================
# MERGE
# =========================================================

def merge_articles(
    old,
    new
):

    result = {}

    for article in old:

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
                    "published_at"
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

    for article in new:

        url = article[
            "url"
        ]

        if url in result:

            result[url][
                "title"
            ] = article[
                "title"
            ]

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

def parse_datetime(
    value
):

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
# TITLE TRANSLATION
# =========================================================

def translate_title(title):

    """
    日本語タイトル生成部分。

    翻訳APIを利用する場合はここに接続する。

    現在はAPIキーが存在する場合のみ
    OpenAI APIを利用する。
    """

    api_key = os.environ.get(
        "OPENAI_API_KEY"
    )

    if not api_key:

        return ""

    try:

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization":
                    f"Bearer {api_key}",
                "Content-Type":
                    "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "あなたはMLB専門の日本語編集者です。"
                            "MLB.comの記事タイトルを自然な日本語に翻訳してください。"
                            "選手名、球団名、野球用語は正確に扱ってください。"
                            "説明や注釈は不要です。"
                            "日本語タイトルだけを返してください。"
                        )
                    },
                    {
                        "role": "user",
                        "content": title
                    }
                ]
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        translated = (
            data["choices"][0]
            ["message"]["content"]
            .strip()
        )

        return translated

    except Exception as error:

        print(
            "翻訳失敗:",
            error
        )

        return ""


# =========================================================
# TRANSLATE NEW TITLES
# =========================================================

def translate_articles(
    articles
):

    for article in articles:

        # すでに日本語訳がある場合は再翻訳しない
        if article.get(
            "title_ja"
        ):

            continue

        print(
            "翻訳:",
            article["title"]
        )

        article[
            "title_ja"
        ] = translate_title(
            article["title"]
        )

        # APIへの連続アクセスを避ける
        time.sleep(
            0.5
        )

    return articles


# =========================================================
# SAVE
# =========================================================

def save_articles(
    articles
):

    os.makedirs(
        "data",
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
        "======================================"
    )

    print(
        "PHILLIES READER"
    )

    print(
        "MLB.com NEWS UPDATE"
    )

    print(
        "======================================"
    )

    # -----------------------------------------------------
    # URL
    # -----------------------------------------------------

    print(
        "MLB.comニュースを検索しています..."
    )

    try:

        urls = get_news_urls()

    except Exception as error:

        print(
            "ニュース一覧取得失敗:"
        )

        print(
            error
        )

        return

    print(
        f"{len(urls)}件の候補を発見"
    )

    # -----------------------------------------------------
    # ARTICLES
    # -----------------------------------------------------

    articles = []

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

            articles.append(
                article
            )

        time.sleep(
            0.3
        )

    # -----------------------------------------------------
    # EXISTING
    # -----------------------------------------------------

    existing = load_existing()

    # -----------------------------------------------------
    # MERGE
    # -----------------------------------------------------

    articles = merge_articles(
        existing,
        articles
    )

    # -----------------------------------------------------
    # TRANSLATE
    # -----------------------------------------------------

    articles = translate_articles(
        articles
    )

    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    articles.sort(
        key=lambda article:
            parse_datetime(
                article.get(
                    "published_at"
                )
            ),
        reverse=True
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    save_articles(
        articles
    )

    print()
    print(
        "======================================"
    )

    print(
        "ニュース更新完了"
    )

    print(
        f"記事数: {len(articles)}"
    )

    print(
        f"保存先: {OUTPUT_FILE}"
    )

    print(
        "======================================"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
