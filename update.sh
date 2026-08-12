#!/bin/zsh
# Sync source files only, without recreating the venv.
# Faster than deploy.sh for iterative development.

set -euo pipefail

PLUGIN_SRC="$(cd "$(dirname "$0")/com.panda.msteams.sdPlugin" && pwd)"
PLUGIN_ID="com.panda.msteams"
DEST="$HOME/Library/Application Support/com.elgato.StreamDeck/Plugins/$PLUGIN_ID.sdPlugin"

if [[ ! -d "$DEST" ]]; then
    echo "✗ Plugin not installed. Run deploy.sh first." >&2
    exit 1
fi

# Stop Stream Deck
if pgrep -f "Elgato Stream Deck" > /dev/null 2>&1; then
    echo "→ Stopping Stream Deck..."
    osascript -e 'quit app "Elgato Stream Deck"' 2>/dev/null || true
    sleep 2
fi

# Sync source files only
echo "→ Syncing source files..."
rsync -a \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    "$PLUGIN_SRC/" "$DEST/"

chmod +x "$DEST/launch.sh"

echo "→ Starting Stream Deck..."
open -a "Elgato Stream Deck"

echo "✓ Update complete."
