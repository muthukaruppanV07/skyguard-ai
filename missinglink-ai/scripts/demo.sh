#!/usr/bin/env bash
#
# MissingLink AI — end-to-end demo workflow.
# Requires: docker, docker compose, curl, jq, and an image to test with.
#
#   usage: scripts/demo.sh [--with-photo /path/to/sighting.jpg]
#
set -euo pipefail

BASE="http://localhost:8080/api/v1"
AI="http://localhost:8000"
API_KEY="${AI_SERVICE_API_KEY:-change-me-ai-gateway-key}"
PHOTO="${1:-}"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
json() { jq -r "$1" <<<"$2"; }

say "Starting Postgres + Redis + backend + AI + frontend"
docker compose up -d --build

say "Waiting for backend to be healthy (up to 120s)"
for i in $(seq 1 60); do
  if curl -sf -o /dev/null "http://localhost:8080/actuator/health"; then break; fi
  sleep 2
done

say "AI service status"
curl -s "$AI/v1/status" | jq .

say "Registering a public reporter"
PUB_TOKEN=$(curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"demo.reporter@example.com","password":"DemoPass1","fullName":"Demo Reporter"}' \
  | jq -r .accessToken)
PUB_AUTH="Authorization: Bearer $PUB_TOKEN"
echo "token: ${PUB_TOKEN:0:24}…"

say "Registering an investigator"
INV_TOKEN=$(curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"demo.investigator@example.com","password":"DemoPass1","fullName":"Demo Investigator"}' \
  | jq -r .accessToken)
INV_AUTH="Authorization: Bearer $INV_TOKEN"

say "Promoting investigator via admin endpoint"
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@missinglink.local","password":"password"}' | jq -r .accessToken)
curl -s -X POST "$BASE/admin/users/promote" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo.investigator@example.com","role":"INVESTIGATOR"}'
echo

say "Creating a public missing-person case (child, Bengaluru)"
CASE_ID=$(curl -s -X POST "$BASE/cases" -H "$PUB_AUTH" -H 'Content-Type: application/json' \
  -d '{"firstName":"Aarav","lastName":"Sharma","age":9,"gender":"MALE","heightCm":128,
       "lastSeenClothing":"blue jacket and black backpack","lastKnownPlace":"MG Road, Bengaluru",
       "lastKnownAt":"2026-08-09T06:30:00Z","isPublic":true}' | jq -r .id)
echo "case id: $CASE_ID"

say "Submitting a sighting with a photo (runs vision + matching pipeline)"
FORM_DATA=(-F "description=child wearing a blue jacket with a black backpack walking on MG Road")
FORM_DATA+=(-F "lat=12.9756" -F "lng=77.6041")
FORM_DATA+=(-F "locationName=MG Road, Bengaluru")
if [[ -n "$PHOTO" ]]; then
  FORM_DATA+=(-F "photo=@${PHOTO}")
fi
SIGHTING_REF=$(curl -s -X POST "$BASE/sightings" -H "$PUB_AUTH" "${FORM_DATA[@]}" | jq -r .sightingReference)
echo "sighting reference: $SIGHTING_REF"

say "Waiting a few seconds for async AI match review"
sleep 8

say "Investigator match queue"
curl -s "$BASE/matches" -H "$INV_AUTH" | jq .

say "Public case map"
curl -s "$BASE/cases/public" | jq . | head -40

say "Done. Frontend: http://localhost:3000  |  AI docs: $AI/docs"
