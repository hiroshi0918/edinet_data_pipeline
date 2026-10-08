# EDINET ダッシュボード (React)

Vite + React 19 + TypeScript。Rails API は `http://localhost:3000` を想定し、Vite が `/api` をプロキシします。

読む順: `src/routes.tsx` → `src/lib/api.ts` → `src/hooks/use-filters.ts` → `src/pages/`。shadcn の `src/components/ui/` は生成物なので後回しでよいです。

## 起動

```bash
# ターミナル 1: Rails API
cd ..
bin/rails server -p 3000

# ターミナル 2: フロント
npm install
npm run dev
```

ブラウザで Vite の URL（通常 `http://localhost:5173`）を開きます。

## テスト

```bash
npm test
```
