# ─── Stage 1 : dépendances ───────────────────────────────────────────────────
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# ─── Stage 2 : build ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# S'assure que le dossier public existe (Next.js le requiert en standalone)
RUN mkdir -p public

ENV NEXT_TELEMETRY_DISABLED=1

# URL bidon pour que next build puisse importer prisma.ts sans crasher
# (la vraie DATABASE_URL est fournie au runtime via env_file dans docker-compose)
ENV DATABASE_URL=postgresql://localhost/build-placeholder


RUN npx prisma generate
RUN npm run build

# ─── Stage 3 : image de production ───────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static    ./.next/static
# Le client Prisma (binaire natif) n'est pas toujours inclus dans standalone
COPY --from=builder --chown=nextjs:nodejs /app/node_modules/.prisma ./node_modules/.prisma

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
