#!/usr/bin/env bash
# Render docs/diagrams/*.mmd -> *.svg. Uses kroki.io (only needs curl).
# Offline alternative: `mmdc -i x.mmd -o x.svg` (npm i -g @mermaid-js/mermaid-cli).
set -euo pipefail
cd "$(dirname "$0")/../docs/diagrams"
for mmd in *.mmd; do
  svg="${mmd%.mmd}.svg"
  echo "rendering $mmd -> $svg"
  curl -fsS -X POST --data-binary "@$mmd" https://kroki.io/mermaid/svg -o "$svg"
done
echo "done"
