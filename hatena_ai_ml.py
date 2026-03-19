"""
はてなブックマーク AI・機械学習カテゴリ 人気記事取得スクリプト

対象タグ: 機械学習, AI, 人工知能, 深層学習, ChatGPT, LLM, 生成AI など
取得方法: はてなブックマーク タグ別 人気エントリー RSS (RDF/RSS 1.0)
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import time


# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
AI_ML_TAGS = [
    "機械学習",
    "AI",
    "人工知能",
    "深層学習",
    "ChatGPT",
    "LLM",
    "生成AI",
    "OpenAI",
    "自然言語処理",
]

MAX_PER_TAG    = 40     # タグごとに取得する最大件数（popular順で最大40件）
MIN_BOOKMARKS  = 20     # 最低ブックマーク数（これ未満は除外）
REQUEST_INTERVAL = 0.5  # リクエスト間隔（秒）
TOP_N = 50              # 最終的に表示する上位件数

RSS_URL = "https://b.hatena.ne.jp/t/{tag}?mode=rss&sort=popular"

# RSS 1.0 (RDF) 名前空間
RSS_NS    = "http://purl.org/rss/1.0/"
HATENA_NS = "http://www.hatena.ne.jp/info/xmlns#"
DC_NS     = "http://purl.org/dc/elements/1.1/"

JST = timezone(timedelta(hours=9))


# ─────────────────────────────────────────────
# データ構造
# ─────────────────────────────────────────────
@dataclass
class Article:
    title: str
    url: str
    bookmarks: int
    description: str
    tags: list = field(default_factory=list)
    published: str = ""

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url == other.url


# ─────────────────────────────────────────────
# RSS 取得・パース
# ─────────────────────────────────────────────
def fetch_popular(tag: str) -> list:
    url = RSS_URL.format(tag=urllib.parse.quote(tag))
    articles = []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Python hatena-ai-ml-fetcher/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
    except Exception as e:
        print(f"  [ERROR] タグ「{tag}」の取得失敗: {e}")
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"  [ERROR] タグ「{tag}」のXMLパース失敗: {e}")
        return []

    # RSS 1.0 の item 要素は rdf:RDF 直下に並ぶ
    for item in root.findall(f"{{{RSS_NS}}}item")[:MAX_PER_TAG]:
        title_el = item.find(f"{{{RSS_NS}}}title")
        link_el  = item.find(f"{{{RSS_NS}}}link")
        desc_el  = item.find(f"{{{RSS_NS}}}description")
        bm_el    = item.find(f"{{{HATENA_NS}}}bookmarkcount")
        date_el  = item.find(f"{{{DC_NS}}}date")

        title       = title_el.text.strip()  if title_el is not None and title_el.text  else ""
        link        = link_el.text.strip()   if link_el  is not None and link_el.text   else ""
        description = desc_el.text.strip()   if desc_el  is not None and desc_el.text   else ""
        bookmarks   = int(bm_el.text)        if bm_el    is not None and bm_el.text     else 0
        published   = date_el.text.strip()   if date_el  is not None and date_el.text   else ""

        if not link or bookmarks < MIN_BOOKMARKS:
            continue

        articles.append(Article(
            title=title,
            url=link,
            bookmarks=bookmarks,
            description=description,
            tags=[tag],
            published=published,
        ))

    return articles


# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  はてなブックマーク AI・機械学習 人気記事取得")
    print(f"  実行日時: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S JST')}")
    print("=" * 65)

    seen: dict = {}  # url -> Article

    for tag in AI_ML_TAGS:
        print(f"[取得中] #{tag} ", end="", flush=True)
        articles = fetch_popular(tag)
        print(f"→ {len(articles)} 件")

        for art in articles:
            if art.url in seen:
                seen[art.url].bookmarks = max(seen[art.url].bookmarks, art.bookmarks)
                if tag not in seen[art.url].tags:
                    seen[art.url].tags.append(tag)
            else:
                seen[art.url] = art

        time.sleep(REQUEST_INTERVAL)

    # ブックマーク数で降順ソート、上位 TOP_N 件
    results = sorted(seen.values(), key=lambda a: a.bookmarks, reverse=True)[:TOP_N]

    print()
    print("=" * 65)
    print(f"  集計結果 TOP {TOP_N}（重複除去済み / 合計 {len(seen)} 件）")
    print("=" * 65)

    for i, art in enumerate(results, 1):
        tags_str = "  ".join(f"#{t}" for t in art.tags)
        desc = (art.description[:70] + "…") if len(art.description) > 70 else art.description

        pub = ""
        if art.published:
            try:
                dt = datetime.fromisoformat(art.published.replace("Z", "+00:00"))
                pub = dt.astimezone(JST).strftime("%Y-%m-%d")
            except Exception:
                pub = art.published[:10]

        print(f"\n[{i:>3}] ★{art.bookmarks:>4}  {art.title}")
        print(f"       URL  : {art.url}")
        print(f"       タグ : {tags_str}")
        if pub:
            print(f"       日付 : {pub}")
        if desc:
            print(f"       概要 : {desc}")

    # CSV 保存
    csv_path = "hatena_ai_ml_result.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("順位,ブックマーク数,タイトル,URL,タグ,日付\n")
        for i, art in enumerate(results, 1):
            title = art.title.replace('"', '""')
            tags  = " / ".join(art.tags)
            pub = art.published[:10] if art.published else ""
            f.write(f'{i},{art.bookmarks},"{title}",{art.url},"{tags}",{pub}\n')

    print(f"\n→ CSV保存: {csv_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
