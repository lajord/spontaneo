#!/bin/bash
# Cron job — envoi automatique des mails Spontaneo
# À appeler toutes les minutes via crontab :
#
#   crontab -e
#   * * * * * /bin/bash /path/to/spontaneo/cron/send-emails.sh >> /var/log/spontaneo-cron.log 2>&1
#
# Variables d'environnement requises (ou à définir ici) :
#   APP_URL      : URL de l'application  (ex. http://localhost:3000)
#   CRON_SECRET  : secret défini dans .env.local

APP_URL="${APP_URL:-http://localhost:3000}"
CRON_SECRET="${CRON_SECRET:-}"

if [ -z "$CRON_SECRET" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: CRON_SECRET is not set"
  exit 1
fi

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  "${APP_URL}/api/cron/send-emails")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n1)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] HTTP ${HTTP_CODE} — ${BODY}"
