#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# patch_frontend.sh — Patch the Relate frontend to point at a new backend URL
# ─────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/patch_frontend.sh <NEW_BACKEND_URL>
#
# Example:
#   ./scripts/patch_frontend.sh https://relationshipos-api.onrender.com/api/v1
#
# This downloads the deployed frontend, replaces the hardcoded backend URL,
# and outputs a patched static site in ./frontend_patched/ ready to redeploy.
# ─────────────────────────────────────────────────────────────

set -euo pipefail

OLD_URL="https://8000-ila4lefkdy2ix5vvaacvh-8fd35693.sg1.manus.computer/api/v1"
NEW_URL="${1:?Usage: $0 <NEW_BACKEND_URL>}"
FRONTEND_URL="https://relateapp-q2dmbaem.manus.space"
OUT_DIR="./frontend_patched"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  RelationshipOS — Frontend Patcher                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Old backend URL: ${OLD_URL}"
echo "New backend URL: ${NEW_URL}"
echo ""

# 1. Download the frontend
echo "→ Downloading frontend from ${FRONTEND_URL}..."
rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}/assets"

curl -sL "${FRONTEND_URL}/" -o "${OUT_DIR}/index.html"
# Extract asset paths from index.html
JS_FILE=$(grep -oP 'src="/assets/[^"]+' "${OUT_DIR}/index.html" | sed 's|src="/||')
CSS_FILE=$(grep -oP 'href="/assets/[^"]+\.css' "${OUT_DIR}/index.html" | sed 's|href="/||')

echo "   JS:  ${JS_FILE}"
echo "   CSS: ${CSS_FILE}"

curl -sL "${FRONTEND_URL}/${JS_FILE}" -o "${OUT_DIR}/${JS_FILE}"
curl -sL "${FRONTEND_URL}/${CSS_FILE}" -o "${OUT_DIR}/${CSS_FILE}"

# 2. Patch the JS bundle
echo "→ Patching API URL in JS bundle..."
ESCAPED_OLD=$(printf '%s\n' "$OLD_URL" | sed 's/[&/\]/\\&/g')
ESCAPED_NEW=$(printf '%s\n' "$NEW_URL" | sed 's/[&/\]/\\&/g')
sed -i "s|${ESCAPED_OLD}|${ESCAPED_NEW}|g" "${OUT_DIR}/${JS_FILE}"

# Also patch the truncated display URL in the settings page
sed -i "s|8000-ila4lefkdy2ix5vvaacvh\.\.\.|$(echo "$NEW_URL" | cut -c1-30)...|g" "${OUT_DIR}/${JS_FILE}"

# 3. Patch index.html meta tags
sed -i "s|${ESCAPED_OLD}|${ESCAPED_NEW}|g" "${OUT_DIR}/index.html"

# 4. Verify
MATCHES=$(grep -c "${NEW_URL}" "${OUT_DIR}/${JS_FILE}" 2>/dev/null || echo "0")
echo ""
echo "✓ Patched ${MATCHES} occurrence(s) in JS bundle"
echo "✓ Output directory: ${OUT_DIR}/"
echo ""
echo "To deploy the patched frontend:"
echo "  • Netlify:  cd ${OUT_DIR} && npx netlify deploy --prod --dir=."
echo "  • Vercel:   cd ${OUT_DIR} && npx vercel --prod"
echo "  • Render:   Push ${OUT_DIR}/ as a Static Site"
echo ""
echo "Done!"
