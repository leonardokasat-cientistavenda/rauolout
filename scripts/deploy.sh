#!/usr/bin/env bash
# Deploy raulout para Cloudflare Pages.
# Lê o CF token e account ID de variáveis de ambiente — NÃO commitar essas.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "✘ CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID precisam estar no env" >&2
  exit 1
fi

echo "→ build"
python3 scripts/build.py

echo "→ git commit (se houver mudança)"
git add -A
git commit -m "update: rebuild $(date +%Y-%m-%d_%H:%M)" 2>/dev/null || echo "  (nada novo)"
git push -q

echo "→ deploy"
npx -y wrangler@latest pages deploy site \
  --project-name=raulout --branch=main --commit-dirty=true
