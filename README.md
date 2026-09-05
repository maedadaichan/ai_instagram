# ai_instagram

Instagram Graph APIを使った投稿自動化ツールです。

## 1. 事前準備(ここはご自身で行ってください)

パスワード・トークンなどの認証情報の取得・入力はセキュリティ上、私(Claude)は代行できません。以下はユーザー自身で行ってください。

1. InstagramアカウントをNoteプロ/ビジネスアカウントに切り替える
2. そのInstagramアカウントをFacebookページと連携する
3. [Meta for Developers](https://developers.facebook.com/) でアプリを新規作成
4. アプリに「Instagram Graph API」を追加
5. 以下の権限を持つアクセストークンを発行する
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
6. Graph API Explorer等で短期トークンを取得後、長期トークン(60日間有効)に交換する
7. `https://graph.facebook.com/v21.0/me/accounts` などでFacebookページID→IGビジネスアカウントIDを調べる

取得した値は、`.env.example` をコピーして `.env` を作成し記入してください。

```bash
cp .env.example .env
```

```
IG_ACCESS_TOKEN=取得した長期アクセストークン
IG_USER_ID=InstagramビジネスアカウントID
```

## 2. セットアップ

```bash
pip install -r requirements.txt
```

## 3. 投稿の実行

画像はInstagram Graph APIの仕様上、**公開アクセス可能なURL**である必要があります(ローカルファイルの直接アップロードは不可)。GitHubの生画像URL、S3、任意のWebサーバー等でホストしてください。

```bash
python post_to_instagram.py --image-url "https://example.com/photo.jpg" --caption "投稿するキャプション文"
```

実行すると `media_id` が表示されれば投稿完了です。

## 4. キャプション作成のサポート

投稿内容(テーマ・トーン・ハッシュタグの方向性など)を伝えていただければ、キャプション文の作成・添削をこの場でお手伝いします。

## 5. 投稿キュー(自動投稿)

`queue/posts.json` に投稿予定(日付・画像パス・キャプション)を並べておくと、`post_next.py` が先頭の未投稿(`posted: false`)エントリを1件だけ投稿します。

```bash
python post_next.py
```

投稿に成功すると、該当エントリが `posted: true` に更新されます(このファイルの変更はcommit・pushしてください)。毎日決まった時間に自動実行するクラウドルーチンから呼び出す想定です。
