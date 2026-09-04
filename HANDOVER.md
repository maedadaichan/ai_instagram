# 引継ぎメモ (2026-09-04時点)

## ゴール
`ai__daisuke`(Ai-Raku)のInstagramアカウントへ、AI活用系の投稿を自動化する。

## 完了済みのこと

### 1. Meta開発者アプリ
- アプリ名: `ai_sns_poster` (App ID: `27606028352409353`)
- ビジネスポートフォリオ: Ai-Raku
- ユースケース: 「Instagramでメッセージとコンテンツを管理」(Instagramログイン方式API)
- 追加済み権限: `instagram_business_basic` / `instagram_business_manage_comments` / `instagram_business_manage_messages` / `instagram_business_content_publish`

### 2. Instagramアカウント連携
- `ai__daisuke` (Instagram User ID: `17841433313484825`) をInstagramテスターとして招待し、本人が承認済み
- 長期アクセストークンを生成済み → [.env](.env) に保存済み(**このファイルはGit管理に含めないこと**)

### 3. 投稿スクリプト
- [post_to_instagram.py](post_to_instagram.py): Instagramログイン方式API (`graph.instagram.com`) を使う形に修正済み
- 使い方: `python post_to_instagram.py --image-url "公開URL" --caption "キャプション"`
- 注意: 画像はネット上の公開URLである必要あり(ローカルファイル直接アップロード不可)
- 未実施: 実際の投稿テストはまだ行っていない

### 4. コンテンツ戦略の調査結果
- 伸びているAI系アカウント例: @brock11johnson (88.5万)、@instacoachmike (150万+)、@tennyhainsworth_ (顔出しなしAIコンテンツで収益化)、@marketing.with.m など
- 伸びている型: 「顔出しなし(faceless)」×「AI自動生成」のReelsが主流
- 制作フロー: 台本生成→AI映像/画像生成→AIナレーション(ElevenLabs等)→字幕自動付与→BGM→投稿
- アルゴリズム傾向: 保存・シェア・視聴時間・DM等のエンゲージメントが重要。週3〜5回投稿のアカウントは週1〜2回より約2倍速く成長
- 詳細な調査ソースは会話履歴に記載(Web検索結果)

## 現在の課題(未解決)

**Claude in Chrome拡張機能のMCP接続が切れている**。ユーザーは拡張機能の再確認・Chrome再起動を実施済みだが、まだ接続が回復していない。

- ユーザーの意向: Claude Codeのセッションを立ち上げ直すことで接続復旧を試みる予定
- 新セッションで最初に確認すべきこと: `mcp__claude-in-chrome__tabs_context_mcp` (またはブラウザツール)が使えるか再確認

## 次にやるべきこと

1. ブラウザ接続の復旧確認
2. 投稿の方向性を決める(例: 「AI導入のリアル」路線 — 業務効率化Tips系・失敗談系・ビフォーアフター系など)。ユーザーへの確認がまだ
3. ChatGPT(chatgpt.com)で投稿用画像を生成
   - ユーザーは画像制作をChatGPTで行いたい意向。Claude in Chromeが繋がれば代行操作可能、繋がらなければプロンプト案を用意してユーザー自身に生成してもらう
4. キャプション文を作成(x-viral-writing / ai-shien-biz-styleスキルが参考になる可能性あり)
5. `post_to_instagram.py` で実際に投稿を実行(公開画像URLが必要 — 画像のホスティング方法も要検討。例: GitHub raw、S3等)

## 参考: プロジェクトファイル一覧
- [README.md](README.md): セットアップ手順の全体ガイド
- [.env.example](.env.example) / [.env](.env): 認証情報
- [requirements.txt](requirements.txt): 依存パッケージ
- [post_to_instagram.py](post_to_instagram.py): 投稿実行スクリプト
- [images/](images): 投稿用画像置き場(空)
