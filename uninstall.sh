#!/bin/zsh
# Remove the plugin from Stream Deck.

set -euo pipefail

PLUGIN_ID="com.panda.msteams"
DEST="$HOME/Library/Application Support/com.elgato.StreamDeck/Plugins/$PLUGIN_ID.sdPlugin"

if [[ ! -d "$DEST" ]]; then
    echo "Plugin not installed, nothing to do."
    exit 0
fi

if pgrep -x "Stream Deck" > /dev/null 2>&1; then
    echo "→ Stopping Stream Deck..."
    osascript -e 'quit app "Stream Deck"'
    sleep 2
fi

echo "→ Removing $DEST..."
rm -rf "$DEST"

echo "→ Starting Stream Deck..."
open -a "Stream Deck"

echo "✓ Plugin removed."
