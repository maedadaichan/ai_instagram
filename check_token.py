"""Check whether IG_ACCESS_TOKEN in .env works, without printing the token."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()
token = (os.getenv("IG_ACCESS_TOKEN") or "").strip().strip("'\"")
if token.lower().startswith("bearer "):
    print("NG: 先頭に「Bearer 」が付いています。トークンだけにしてください。")
    raise SystemExit(1)
if not token:
    print("NG: .env に IG_ACCESS_TOKEN がありません。")
    raise SystemExit(1)

resp = requests.get(
    "https://graph.instagram.com/v21.0/me",
    params={"fields": "username"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=20,
)
if resp.ok:
    print(f"OK: 有効なトークンです(@{resp.json().get('username')}, {len(token)}文字)")
else:
    message = resp.json().get("error", {}).get("message", resp.text[:200])
    print(f"NG: {resp.status_code} {message}({len(token)}文字, IGAAで始まる: {token.startswith('IGAA')})")
    raise SystemExit(1)
