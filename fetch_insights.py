"""
投稿済みキュー(queue/posts.json で posted: true のもの)について、
Instagram Graph APIから反応データ(いいね数・コメント数、取得できればリーチ・保存数)を取得し、
JSONで標準出力に書き出すスクリプト。

認証方式は post_to_instagram.py と同じ(Authorization: Bearer ヘッダー)。
インサイト系フィールド(reach, saved等)は権限が無いと取得できないことがあるため、
失敗しても全体は止めず、取得できた範囲のデータだけを返す。

使い方:
    python fetch_insights.py > reports/raw_insights.json
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
BASE_URL = f"https://graph.instagram.com/{API_VERSION}"
AUTH_HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"} if ACCESS_TOKEN else {}

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "queue", "posts.json")


def load_queue() -> list:
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_basic_fields(media_id: str) -> dict:
    resp = requests.get(
        f"{BASE_URL}/{media_id}",
        params={"fields": "like_count,comments_count,timestamp,permalink"},
        headers=AUTH_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_media_insights(media_id: str) -> dict:
    """reach/saved等。権限が無い場合は空dictを返す"""
    try:
        resp = requests.get(
            f"{BASE_URL}/{media_id}/insights",
            params={"metric": "reach,saved,shares,profile_visits"},
            headers=AUTH_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return {item["name"]: item["values"][0]["value"] for item in data}
    except Exception:  # noqa: BLE001
        return {}


def main() -> int:
    entries = [e for e in load_queue() if e.get("posted") and e.get("media_id")]
    if not entries:
        print(json.dumps({"posts": []}, ensure_ascii=False, indent=2))
        return 0

    results = []
    for entry in entries:
        media_id = entry["media_id"]
        try:
            basic = fetch_basic_fields(media_id)
        except Exception as e:  # noqa: BLE001
            print(f"警告: {entry['id']} の取得に失敗しました: {e}", file=sys.stderr)
            continue
        insights = fetch_media_insights(media_id)
        results.append(
            {
                "id": entry["id"],
                "date": entry.get("date"),
                "posted_at": entry.get("posted_at"),
                "media_id": media_id,
                "permalink": basic.get("permalink"),
                "like_count": basic.get("like_count"),
                "comments_count": basic.get("comments_count"),
                **insights,
            }
        )

    print(json.dumps({"posts": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
