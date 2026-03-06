/**
 * PM2 ecosystem config — déploiement full VPS
 *
 * Prérequis :
 *   - apps/web/.env.local        → variables Next.js
 *   - apps/worker/.env           → variables worker
 *   - apps/ai-service/.env       → variables FastAPI
 *
 * Commandes :
 *   pm2 start ecosystem.config.js   → démarrer tous les process
 *   pm2 restart all                 → redémarrer
 *   pm2 logs                        → voir les logs
 *   pm2 status                      → état des process
 *   pm2 save && pm2 startup         → lancer au démarrage du serveur
 */

module.exports = {
  apps: [
    // ── Frontend + API (Next.js) ───────────────────────────────────────────────
    {
      name: 'spontaneo-web',
      cwd: 'apps/web',
      script: 'node_modules/.bin/next',
      args: 'start --port 3000',
      interpreter: 'none',
      env_file: '.env.local',
      env: {
        NODE_ENV: 'production',
      },
      autorestart: true,
      watch: false,
    },

    // ── Service IA (FastAPI Python) ────────────────────────────────────────────
    {
      name: 'spontaneo-ai',
      cwd: 'apps/ai-service',
      script: 'uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 8000 --workers 4',
      interpreter: 'none',
      autorestart: true,
      watch: false,
    },

    // ── Worker d'enrichissement (Node.js) ─────────────────────────────────────
    {
      name: 'spontaneo-worker',
      cwd: 'apps/worker',
      script: 'dist/index.js',
      interpreter: 'node',
      env_file: '.env',
      env: {
        NODE_ENV: 'production',
      },
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
    },
  ],
}
