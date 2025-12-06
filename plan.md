# PubMed 検索・メタデータ収集・全文ダウンロード 実装計画

参考: [scihub-cli](https://github.com/Oxidane-bot/scihub-cli), [botasaurus](https://github.com/omkarcloud/botasaurus)

---

## 1. アーキテクチャ概要

- 言語/ランタイム  
  - Python 3.11+。パッケージ管理と実行は `uv` を前提とし、`uv sync --frozen` でロックファイルに基づく再現性を確保。

- アーキテクチャスタイル  
  - Clean Architecture + ヘキサゴナル (Ports & Adapters)。  
  - 中心にドメイン (`Paper`, `Download`, `ApiCallLog` 等)、外側に UseCase 層、さらに外側に各種アダプタ (DB, HTTP, Botasaurus, CLI, FS)。

- データベース / ORM  
  - 本番 DB は PostgreSQL 16 (JSONB, GIN インデックス利用)。ローカル開発では SQLite も許容。  
  - ORM/DB ツールキットは SQLAlchemy 2.x (Core + ORM) + Alembic。必要なら SQLModel を併用して型安全性と DX を向上。

- HTTP / スクレイピングレイヤ  
  - API 呼び出し (Entrez/E-utilities, Unpaywall など) には `httpx.AsyncClient`。  
  - 論文 PDF のダウンロードには **Botasaurus** を利用し、`@request` で軽量 HTTP、`@browser` で Cloudflare 等を突破するブラウザ自動化を行う。

- 非同期化方針  
  - HTTP/ファイル/DB I/O は `async` / `await` を第一級とし、`anyio` のタスクグループで構造化並列処理。  
  - CPU バウンド処理 (重いパースや検証) は必要に応じてスレッド/プロセスプールにオフロード。

- 横断的関心事  
  - リトライ/サーキットブレーカー: `tenacity` 互換ラッパで統一、ポリシーは設定で切り替え。  
  - レートリミット: トークンバケット + 予測スリープ。NCBI 推奨値 (API key 有無で 3/10 req/sec) と `Retry-After` ヘッダを厳密に尊重。  
  - オブザーバビリティ: 構造化ログ (JSON/pretty 切替)、OpenTelemetry ベースのトレース＆メトリクス、主要メトリクス (成功/失敗件数、HTTP 4xx/5xx、ダウンロード成功率) の自動収集。  
  - コンフィグ管理: Pydantic Settings (v2) + `.env` + 環境変数 + CLI オプションの多層マージ。`pubmed config validate --strict` コマンドで検証。  
  - セキュリティ/コンプライアンス:
    - Sci-Hub 利用はデフォルト無効。`--enable-scihub` かつ設定で明示 opt-in された場合のみ許可。  
    - ファイルパス/外部コマンドは必ずエスケープして OS コマンドインジェクションを防止。  
    - API key やメールアドレスなどのシークレットは環境変数/シークレットストア経由で注入し、ログには出さない。

---

## 2. DB/ORM 選定と方針

- 要件  
  - PubMed / Unpaywall / Sci-Hub 等の API レスポンスを **欠落なく (lossless)** 保存できること。  
  - よく使うフィールドは正規化テーブルとして高速にクエリ可能。  
  - スキーマ進化・マイグレーションが容易で、長期運用に耐えられること。  
  - 並列ダウンロードやバルク upsert に耐える性能とトランザクション制御を持つこと。

- 方針  
  - DB: PostgreSQL (JSONB, GIN インデックス) を本番標準とし、開発/テスト用途には SQLite も利用可。  
  - ORM: SQLAlchemy 2.x + Alembic。  
  - 生レスポンスは JSONB/TEXT の `raw_*` カラムと `ApiCallLog` テーブルに保存し、正規化カラムはクエリ用に最小限抽出する二層構造。

---

## 3. データモデルと Lossless 保存

- 主なエンティティ
  - `Paper`  
    - pmid, pmcid, doi, title, journal, year, volume, issue, pages, language, keywords など。  
    - `raw_pubmed_xml`: PubMed EFetch XML 全体 (TEXT)。  
    - `raw_pubmed_json`: 将来 API v3 など JSON レスポンス全体 (JSONB)。  
    - `raw_unpaywall_json`: Unpaywall レスポンス全体 (JSONB)。
  - `Author` / `PaperAuthor`  
    - 著者情報と Paper との多対多 + 順序。
  - `Download`  
    - paper_id, source (pmc/unpaywall/scihub/other), status (pending/succeeded/failed/skipped)、error、attempted_at、checksum、file_size 等。  
    - `raw_http_headers` (JSONB), `raw_http_meta` (JSONB: status_code, final_url, redirect_chain など)。
  - `ApiCallLog`  
    - service, endpoint, request_params, response_body, status_code, headers, created_at 等。  
    - すべての外部 API 呼び出しをここに lossless 保存。

- 制約・インデックス  
  - `Paper`: (pmid), (doi) にユニーク制約 (NULL 可)。  
  - `Download`: (paper_id, source) にユニーク制約。  
  - `ApiCallLog`: service, created_at, status_code などにインデックス。  
  - よく使う検索軸 (year, journal, created_at) にインデックス。

---

## 4. メタデータ取得フロー

1. 検索 (ESearch)  
   - 入力: `term`, `retmax`, `retstart`, `mindate`, `maxdate`, `sort` など。  
   - `usehistory=y` を指定し、`WebEnv` / `query_key` によるサーバ側ヒストリを利用。  
   - `tool` / `email` / `api_key` を必ず付与。  
   - レスポンス全文を `ApiCallLog` に保存。

2. 詳細取得 (EFetch)  
   - PMID バッチ (例: 200 件) ごとに XML を取得。  
   - 生 XML を `ApiCallLog` と `Paper.raw_pubmed_xml` に保存。  
   - `search/parser.py` で DOI / PMCID / タイトル / 著者 / ジャーナル / 年などを抽出。

3. 永続化 (ingest)  
   - `search/ingest.py` で Paper / Author / Download をトランザクション内で upsert。  
   - 新規論文には `Download(status=pending)` を作成。  
   - 未マッピングのフィールドも raw_* に存在するので、スキーマ拡張時に再抽出可能。

4. 整合性チェック  
   - 不正値や欠損値を検出したら Download を `skipped` / `failed` に変更し、`error` に理由を保存。  
   - `pubmed doctor` コマンドで raw_* と正規化カラムの整合性 (例: DOI の一致) を検査。

---

## 5. 全文ダウンロード戦略 (Botasaurus 利用)

- 優先順位  
  - **PMC → Unpaywall → Sci-Hub → その他 (publisher 直)** の順で試行。

- 共通ポリシー (Botasaurus ベース)
  - Botasaurus の `@request` / `@browser` デコレータでダウンロードタスクを定義。  
  - `max_retry`, `retry_wait`, `cache`, `run_async` 等を使って堅牢性とスループットを両立。  
  - PDF バリデーション: Content-Type, 先頭バイト, 最小サイズ。  
  - 書き込みフロー: テンポラリ → チェックサム計算 → アトミック move。  
  - すべての HTTP 応答は `Download.raw_http_headers` / `raw_http_meta` に保存。

- PMC  
  - PMCID から OA PDF URL を取得 (API / OAI-PMH)。  
  - `adapters.botassaurus.tasks_request` 経由で PDF を取得し、検証・保存。  
  - 403/404/ライセンス NG の場合は `failed` として Unpaywall にフォールバック。

- Unpaywall  
  - DOI から `best_oa_location` を取得。  
  - 直リンクなら `@request` でダウンロード。HTML 経由でしか取得できない場合は `@browser` で解決。  
  - レートリミット/メールアドレス要件を遵守。

- Sci-Hub  
  - デフォルト無効。`--enable-scihub` + 設定で明示 opt-in された場合のみ有効。  
  - `@browser` でページを開き、`<iframe>` / `<embed>` の `src` 等から PDF URL を抽出。  
  - ミラーを複数管理し、起動時のヘルスチェックにより死活監視。Captcha/ログイン検知時はミラーを切り替え。

---

## 6. ディレクトリ / モジュール構成 (細かいモジュール化)

- `src/pubmed/`
  - `__init__.py`

  - `core/` … 共通基盤
    - `__init__.py`
    - `errors.py` … 共通例外。
    - `types.py` … 型エイリアス、共通 dataclass。
    - `utils.py` … 汎用ユーティリティ (slug 化、再試行ヘルパなど)。

  - `config/` … 設定・ロギング・オブザーバビリティ
    - `__init__.py`
    - `settings.py` … Pydantic Settings による設定定義と読み込み。
    - `logging.py` … `logging.config.dictConfig` ベースの構成。
    - `observability.py` … OpenTelemetry / メトリクス初期化。

  - `adapters/` … 外部システムとの接続
    - `__init__.py`

    - `http/`
      - `__init__.py`
      - `client.py` … 共通 `httpx.AsyncClient` ファクトリ (再利用可能なセッション)。  
      - `entrez.py` … PubMed E-utilities (ESearch/EFetch/ELink) 用クライアント。  
      - `unpaywall.py` … Unpaywall API クライアント。  
      - `scihub.py` … Sci-Hub ミラーのヘルスチェックなどに使う HTTP クライアント。  
      - `rate_limit.py` … サービス別レートリミット実装。

    - `storage/`
      - `__init__.py`
      - `filesystem.py` … PDF/エクスポートファイルの I/O。  
      - `paths.py` … `data/papers/<pmid>.pdf` 等のパス/ディレクトリ設計。

    - `db/`
      - `__init__.py`
      - `session.py` … エンジン/セッション生成、接続設定。  
      - `models.py` … SQLAlchemy モデル定義。  
      - `repositories/`
        - `__init__.py`
        - `papers.py` … Paper/Author/PaperAuthor 用リポジトリ。  
        - `downloads.py` … Download 用リポジトリ。  
        - `api_logs.py` … ApiCallLog 用リポジトリ。

    - `botasaurus/`
      - `__init__.py`
      - `client.py` … Botasaurus の共通設定 (プロファイル/プロキシ/キャッシュ) を管理。  
      - `tasks_request.py` … `@request` ベースの PDF ダウンロードタスク群。  
      - `tasks_browser.py` … `@browser` ベースの URL 解決/ダウンロードタスク群。  
      - `profiles.py` … プロファイル名、プロキシ設定などの定義。

    - `cli/`
      - `__init__.py`
      - `app.py` … Typer アプリの定義。  
      - `io.py` … CLI 入出力 (色付き表示、確認プロンプト等) のヘルパ。

  - `domain/` … ドメインモデル
    - `__init__.py`

    - `paper/`
      - `__init__.py`
      - `entities.py` … Paper エンティティ。  
      - `value_objects.py` … PMID/DOI/PMCID 等の値オブジェクト。  
      - `services.py` … 論文に関するドメインロジック (重複判定など)。

    - `author/`
      - `__init__.py`
      - `entities.py` … Author, PaperAuthor 等。

    - `download/`
      - `__init__.py`
      - `entities.py` … Download エンティティ。  
      - `policies.py` … ダウンロード優先順位/再試行ポリシー。

    - `api_log/`
      - `__init__.py`
      - `entities.py` … ApiCallLog エンティティ。

  - `usecases/` … アプリケーションサービス
    - `__init__.py`

    - `search/`
      - `__init__.py`
      - `search_papers.py` … Term から PubMed 検索 → 取得 → 保存のユースケース。

    - `download/`
      - `__init__.py`
      - `download_papers.py` … 未ダウンロード論文をキューから取り出してダウンロード。  
      - `sync_status.py` … ファイル存在チェックと Download.status の同期。

    - `maintenance/`
      - `__init__.py`
      - `run_doctor.py` … 整合性チェック実行。  
      - `validate_config.py` … 設定検証ユースケース。

  - `search/` … メタデータ取得用の低レベル処理
    - `__init__.py`
    - `parser.py` … PubMed XML/Medline のパース。  
    - `ingest.py` … パース結果を domain/infrastructure にブリッジし、DB に upsert。

  - `download/` … ダウンロードフロー
    - `__init__.py`
    - `workflow.py` … キュー/ワーカー管理、Botasaurus タスクの呼び出し。  
    - `sources/`
      - `__init__.py`
      - `pmc.py` … PMC 用ダウンロードロジック。  
      - `unpaywall.py` … Unpaywall 用ダウンロードロジック。  
      - `scihub.py` … Sci-Hub 用ダウンロードロジック。

  - `presentation/cli/` … CLI プレゼンテーション層
    - `__init__.py`
    - `app.py` … エントリポイント (`pubmed` コマンド)。  
    - `commands/`
      - `search.py`
      - `download.py`
      - `show.py`
      - `export.py`
      - `config.py`
      - `doctor.py`

---

## 7. CLI 仕様 (Typer)

- コマンド例
  - `pubmed search "cancer genomics" --retmax 200 --mindate 2020/01/01 --save-db`
  - `pubmed download --sources pmc,unpaywall --max-workers 4 --output data/papers --enable-scihub`
  - `pubmed show <pmid>` … DB のメタデータとダウンロード履歴を表示。
  - `pubmed export --format csv --output exports/papers.csv`
  - `pubmed config validate --strict`
  - `pubmed doctor`

- UX ポリシー
  - すべてのコマンドで `--dry-run` サポート。  
  - 主要オプションは環境変数 (例: `PUBMED_DEFAULT_SOURCES`) で上書き可能。  
  - ログレベル/フォーマットは `--log-level` / `--log-format` で指定。

---

## 8. 設定と環境変数

- `PUBMED_API_KEY` … NCBI API key。  
- `PUBMED_TOOL_NAME`, `PUBMED_EMAIL` … NCBI に対するツール識別子と連絡先。  
- `UNPAYWALL_EMAIL` … Unpaywall API 用メールアドレス。  
- `PROXY_URL` … Sci-Hub / Unpaywall / PMC 用プロキシ。  
- `DATA_DIR` … PDF 保存ディレクトリ (デフォルト `data/papers`)。  
- `LOG_LEVEL`, `LOG_FORMAT` … ログ出力設定。  
- Botasaurus 関連:
  - `BOTASAURUS_PROFILE` … 使用するブラウザプロファイル名。  
  - `BOTASAURUS_MAX_BROWSERS` … 同時ブラウザ数の上限。  
  - `BOTASAURUS_PROXY` … Botasaurus 用プロキシ設定。
- `.env.example` … 必要なキー/推奨値を列挙したサンプルを用意。

---

## 9. テスト戦略・品質保証

- Lossless 保存の検証  
  - 代表的な EFetch / Unpaywall レスポンスサンプルを fixture 化し、保存された `raw_*` カラムと元レスポンスがバイトレベルで一致することを確認。  
  - 正規化カラムを増やしても raw_* の内容は変更しない (追記のみ) 方針。

- Botasaurus 統合のテスト  
  - `adapters.botasaurus.tasks_request` / `tasks_browser` のタスクは HTTP レイヤをモックした単体テストを書く。  
  - 実ブラウザを用いる E2E テストは少数 (代表的な 1〜2 ケース) に絞る。

- DB テスト  
  - SQLite インメモリ DB でスキーマ・制約・upsert ロジックを検証。  
  - CI で PostgreSQL コンテナを起動し、本番同等スキーマでもテストを実行。

- CLI テスト  
  - Typer の `CliRunner` で各コマンド (`search` / `download` / `show` / `export` / `doctor`) を E2E 風にテスト。

- 静的解析と CI  
  - `ruff` でフォーマット + Lint、`mypy` で型チェック (厳しすぎないが一貫した設定)。  
  - GitHub Actions で `uv` を用いた依存キャッシュつきワークフローを構築し、テスト/Lint/型チェックを自動実行。

---

## 10. 開発フェーズとマイルストーン

1. プロジェクト雛形  
   - `pyproject.toml` / `uv.lock` / `src` / `tests` / `presentation/cli` 雛形を作成。  
   - `config.settings` / `config.logging` / `config.observability` の最小実装。

2. 検索スタック  
   - `adapters.http.client` / `adapters.http.entrez` / `search.parser` / `search.ingest` を実装し、DB への upsert と raw_* 保存まで完了。  
   - `usecases.search.search_papers` と CLI `search` コマンドを実装。

3. ダウンロードスタック (Botasaurus 統合)  
   - `adapters.botasaurus.client` / `tasks_request` / `tasks_browser` を実装し、共通 PDF ダウンロードタスクを定義。  
   - `download.workflow` と `download.sources.(pmc|unpaywall|scihub)` を実装し、未ダウンロード論文の並列ダウンロードを実現。  
   - Download + raw_http_* の保存とステータス更新ロジックを完成させる。

4. CLI 拡張  
   - `presentation.cli.commands.(download|show|export|config|doctor)` を実装。  
   - `usecases.maintenance.run_doctor` / `validate_config` と連携。  
   - Sci-Hub の opt-in フラグや Botasaurus 関連設定を CLI から操作できるようにする。

5. テスト強化 & ドキュメント  
   - `pytest` + `ruff` + `mypy` のカバレッジを拡充。  
   - `.env.example` / README を更新し、Lossless 保存方針・Botasaurus 利用方針・ディレクトリ構成を明記。  
   - 必要に応じてアーキテクチャ図やシーケンス図を追加。

