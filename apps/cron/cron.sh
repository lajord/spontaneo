#!/bin/sh
# Appelle l'endpoint cron de la web app toutes les 60 secondes

URL="${CRON_URL:-http://web:3000/api/cron/send-emails}"

echo "[cron] Démarrage — URL: $URL"

while true; do
  TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  RESULT=$(curl -sf \
    -H "Authorization: Bearer ${CRON_SECRET}" \
    -H "Content-Type: application/json" \
    "$URL" 2>&1)

  if [ $? -eq 0 ]; then
    echo "[cron] $TIMESTAMP OK — $RESULT"
  else
    echo "[cron] $TIMESTAMP ERREUR — $RESULT"
  fi

  sleep 60
done
