# 🚀 Spontaneo

> Candidatures spontanées automatiques, propulsées par l'IA.

## Stack

| Couche | Technologie |
|--------|-------------|
| Frontend | Next.js 15, React, TypeScript |
| Styling | Tailwind CSS |
| Auth | BetterAuth |
| Database | Supabase (PostgreSQL) + Prisma |
| Backend IA | FastAPI (Python) |
| Hosting | Vercel |

## Structure

```
apps/
├── web/           → Next.js (frontend + API routes)
└── ai-service/    → FastAPI (service IA)
```

## Setup

### 1. Web App (Next.js)

```bash
cd apps/web
cp .env.example .env     # Remplir les variables
npm install
npx prisma generate
npx prisma db push       # Push le schema vers Supabase
npm run dev               # → http://localhost:3000
```

### 2. AI Service (FastAPI)

```bash
cd apps/ai-service
python -m venv venv
venv\Scripts\activate     # Windows
pip install -r requirements.txt
cp .env.example .env      # Remplir la clé OpenAI
uvicorn app.main:app --reload  # → http://localhost:8000
```

## Développement

- **Web** : `http://localhost:3000`
- **API IA** : `http://localhost:8000`
- **Docs API IA** : `http://localhost:8000/docs`
- **Prisma Studio** : `npx prisma studio`
