# ─── Stage 1 : build ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
# Installe TOUS les deps (prisma CLI est en devDependencies)
RUN npm ci

COPY prisma ./prisma
RUN npx prisma generate

COPY src        ./src
COPY tsconfig.json .
RUN npm run build

# ─── Stage 2 : image de production ───────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Copie les node_modules (inclut le client Prisma généré) et le code compilé
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist         ./dist

EXPOSE 3001

CMD ["node", "dist/index.js"]
