/**
 * PM2 ecosystem config - deploiement full VPS
 */

module.exports = {
  apps: [
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
    {
      name: 'spontaneo-ai',
      cwd: 'apps/ai-service',
      script: 'uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 8000 --workers 4',
      interpreter: 'none',
      autorestart: true,
      watch: false,
    },
    {
      name: 'spontaneo-agent-worker',
      cwd: 'apps/ai-service',
      script: 'python',
      args: '-m app.agent_worker.main',
      interpreter: 'none',
      env_file: '.env',
      env: {
        WEB_URL: 'http://127.0.0.1:3000',
        AGENT_WORKER_MAX_CONCURRENT: '2',
        AGENT_WORKER_POLL_INTERVAL_MS: '5000',
        AGENT_WORKER_STALE_THRESHOLD_SECONDS: '3600',
      },
      autorestart: true,
      watch: false,
    },
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
