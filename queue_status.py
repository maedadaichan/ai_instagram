"""
投稿キューの残り件数を表示し、未投稿エントリの動画・画像ファイルが揃っているか検証するスクリプト。

使い方:
    python queue_status.py

問題があれば終了コード1を返す。
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(ROOT, "queue", "posts.json")


def main() -> int:
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        queue = json.load(f)

    pending = [e for e in queue if not e.get("posted")]
    print(f"キュー残り{len(pending)}件(全{len(queue)}件)")

    problems = []
    ids = [e.get("id") for e in queue]
    for entry_id in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"idが重複しています: {entry_id}")
    for entry in pending:
        media = entry.get("video") or entry.get("image")
        if not media:
            problems.append(f"{entry.get('id')}: videoもimageもありません")
        elif not media.startswith("http") and not os.path.exists(os.path.join(ROOT, media)):
            problems.append(f"{entry.get('id')}: ファイルがありません: {media}")
        if not entry.get("caption"):
            problems.append(f"{entry.get('id')}: captionがありません")

    for problem in problems:
        print(f"問題: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
