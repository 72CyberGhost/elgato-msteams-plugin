#!/bin/zsh
# Install the plugin into the Stream Deck plugins directory and restart the app.

set -euo pipefail

PLUGIN_SRC="$(cd "$(dirname "$0")/com.panda.msteams.sdPlugin" && pwd)"
PLUGIN_ID="com.panda.msteams"
PLUGINS_DIR="$HOME/Library/Application Support/com.elgato.StreamDeck/Plugins"
DEST="$PLUGINS_DIR/$PLUGIN_ID.sdPlugin"

# Stop Stream Deck if running
if pgrep -x "Stream Deck" > /dev/null 2>&1; then
    echo "→ Stopping Stream Deck..."
    osascript -e 'quit app "Stream Deck"'
    sleep 2
fi

# Remove previous installation
if [[ -d "$DEST" ]]; then
    echo "→ Removing previous installation..."
    rm -rf "$DEST"
fi

# Copy plugin files (exclude .venv, __pycache__, .DS_Store)
echo "→ Copying plugin to $DEST..."
rsync -a \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    "$PLUGIN_SRC/" "$DEST/"

# Create venv and install dependencies
echo "→ Creating virtual environment..."
python3 -m venv "$DEST/.venv"
echo "→ Installing dependencies..."
"$DEST/.venv/bin/pip" install --quiet -r "$DEST/requirements.txt"

chmod +x "$DEST/launch.sh"

echo "→ Starting Stream Deck..."
open -a "Stream Deck"

echo "✓ Deploy complete: $DEST"
