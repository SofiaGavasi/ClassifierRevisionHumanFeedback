# RGR web frontend

Vite + React + KaTeX + d3-graphviz. Talks to the FastAPI backend at `/api/*` (proxied to `localhost:8000` in dev).

## Run (dev)

```bash
cd web/app
npm install
npm run dev
```

The backend must be running (`web/server/README.md`). Open `http://localhost:5173`.

## Adding a new algorithm

1. Add a new endpoint on the backend (`POST /api/revise/<name>`) that returns the standard `Trace` shape.
2. Add an entry to `ALGORITHMS` in `src/App.tsx`.

