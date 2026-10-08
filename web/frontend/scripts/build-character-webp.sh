#!/usr/bin/env bash
# public/characters/*.png から、シート用（幅768px）と一覧・行進用（幅256px）の WebP を作る。
# 要 cwebp（macOS: brew install webp / Debian: apt install webp）。
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
src="$root/public/characters"
full="$src/webp"
thumb="$src/thumb"
mkdir -p "$full" "$thumb"

for png in "$src"/*.png; do
  name="$(basename "$png" .png)"
  cwebp -quiet -q 82 -alpha_q 90 -resize 768 0 "$png" -o "$full/$name.webp"
  cwebp -quiet -q 80 -alpha_q 85 -resize 256 0 "$png" -o "$thumb/$name.webp"
done
