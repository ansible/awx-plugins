#!/bin/bash
set -euo pipefail
echo on


# Define variables
APP_ID="1121547"
INSTALLATION_ID="60185608"
NOW=$(date +%s)
EXP=$(($NOW + 600))  # Token valid for 10 minutes
HEADER='{
  "alg": "RS256",
  "typ": "JWT"
}'
PAYLOAD="{
  \"iat\": $NOW,
  \"exp\": $EXP,
  \"iss\": \"$APP_ID\"
}"
PEM="/home/arestlel/Downloads/arestlel-github-app-ansible.2025-01-23.private-key.pem"

# Encode header and payload
HEADER_B64=$(echo -n "$HEADER" | openssl base64 -e -A | tr -d '=' | tr '/+' '_-')
PAYLOAD_B64=$(echo -n "$PAYLOAD" | openssl base64 -e -A | tr -d '=' | tr '/+' '_-')
# Sign the token
SIGNATURE=$(echo -n "$HEADER_B64.$PAYLOAD_B64" | openssl dgst -sha256 -sign $PEM | openssl base64 -e -A | tr -d '=' | tr '/+' '_-')
# Create final JWT
JWT="$HEADER_B64.$PAYLOAD_B64.$SIGNATURE"
echo "JWT: $JWT"

URL="https://api.github.com/app/installations/$INSTALLATION_ID/access_tokens"

RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Accept: application/vnd.github+json" \
    $URL)

TOKEN=$(echo "$RESPONSE" | jq -r .token)

if [[ "$TOKEN" == "null" || -z "$TOKEN" ]]; then
    echo "Failed to retrieve GitHub token."
    exit 1
fi

echo "Token: $TOKEN"