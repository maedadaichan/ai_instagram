"""
Instagram Graph API 投稿スクリプト

前提:
- Instagramアカウントがビジネス/プロアカウントで、Facebookページと連携済みであること
- Meta for Developersでアプリを作成し、長期アクセストークンとIGビジネスアカウントIDを取得していること
- 画像は公開アクセス可能なURLである必要がある(ローカルファイルは直接アップロード不可)

使い方:
    python post_to_instagram.py --image-url "https://example.com/photo.jpg" --caption "キャプション文"
"""

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_USER_ID = os.getenv("IG_USER_ID")
API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
BASE_URL = f"https://graph.instagram.com/{API_VERSION}"


def create_media_container(image_url: str, caption: str) -> str:
    """画像投稿用のメディアコンテナを作成し、コンテナIDを返す"""
    resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def wait_until_ready(container_id: str, timeout_sec: int = 60) -> None:
    """コンテナのステータスがFINISHEDになるまで待機"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/{container_id}",
            params={"fields": "status_code", "access_token": ACCESS_TOKEN},
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"メディア処理がエラーになりました: container_id={container_id}")
        time.sleep(2)
    raise TimeoutError(f"メディア処理がタイムアウトしました: container_id={container_id}")


def publish_media(container_id: str) -> str:
    """コンテナを公開し、投稿(メディア)IDを返す"""
    resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media_publish",
        data={
            "creation_id": container_id,
            "access_token": ACCESS_TOKEN,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def post_image(image_url: str, caption: str) -> str:
    if not ACCESS_TOKEN or not IG_USER_ID:
        raise RuntimeError(
            "IG_ACCESS_TOKEN / IG_USER_ID が設定されていません。.env を作成してください(.env.example参照)。"
        )
    container_id = create_media_container(image_url, caption)
    wait_until_ready(container_id)
    media_id = publish_media(container_id)
    return media_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Instagramに画像を投稿する")
    parser.add_argument("--image-url", required=True, help="公開アクセス可能な画像URL")
    parser.add_argument("--caption", default="", help="投稿キャプション")
    args = parser.parse_args()

    try:
        media_id = post_image(args.image_url, args.caption)
    except Exception as e:  # noqa: BLE001
        print(f"投稿に失敗しました: {e}", file=sys.stderr)
        return 1

    print(f"投稿完了しました。media_id={media_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
