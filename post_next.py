"""
投稿キュー(queue/posts.json)から未投稿の先頭1件を選び、Instagramに投稿するスクリプト。

前提:
- IG_ACCESS_TOKEN / IG_USER_ID が環境変数(または.env)に設定されていること
- GITHUB_REPO_RAW_BASE で画像の公開URLのベースを指定できる(未設定時はデフォルトのraw.githubusercontent.com URLを使用)
- 投稿成功後、queue/posts.json の該当エントリを posted: true に更新して保存する
  (呼び出し側でこのファイルをcommit・pushすることを想定)

使い方:
    python post_next.py
"""

import json
import os
import sys
from datetime import date, datetime, timezone

from post_to_instagram import post_image

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "queue", "posts.json")
DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/maedadaichan/ai_instagram/main"


def load_queue() -> list:
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(entries: list) -> None:
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    entries = load_queue()
    next_entry = next((e for e in entries if not e.get("posted")), None)

    if next_entry is None:
        print("投稿待ちのキューはありません。")
        return 0

    raw_base = os.getenv("GITHUB_REPO_RAW_BASE", DEFAULT_RAW_BASE)
    image_url = f"{raw_base}/{next_entry['image']}"

    print(f"投稿します: id={next_entry['id']} date={next_entry['date']}")
    try:
        media_id = post_image(image_url, next_entry["caption"])
    except Exception as e:  # noqa: BLE001
        print(f"投稿に失敗しました: {e}", file=sys.stderr)
        return 1

    next_entry["posted"] = True
    next_entry["posted_at"] = datetime.now(timezone.utc).date().isoformat()
    next_entry["media_id"] = media_id
    save_queue(entries)

    print(f"投稿完了しました。id={next_entry['id']} media_id={media_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
