#!/bin/zsh

PLUGIN="$HOME/Library/Application Support/com.elgato.StreamDeck/Plugins/com.panda.msteams.sdPlugin"
exec "$PLUGIN/.venv/bin/python" "$PLUGIN/plugin.py" "$@"
