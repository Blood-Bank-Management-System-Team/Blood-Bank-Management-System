#!/usr/bin/env bash
# Runs ON THE SERVER (copied there by .github/workflows/cd.yml, or run it by hand).
#
#   echo "<registry token>" | ./deploy.sh <image> <tag> <registry-user>
#
# Expects docker-compose.prod.yml and a filled-in .env in the same directory.
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "usage: $0 <image> <tag> <registry-user>  (registry token on stdin)" >&2
    exit 2
fi

IMAGE="$1"
TAG="$2"
REGISTRY_USER="$3"

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Missing .env next to docker-compose.prod.yml. Create it from .env.example first." >&2
    exit 1
fi

IFS= read -r REGISTRY_TOKEN
printf '%s' "$REGISTRY_TOKEN" | docker login ghcr.io -u "$REGISTRY_USER" --password-stdin
trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT

export WEB_IMAGE="$IMAGE"
export IMAGE_TAG="$TAG"
COMPOSE="docker compose -f docker-compose.prod.yml"

$COMPOSE pull
$COMPOSE up -d --remove-orphans --wait --wait-timeout 180

echo "$TAG" > .deployed_tag
docker image prune -f >/dev/null
echo "Deployed ${IMAGE}:${TAG}"
