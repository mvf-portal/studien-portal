#!/usr/bin/env bash
# Wartet, bis GitHub das Zertifikat fuer studien.m-vf.de ausgestellt hat,
# und erzwingt dann HTTPS. Bricht nach einer Stunde ab.
#
# Warum ueberhaupt warten: Nach einem DNS-Wechsel stellt GitHub das
# Zertifikat selbst aus, meist binnen einer Stunde. Vorher wird ein PUT mit
# https_enforced=true abgelehnt. Einmal probieren und aufgeben waere also
# zu frueh, dauernd probieren unhoeflich. Alle zwei Minuten reicht.
set -u
REPO="mvf-portal/studien-portal"
for i in $(seq 1 30); do
  zustand=$(gh api "repos/$REPO/pages" --jq '(.https_certificate.state)//"null"' 2>/dev/null)
  echo "$(date +%H:%M:%S)  Versuch $i/30  Zertifikat: $zustand"
  if [ "$zustand" = "approved" ]; then
    gh api -X PUT "repos/$REPO/pages" -F https_enforced=true >/dev/null 2>&1
    sleep 5
    erz=$(gh api "repos/$REPO/pages" --jq '.https_enforced' 2>/dev/null)
    echo "HTTPS erzwungen: $erz"
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 https://studien.m-vf.de/ || echo 000)
    echo "https://studien.m-vf.de/ -> HTTP $code"
    exit 0
  fi
  sleep 120
done
echo "Nach einer Stunde kein Zertifikat. Zustand: $zustand"
echo "Das ist kein Fehler, GitHub braucht nach einem DNS-Wechsel"
echo "gelegentlich laenger. Spaeter erneut laufen lassen."
exit 1
