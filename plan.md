# PubMed 検索・メタデータ収集・全文取得 実装計画（改訂版）

参考: [scihub-cli](https://github.com/Oxidane-bot/scihub-cli), [botasaurus](https://github.com/omkarcloud/botasaurus)

## 1. アーキテクチャ概要
- **言語/ランタイム**: Python 3.11+。標準で `uv` を推奨（高速インストール/ロック）。
- **プロジェクト構造**: `src` 配下に機能別モジュールを明確分離。`tests` でユニット/統合テストを保持。
- **設計原則**:
  - コアロジックを「検索」「永続化」「ダウンロード」「CLI」の 4 層に分離。
  - 依存方向は下位（infra/utils）→上位（アプリ）へ単方向にする。
  - I/O（HTTP/DB/FS）はポート・アダプタパターンを採用しテスト容易性を確保。

## 2. ディレクトリ/モジュール構成
- `src/pubmed/`
  - `config.py`: `.env`/環境変数読み込み + Pydantic 設定モデル。API キーやプロキシ、キャッシュ TTL を定義。
  - `logging.py`: `logging.config.dictConfig` を使った統一ロガー。JSON ログと人間可読ログを切り替え。
  - `utils/`
    - `http.py`: `httpx.AsyncClient` を使ったセッション生成、UA/プロキシ/リトライポリシー（指数バックオフ）。
    - `rate_limit.py`: NCBI レートリミット（API key 有/無で切替）と Sci-Hub アクセス間隔管理。
    - `parsing.py`: HTML/PDF URL 抽出、日付/ID 正規化。
    - `fs.py`: パス生成 (`data/papers/<pmid>.pdf`)、チェックサム計算、テンポラリ保存。
  - `models.py`: SQLAlchemy Core/ORM モデル（Paper, Author, Journal, Download, PaperAuthor）。スキーママイグレーションのため Alembic 設定を想定。
  - `database.py`: エンジン/Session 管理、`get_session()` コンテキスト、SQLite/PostgreSQL 切替。
  - `schemas.py`: Pydantic スキーマ（外部 API レスポンス/CLI 入力検証）。
  - `search/`
    - `entrez_client.py`: E-utilities (ESearch/EFetch/ELink) 呼び出しクライアント。`httpx` ベース、`retstart` ページング、`WebEnv`/`QueryKey` によるバッチ取得対応。
    - `parser.py`: EFetch XML/Medline から DOI/PMCID/タイトル/著者/抄録を抽出。
    - `service.py`: 検索→詳細取得→スキーマ化を orchestrate。
  - `ingest.py`: メタデータ保存フロー。Paper/Author の upsert、Download 初期レコード作成。
  - `downloaders/`
    - `pmc.py`: PMCID から PDF URL を取得（PMC API/OAI-PMH）、`httpx` でダウンロード。
    - `unpaywall.py`: DOI で OA 情報取得。`best_oa_location` 優先。PDF 直接 URL を返す。
    - `scihub.py`: 複数ミラーのローテーション、フォーム送信/iframe 解析、Captcha/HTML 失敗検知。`--enable-scihub` フラグ必須。
    - `fallback.py`: 優先度付きの戦略（PMC → Unpaywall → Sci-Hub）。例外を握りつぶさず理由を Download レコードへ記録。
  - `workflow.py`: PMID リストを入力にメタデータ取得 + 全文ダウンロードを非同期キュー（`asyncio.gather` + セマフォ）で実施。再試行ポリシーを集中管理。
  - `cli.py`: Typer ベース CLI。`search`/`ingest`/`download`/`show`/`export` コマンドを提供。
- `tests/`: respx で HTTP モック、SQLite in-memory で DB テスト、Typer `CliRunner` で CLI テスト。

## 3. データモデル詳細 (SQLAlchemy)
- `Paper`: `pmid`(PK, uniq), `pmcid`, `doi`, `title`, `abstract`, `journal`, `year`, `volume`, `issue`, `pages`, `url`, `is_oa`, `created_at`, `updated_at`。
- `Author`: `id`(PK), `name`, `affiliation`。
- `Journal`: `id`(PK), `name`, `issn`。
- `PaperAuthor`: `paper_id`, `author_id`, `order`。
- `Download`: `id`, `paper_id`, `source`(pmc/unpaywall/scihub), `url`, `status`(pending/success/failed/skipped), `path`, `checksum`, `error`, `attempted_at`。
- インデックス: `pmid`/`doi`/`pmcid` のユニーク制約。`Download.paper_id + source` でユニーク。

## 4. メタデータ取得フロー
1) **検索 (ESearch)**: `term`, `retmax`, `retstart`, `mindate`, `maxdate`, `sort` を受け取り PMID リスト取得。大量件数は `usehistory=y` + `WebEnv`/`QueryKey` でページング。
2) **詳細取得 (EFetch)**: PMID バッチを XML で取得。`parser.py` で DOI/PMCID/PMID/タイトル/著者/抄録/ジャーナル/出版年を抽出。
3) **永続化**: `ingest.py` でトランザクション upsert。既存 DOI/PMID があれば更新、無ければ挿入。`Download` は `status=pending` で初期化。
4) **整合性**: 不正値（DOI 無しなど）は `status=skipped` で Download をマークし後続ダウンロードから除外。

