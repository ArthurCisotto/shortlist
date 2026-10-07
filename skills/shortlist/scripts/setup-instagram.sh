#!/usr/bin/env bash
set -euo pipefail
skill_scripts=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
instagram_tool_dir="$HOME/.local/share/shortlist/instagram"
npm install --prefix "$instagram_tool_dir" @i7m/instagram-cli@2.0.1 --no-audit --no-fund
# Upstream patches live inside the installed package; apply them to the tool root.
(
  cd -- "$instagram_tool_dir"
  node node_modules/patch-package/index.js --patch-dir node_modules/@i7m/instagram-cli/patches --error-on-fail
)
node "$skill_scripts/instagram.cjs" doctor
