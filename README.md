# MS Teams Controls — Elgato Stream Deck Plugin

Stream Deck plugin for macOS that controls Microsoft Teams via the Accessibility API (AX), without using the official Stream Deck SDK.

## Features

| Action | Description |
|--------|-------------|
| Toggle Microphone | Mute / unmute the microphone |
| Toggle Camera | Turn the camera on / off |
| Toggle Hand | Raise / lower your hand |
| Leave Meeting | Leave the current meeting |

### Behaviour

- **No active meeting** — buttons show greyscale icons and do nothing when pressed.
- **Active meeting** — when a meeting starts, icons automatically sync with the real Teams state (mic muted, camera off, hand raised).
- **Viewer / live event mode** — when Teams is in viewer mode (only the Leave button is present), mic / camera / hand buttons show greyscale idle icons and are disabled; only Leave is active.
- **Instant update** — after pressing a button, a background thread polls the AX tree every 100 ms until the state changes (1 s timeout), updating the icon as soon as Teams reflects the action.
- **Background polling** — every 2 seconds the plugin checks the meeting state and syncs icons for any changes made directly in Teams.

## Requirements

- macOS 10.15+
- Microsoft Teams (classic or new)
- Elgato Stream Deck software 6.4+
- Python 3.11+
- **Accessibility** permission granted to the Python process: *System Settings → Privacy & Security → Accessibility*

## Project structure

```
elgato-msteams-plugin/
├── README.md
├── deploy.sh               # First install: copy plugin, create venv, install deps
├── update.sh               # Sync source files only (preserves venv)
├── uninstall.sh            # Remove the plugin
└── com.panda.msteams.sdPlugin/
    ├── manifest.json       # Plugin and action definitions
    ├── plugin.py           # Entry point: Stream Deck WebSocket event loop
    ├── accessibility.py    # Teams state reading and control via macOS AX API
    ├── teams_mute_mvp.py   # CLI debug tool: inspect AX tree, dry-run mute
    ├── launch.sh           # Launcher script invoked by Stream Deck
    ├── requirements.txt    # Python dependencies
    └── images/
        ├── pluginIcon.png
        ├── unmuted.png         # Mic on
        ├── mute.png            # Mic off
        ├── cam_on.png          # Camera on
        ├── cam_off.png         # Camera off
        ├── hand_down.png       # Hand lowered (raise hand available)
        ├── hand_raised.png     # Hand raised (lower hand available)
        ├── leave.png           # Leave meeting
        ├── idle_mic.png        # Greyscale variant — no active meeting or unavailable
        ├── idle_cam.png
        ├── idle_hand.png
        └── idle_leave.png
```

## Installation

Use the provided scripts from the project root:

```sh
./deploy.sh      # first install
./update.sh      # sync source files only (faster, preserves venv)
./uninstall.sh   # remove the plugin
```

### Manual installation

1. Copy the plugin folder to the Stream Deck plugins directory:
   ```sh
   cp -r com.panda.msteams.sdPlugin \
     ~/Library/Application\ Support/com.elgato.StreamDeck/Plugins/
   ```

2. Create the virtual environment and install dependencies:
   ```sh
   cd ~/Library/Application\ Support/com.elgato.StreamDeck/Plugins/com.panda.msteams.sdPlugin
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. Grant Accessibility permission to the Python process:
   *System Settings → Privacy & Security → Accessibility → add `.venv/bin/python`*

4. Restart Stream Deck — the plugin appears under the **Microsoft Teams** category.

## Architecture

The plugin connects to Stream Deck over WebSocket (native SDK v2 protocol) with no third-party SDK dependency.

**`plugin.py`** drives the WebSocket event loop and holds a thread-safe `PluginState` tracking the current mic, camera, and hand state. A recursive timer runs background polling every 2 seconds; on button press, a dedicated thread detects the AX state change in real time. The event dispatcher uses Python `match`/`case` for both the Stream Deck event loop and action routing.

**`accessibility.py`** queries the Teams AX tree via `pyobjc-framework-ApplicationServices`. The `meeting_state()` function does a single tree walk and returns `(in_meeting, mic_muted, cam_off, hand_raised)`. Meeting detection uses the mic button as primary indicator; if absent, the Leave button is checked to handle viewer/live event mode. Hand-raised state is derived from the button label: `"Lower your hand"` → raised, `"Raise your hand"` → lowered.
