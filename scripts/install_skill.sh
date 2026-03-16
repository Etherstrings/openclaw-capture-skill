#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_SRC="$ROOT_DIR/openclaw-capture"
SKILL_DEST="$HOME/.openclaw/workspace/skills/openclaw-capture"

mkdir -p "$HOME/.openclaw/workspace/skills"
rm -rf "$SKILL_DEST"
cp -R "$SKILL_SRC" "$SKILL_DEST"

echo "Installed skill to $SKILL_DEST"

