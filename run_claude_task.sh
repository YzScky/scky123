#!/usr/bin/env bash
set -euo pipefail

PROMPT="${1:-}"
if [ -z "$PROMPT" ]; then
  echo "用法: /cc 你的问题"
  exit 1
fi

cd /Users/qinzimu/Documents/Playground
/opt/homebrew/bin/claude "$PROMPT"
