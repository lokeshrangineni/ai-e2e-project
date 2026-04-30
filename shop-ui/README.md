# Shop UI

React + TypeScript + Vite frontend for ShopChat.

## Features

- Chat interface with streaming (SSE) responses
- Role selector (Customer / Operator / Admin) — mock auth via headers
- Customer selector per role
- Markdown rendering for assistant responses

## Setup

```bash
npm install
npm run dev       # http://localhost:5173
```

## Build & Lint

```bash
npm run build     # Production build (includes type check)
npm run lint      # ESLint
```

## Configuration

The backend URL is configured in `src/config.ts` (defaults to `http://localhost:8000`).
