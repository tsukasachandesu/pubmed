# PubMed 検索・メタデータ収集・全文取得 実装計画

参考: [scihub-cli](https://github.com/Oxidane-bot/scihub-cli), [botasaurus](https://github.com/omkarcloud/botasaurus)

## 1. アーキテクチャ概要
- **言語/ランタイム**: Python 3.11+。`uv` でのロック/インストールをデフォルトとし、`--frozen` で再現性を担保。
- **アーキテクチャスタイル**: Clean Architecture + ヘキサゴナルを併用し、ドメイン（検索・論文・ダウンロード）を中心にポート/アダプタで疎結合化。同期/非同期の境界をユースケース層で明示し、非同期 I/O（HTTP/ファイル）を第一級として扱う。
- **レイヤリング**:
  - **Domain**: 取得/永続化/ダウンロードのポート定義、エンティティ（Paper, Author, Download）とサービス（ドメインルール）。
  - **UseCase (Application)**: ドメインポートを組み合わせたユースケース（検索→パース→保存、全文ダウンロードパイプライン、CLI コマンド実装に依存しないジョブ）。
  - **Interface/Adapter**: HTTP クライアント、DB 実装、ファイルシステム、CLI/REST/バッチエントリポイント。依存は Domain/UseCase のみに限定。
  - **Infrastructure**: ロギング、設定、リトライ、キャッシュ、タスクスケジューラ（`anyio`/`asyncio` セマフォ）、オブザーバビリティ（OpenTelemetry ロガー/トレース/メトリクス）。
- **横断的関心事**:
  - リトライ/サーキットブレーカーを `tenacity` 互換の薄いラッパで統一。
  - レートリミットはトークンバケット + 予測的ウェイト（NCBI レスポンスヘッダを考慮）。
  - オブザーバビリティ: 構造化ログ（JSON/pretty）、トレース ID のコンテキスト伝搬、ダウンロード成功率/HTTP 4xx/5xx をメトリクス化。
  - コンフィグは Pydantic Settings + `.env` で階層マージ。`config validate --strict` コマンドで検証可能にする。
  - セキュリティ/コンプライアンス: Sci-Hub はフラグ必須 + 監査ログにソースを残す。PII を扱わないがファイル名/パスはエスケープし OS コマンドインジェクションを防ぐ。
  - スケーラビリティ: ダウンロードワーカーはセマフォ + バックプレッシャー、キューイング（`asyncio.Queue`）でメモリフットプリントを制御。将来の分散化に備え、ワーカープールを抽象化。

## 2. ディレクトリ/モジュール構成
- `src/pubmed/`
  - `settings.py`: Pydantic Settings。`.env` 読み込み、値の strict validation、`config validate` 用ヘルパ。
  - `logging.py`: `logging.config.dictConfig` ベースの構造化ロガー。OpenTelemetry ハンドラ/Exporter を組み込み可能に。
  - `adapters/` (Interface/Adapter)
    - `http_client.py`: `httpx.AsyncClient` ファクトリ、UA/プロキシ/リトライ/サーキットブレーカー。`@asynccontextmanager` でクリーンアップ。
    - `rate_limit.py`: NCBI/Unpaywall/Sci-Hub 用トークンバケットとレスポンスヘッダ連動のスリープ計算。
    - `filesystem.py`: パス生成 (`data/papers/<pmid>.pdf`)、テンポラリ保存、チェックサム、アトミック move。
    - `observability.py`: ログ・メトリクス・トレースの初期化。リクエストタグ/PMID/DOI を Span に付与。
  - `domain/` (Domain)
    - `entities.py`: Paper, Author, Journal, Download 等のドメインオブジェクト（不変値 + 検証）。
    - `ports.py`: リポジトリ/外部 API/ストレージのインターフェイス定義。
    - `services.py`: ビジネスルール（保存時のユニークキー優先順位、ダウンロード許可判定、再試行方針）。
  - `infrastructure/`
    - `db/`
      - `models.py`: SQLAlchemy ORM/Core モデル。Alembic migration 用設定ファイルも同居。
      - `session.py`: エンジン/セッション生成、`get_session()`、同期/非同期両対応のフック。
      - `repositories.py`: ドメイン `ports` に準拠した実装。upsert、バルクインサート、衝突解決。
    - `cache.py`: `diskcache`/`sqlite` ベースの簡易キャッシュ。Entrez の WebEnv/QueryKey を短期保持。
  - `search/`
    - `entrez_client.py`: E-utilities (ESearch/EFetch/ELink) クライアント。`retstart` ページング、`usehistory` 対応、`http_client` を注入。
    - `normalizer.py`: EFetch XML/Medline から DOI/PMCID/タイトル/著者/抄録/ジャーナルを抽出しスキーマ化。
    - `usecase.py`: 検索→パース→保存を一貫実行。結果をドメインサービスに渡し永続化。
  - `ingest/`
    - `usecase.py`: メタデータ保存フロー。Paper/Author の upsert、Download 初期レコード作成、エラーハンドリングを集約。
  - `download/`
    - `sources/`
      - `pmc.py`: PMCID→PDF URL 抽出（PMC API/OAI-PMH）。
      - `unpaywall.py`: DOI→OA 情報取得。`best_oa_location` 優先、PDF ダイレクトリンクを返す。
      - `scihub.py`: ミラー ローテーション + iframe/embed 解析。Captcha/HTML 失敗検知。`--enable-scihub` ガード。
    - `strategy.py`: 優先度付きフォールバック（PMC → Unpaywall → Sci-Hub）。各試行の結果を Download ログに記録。
    - `pipeline.py`: 非同期ダウンロードワーカー。セマフォ + バックプレッシャー、テンポラリ保存→検証→コミットを一元管理。
  - `workflow.py`: PMID リスト入力で検索→永続化→全文取得を統合。ジョブ単位のリトライと観測情報を付与。
  - `cli.py`: Typer ベース CLI。`search`/`ingest`/`download`/`show`/`export`/`config validate` を提供。DI で UseCase を注入。
- `tests/`
  - `unit/` と `integration/` に分離。respx/pytest-httpx、SQLite in-memory、CliRunner を活用。
  - `fixtures/` にテスト用 XML/PDF サンプルを保持。

## 3. データモデル詳細 (SQLAlchemy)
- **永続化方針**
  - API から取得したメタデータ/全文 URL/ダウンロード結果は欠落なく全件データベースに保存し、フィルタリングやトリミングは保存後のクエリで行う。
  - ORM を基本としつつ、バルク/アップサートは Core を併用。セッションは「リクエスト/CLI コマンド単位」で scope し、非同期は `async_sessionmaker` で別管理。トランザクション境界はユースケース層で開始し、リポジトリはセッション注入型にする。
  - Alembic は単一ブランチ運用 + `revision --autogenerate` を必ずレビュー。命名規約 `YYYYMMDD_hhmmss_<summary>`。
  - SQLite/PostgreSQL 両対応。外部キー ON/OFF や `ON DELETE` ポリシーの差異を Alembic スクリプトに明示（基本は RESTRICT、`Download.paper_id` は CASCADE）。

**テーブル/制約**
- `Paper`: `pmid`(PK, uniq), `pmcid`, `doi`, `title`, `abstract`, `journal`, `year`, `volume`, `issue`, `pages`, `url`, `is_oa`, `created_at`, `updated_at` (UTC, `updated_at` は SQLAlchemy イベントで自動更新)。
- `Author`: `id`(PK), `name`, `affiliation`。
- `Journal`: `id`(PK), `name`, `issn`。
- `PaperAuthor`: `paper_id`, `author_id`, `order`。`(paper_id, order)` にユニーク制約（1 始まりの順序を保証）。
- `Download`: `id`, `paper_id`, `source`(pmc/unpaywall/scihub), `url`, `status`(pending/success/failed/skipped), `path`, `checksum`, `error`(TEXT, 長さ上限 2k 目安), `attempted_at`(timezone-aware)。`Download.paper_id + source` をユニーク。
- `doi`/`pmcid` の重複防止: Postgres はパーシャルユニーク (`WHERE doi IS NOT NULL`) を検討、SQLite は CHECK + 複合 UNIQUE を採用。

**インデックス/検索性**
- `pmid`/`doi`/`pmcid` にユニークインデックス。`Download` は `(paper_id, source)` でユニーク + `status` へのカバリングインデックス。
- タイトル/抄録に対する全文検索は将来オプションとして FTS5(GIN) を検討（現段階では未実装と明記）。

**テスト/シード**
- Alembic マイグレーションは CI で `alembic upgrade head` を実行し、SQLite in-memory で upsert/ユニーク制約/外部キーの回帰を検証。
- 小規模サンプル（数件の Paper/Download）を seed fixture として用意し、ダウンロード履歴の整合性テストに利用。

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
