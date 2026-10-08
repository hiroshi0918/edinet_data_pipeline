# EDINET Dashboard（Rails + React）

会社図鑑の画面。PostgreSQL 直読みの Rails API と React SPA。入口は表紙（社名検索と業種の目次）、ランキング、日経225一覧。見た目の決まりは [frontend/DESIGN_SYSTEM.md](frontend/DESIGN_SYSTEM.md)。選んだ会社は `GET /companies/:code/sheet` のシート。パイプライン本体（Python）と Streamlit は触らない。

- JSON は snake_case、GET のみ。契約は [API_CONTRACT.md](API_CONTRACT.md)
- スキーマ正本はリポジトリルートの Alembic。`bin/rails db:migrate` は使わない
- 開発時は Vite (`http://localhost:5173`) が `/api` を Rails (`:3000`) へ proxy

## コードの読み順

1. [API_CONTRACT.md](API_CONTRACT.md) — 画面と JSON の対応
2. `config/routes.rb` — エンドポイント一覧
3. `app/queries/dimension.rb` — 許可リストと閾値
4. `app/queries/*.rb` — SQL（`data.py` の移植）。スポットライトは `spotlight_query.rb`
5. `app/controllers/api/v1/` — パラメータを Query に渡すだけ
6. `frontend/src/routes.tsx` — React Router
7. `frontend/src/hooks/use-filters.ts` — URL とフィルタの同期
8. `frontend/src/pages/` — 各画面

## 起動

リポジトリルートで Postgres を起動する。

```bash
docker compose up -d db
```

依存関係のインストール、テスト DB `edinet_db_test` の作成、Alembic の適用:

```bash
cd web
bin/setup
```

API とフロントを同時起動:

```bash
bin/dev
```

- API: `http://localhost:3000/api/v1/meta`
- UI: `http://localhost:5173`（Vite が `/api` を Rails へ proxy）

シートの企業ロゴは [logo.dev](https://www.logo.dev/) の画像 URL。`frontend/.env` に publishable key（`pk_`）だけ置く。secret key は使わない。未設定、証券コードなし、ロゴ無しのときは社名の頭文字になる。

```bash
# frontend/.env
VITE_LOGO_DEV_PUBLISHABLE_KEY=pk_...
```

別々に起動する場合:

```bash
bin/rails s
# 別ターミナル
npm --prefix frontend run dev
```

## テスト

```bash
cd web
bundle exec rspec
```

テストは `edinet_db_test` だけを使う。開発 DB `edinet_db` は叩かない。

フロント:

```bash
npm --prefix frontend test
```

Ruby の PATH 例:

```bash
export PATH="/opt/homebrew/lib/ruby/gems/3.4.0/bin:/opt/homebrew/opt/ruby/bin:$PATH"
```
