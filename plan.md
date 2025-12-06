# PubMed メタデータ収集・全文ダウンロード計画

以下は PubMed での検索・メタデータ収集・全文取得（PMC / Sci-Hub / Unpaywall のフォールバック）を行うための詳細な実装計画です。参考: [scihub-cli](https://github.com/Oxidane-bot/scihub-cli), [botasaurus](https://github.com/omkarcloud/botasaurus)

## 全体構成
- 言語: Python 3.11 以降
- パッケージ管理: `uv` または `pip` + `requirements.txt`
- 主なライブラリ
  - PubMed/PMC 取得: `biopython` (Entrez)、`pymed`
  - DB: `SQLAlchemy` + SQLite (初期) / Postgres (拡張可)
  - HTTP: `httpx` または `requests`
  - CLI: `typer` or `click`
  - 並列処理: `asyncio` + `httpx` または `concurrent.futures`
  - PDF 解析 (必要なら): `pypdf`

## ディレクトリ/モジュール案
- `src/pubmed/`
  - `config.py`: API キー・環境変数読み込み
  - `search.py`: PubMed 検索、E-utilities ラッパー
  - `models.py`: SQLAlchemy モデル（論文・著者・ジャーナルなど）
  - `database.py`: セッション管理、DB 初期化
  - `ingest.py`: 検索結果を DB に保存するフロー
  - `downloaders/`
    - `pmc.py`: PMC/OAI-PMH/PMCID 経由の PDF 取得
    - `unpaywall.py`: DOI を使った OA 情報取得と PDF URL 抽出
    - `scihub.py`: Sci-Hub ミラーへのリクエスト、captcha/失敗時のリトライ
    - `fallback.py`: 優先度付きの取得フロー（PMC → Unpaywall → Sci-Hub）
  - `cli.py`: Typer/Click ベースの CLI エントリポイント
  - `utils/`: ロギング、リトライ、ユーザーエージェント、Rate Limit 管理
- `tests/`: 各モジュールのユニットテスト
- `README.md`: セットアップと利用方法

## 検索 & メタデータ取得フロー
1. **検索クエリ構築**
   - ESearch を用いて PMID リスト取得。パラメータ: `term`, `retmax`, `retstart`, `mindate`, `maxdate`, `sort`。
   - 大量取得時は `retstart` でページング。
2. **メタデータ取得**
   - EFetch で PMID から詳細（タイトル、著者、抄録、ジャーナル、出版年、DOI 等）取得。
   - DOI などの識別子を抽出し DB に保存。
3. **DB 設計（SQLAlchemy）**
   - `Paper`: PMID, PMCID, DOI, title, abstract, journal, year, volume, issue, pages, url, is_oa, created_at/updated_at。
   - `Author`: name, affiliation。`paper_authors` で多対多。
   - `Download`: paper_id, source (PMC/Unpaywall/Sci-Hub), url, status, path, checksum, attempted_at。
   - インデックス: PMID/DOI にユニーク制約。
4. **永続化フロー**
   - トランザクション内で upsert（`ON CONFLICT DO NOTHING` 相当）を実装。
   - 既存レコードとの突き合わせで重複を防止。

## 全文取得フロー
- **優先度:** PMC → Unpaywall → Sci-Hub
- 共通の機能
  - DOI/PMCID が無い場合のスキップロジック
  - タイムアウト、バックオフ、リトライ（指数的）
  - User-Agent ローテーション（参考: scihub-cli/botasaurus のプロキシや UA ランダム化）
  - 保存先: `data/papers/<pmid>.pdf`。状態は `Download` テーブルに記録。

### PMC ダウンロード
- `pmcid` がある場合のみ実行。
- NCBI の `pmc` API から PDF URL を取得しダウンロード。
- 403/404 時は Unpaywall にフォールバック。

### Unpaywall
- DOI をキーに `https://api.unpaywall.org/v2/{doi}?email=` で OA 情報取得。
- OA URL が PDF なら直接ダウンロード。複数ある場合は `best_oa_location` を優先。
- OA でない場合は Sci-Hub にフォールバック。

### Sci-Hub
- DOI/URL を用いて Sci-Hub ミラーへ POST/GET。
- CAPTCHA/HTML 応答の場合はミラーのローテーションまたはプロキシ利用。
- PDF 埋め込み `<iframe>`/`<embed>` の `src` を抽出しダウンロード。
- リスクと合法性を考慮し、デフォルトでは無効化し、`--enable-scihub` フラグで明示的に実行。

## CLI 仕様案 (Typer)
- `pubmed search "cancer genomics" --retmax 200 --mindate 2020/01/01 --save-db`
- `pubmed fetch-pdfs --source pmc,unpaywall --max-workers 4 --output data/papers`
- `pubmed show <pmid>`: DB からメタデータ確認。
- `pubmed export --format csv/json --output exports/papers.csv`

## 設定/環境変数
- `PUBMED_API_KEY`: NCBI API key (必須ではないが推奨)
- `UNPAYWALL_EMAIL`: Unpaywall API 用メールアドレス（必須）
- `PROXY_URL`: Sci-Hub アクセス用プロキシ (任意)
- `.env` から読み込み。`config.py` でバリデーション。

## 例外処理 & ロギング
- `logging.config.dictConfig` を用いた構成。
- ダウンロード失敗理由を `Download.status` と `error_message` に保持。
- HTTP ステータス別のリトライ/フォールバックパターンを定義。

## テスト戦略
- PubMed/PMC/Unpaywall API 呼び出しは `respx`/`requests-mock` でモック。
- DB テストは SQLite のインメモリを使用。
- CLI は `typer.testing.CliRunner` を使用。

## 開発フェーズ
1. プロジェクトの雛形作成（`src` 構造、pyproject/requirements、CLI エントリ）。
2. DB モデル & 永続化レイヤー実装、基本検索と登録までカバー。
3. PMC → Unpaywall → Sci-Hub の downloader 実装と統合。
4. CLI コマンド整備、設定ファイル/環境変数対応。
5. テスト追加、README/使用例更新。

## リスク/考慮点
- Sci-Hub 利用は法的リスクがあるため、デフォルト無効 + 明示 opt-in。
- NCBI のレートリミット (API key あり: 10req/s, なし: 3req/s) を遵守。
- 大規模ダウンロード時のストレージ/冗長性、ファイル名衝突を考慮。