## 5. 全文ダウンロード戦略
- **優先順位**: PMC → Unpaywall → Sci-Hub。Download レコードに全試行を履歴化。
- **共通ポリシー**
  - タイムアウト/指数バックオフリトライ（HTTP 5xx/429）。
  - UA ローテーション + オプションのプロキシ（botasaurus/scihub-cli 由来の戦略を反映）。
  - コンテンツ検証: PDF MIME/先頭バイトチェック、サイズ下限チェック。
  - 保存時はテンポラリ → チェックサム計算 → アトミック move。`Download.status`/`error`/`attempted_at` を更新。

### PMC
- PMCID から `pmc.py` が OAI-PMH/PMC API を呼び PDF URL を抽出。
- 403/404/非 OA の場合は `Download.status=failed` 理由を記録し Unpaywall へフォールバック。

### Unpaywall
- DOI をキーに `https://api.unpaywall.org/v2/{doi}?email=` を呼び、`best_oa_location` を優先。
- PDF 直リンクでない場合はスキップ理由を記録し Sci-Hub に移行。

### Sci-Hub
- DOI/URL をミラーへ送信。HTML 応答なら `<iframe>`/`<embed>` の `src` を抽出。
- Captcha/認証ページ検知で別ミラー/プロキシにローテート。既知ミラーの健全性チェックを起動時に実施可能。
- 法的リスク回避のため CLI フラグ `--enable-scihub` が無ければ実行しない。

## 6. CLI 仕様 (Typer)
- `pubmed search "cancer genomics" --retmax 200 --mindate 2020/01/01 --save-db`
- `pubmed download --sources pmc,unpaywall --max-workers 4 --output data/papers --enable-scihub`
- `pubmed show <pmid>`: DB からメタデータ/ダウンロード履歴を表示。
- `pubmed export --format csv/json --output exports/papers.csv`

## 7. 設定/環境変数
- `PUBMED_API_KEY`: NCBI API key（推奨、Rate Limit 緩和）。
- `UNPAYWALL_EMAIL`: Unpaywall API 用メール（必須）。
- `PROXY_URL`: Sci-Hub/Unpaywall 用プロキシ（任意）。
- `DATA_DIR`: PDF 保存先。未指定時は `data/papers`。
- `LOG_LEVEL`, `LOG_FORMAT`: json/text 切替。

## 8. テスト戦略
- HTTP コールは `respx`/`pytest-httpx` でモック、タイムアウト/リトライ/フォールバックの分岐を網羅。
- DB は SQLite インメモリ + フィクスチャでセットアップ。upsert/ユニーク制約/リレーションを検証。
- CLI は `CliRunner` でサブコマンド別に E2E 風テスト。
- ダウンローダは小さな PDF モックで MIME/チェックサム/エラー処理を確認。

## 9. 開発フェーズとマイルストーン
1) プロジェクト雛形 (`src`/`pyproject`/`uv.lock`/`cli` エントリ)。logging/config/util を先行整備。
2) 検索スタック: `entrez_client` + `parser` + `ingest`（DB upsert まで）。基本 CLI `search` を提供。
3) ダウンロードスタック: PMC/Unpaywall/Sci-Hub 各 downloader + `fallback` 統合。`workflow` で非同期ダウンロード。
4) CLI 拡充: `download`/`show`/`export`、設定ロード、`--enable-scihub` フラグ。
5) テスト強化 & CI: `pytest` + フォーマッタ/リンタ（`ruff`, `mypy` 任意）。サンプル `.env.example` と README 更新。

## 10. リスクと対策
- Sci-Hub: 法的リスク → デフォルト無効 + 明示 opt-in、モジュール単体で無効化可能にする。
- レートリミット: `rate_limit.py` で API key 有/無を考慮し sleep を挿入。`Retry-After` ヘッダ尊重。
- ミラー死活監視: Sci-Hub ミラー一覧を設定で複数持ち、起動時ヘルスチェック。
- データ品質: DOI/PMCID 欠落時は `Download.status=skipped`。タイトル/著者欠落をログで通知。
- ストレージ: 衝突防止のため `<pmid>.pdf` 形式 + チェックサム。冪等な再ダウンロードをサポート。
