#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import websocket

from accessibility import leave_meeting, meeting_state, toggle_camera, toggle_hand, toggle_mute

PLUGIN_UUID = "com.panda.msteams"
PLUGIN_DIR = Path(__file__).parent

ACTION_MUTE = "com.panda.msteams.toggle-mic"
ACTION_CAMERA = "com.panda.msteams.toggle-camera"
ACTION_HAND = "com.panda.msteams.toggle-hand"
ACTION_LEAVE = "com.panda.msteams.leave-meeting"

IDLE_IMAGE = {
    ACTION_MUTE:   "idle_mic.png",
    ACTION_CAMERA: "idle_cam.png",
    ACTION_HAND:   "idle_hand.png",
    ACTION_LEAVE:  "idle_leave.png",
}

POLL_INTERVAL = 3.0


class PluginState:
    def __init__(self) -> None:
        self.in_meeting: bool = False
        self.mic_muted: bool | None = None
        self.cam_off: bool | None = None
        self.hand_raised: bool | None = None
        self.contexts: dict[str, str] = {}
        self.lock = threading.Lock()


def send(ws: websocket.WebSocket, event: str, payload: dict) -> None:
    ws.send(json.dumps({"event": event, **payload}))


def set_image(ws: websocket.WebSocket, context: str, filename: str) -> None:
    path = PLUGIN_DIR / "images" / filename
    send(ws, "setImage", {
        "context": context,
        "payload": {"image": str(path), "target": 0},
    })


def show_alert(ws: websocket.WebSocket, context: str) -> None:
    send(ws, "showAlert", {"context": context})


def _image_for(action: str, state: PluginState) -> str:
    if action == ACTION_MUTE:
        return "mute.png" if state.mic_muted else "unmuted.png"
    if action == ACTION_CAMERA:
        return "cam_off.png" if state.cam_off else "cam_on.png"
    if action == ACTION_HAND:
        return "hand_raised.png" if state.hand_raised else "hand_down.png"
    if action == ACTION_LEAVE:
        return "leave.png"
    return "idle_mic.png"


def _sync_camera(ws: websocket.WebSocket, context: str, state: PluginState) -> None:
    with state.lock:
        old = state.cam_off
    for _ in range(10):
        _, _, cam_off, _ = meeting_state()
        if cam_off is not None and cam_off != old:
            with state.lock:
                state.cam_off = cam_off
            set_image(ws, context, "cam_off.png" if cam_off else "cam_on.png")
            return
        threading.Event().wait(0.1)


def _sync_hand(ws: websocket.WebSocket, context: str, state: PluginState) -> None:
    with state.lock:
        old = state.hand_raised
    for _ in range(10):
        _, _, _, hand_raised = meeting_state()
        if hand_raised is not None and hand_raised != old:
            with state.lock:
                state.hand_raised = hand_raised
            set_image(ws, context, "hand_raised.png" if hand_raised else "hand_down.png")
            return
        threading.Event().wait(0.1)


def _sync_mic(ws: websocket.WebSocket, context: str, state: PluginState) -> None:
    with state.lock:
        old = state.mic_muted
    for _ in range(10):
        _, mic_muted, _, _ = meeting_state()
        if mic_muted is not None and mic_muted != old:
            with state.lock:
                state.mic_muted = mic_muted
            set_image(ws, context, "mute.png" if mic_muted else "unmuted.png")
            return
        threading.Event().wait(0.1)


def refresh_all(ws: websocket.WebSocket, state: PluginState, in_meeting: bool) -> None:
    with state.lock:
        contexts = dict(state.contexts)
    for context, action in contexts.items():
        if in_meeting:
            set_image(ws, context, _image_for(action, state))
        else:
            set_image(ws, context, IDLE_IMAGE.get(action, "idle_mic.png"))


def poll_meeting(ws: websocket.WebSocket, state: PluginState) -> None:
    in_meeting, mic_muted, cam_off, hand_raised = meeting_state()
    with state.lock:
        meeting_changed = in_meeting != state.in_meeting
        mic_changed = in_meeting and mic_muted is not None and mic_muted != state.mic_muted
        cam_changed = in_meeting and cam_off is not None and cam_off != state.cam_off
        hand_changed = in_meeting and hand_raised is not None and hand_raised != state.hand_raised
        state.in_meeting = in_meeting
        if in_meeting:
            if mic_muted is not None:
                state.mic_muted = mic_muted
            if cam_off is not None:
                state.cam_off = cam_off
            if hand_raised is not None:
                state.hand_raised = hand_raised
    if meeting_changed or mic_changed or cam_changed or hand_changed:
        refresh_all(ws, state, in_meeting)
    t = threading.Timer(POLL_INTERVAL, poll_meeting, args=(ws, state))
    t.daemon = True
    t.start()


def handle_key_down(ws: websocket.WebSocket, action: str, context: str, state: PluginState) -> None:
    with state.lock:
        in_meeting = state.in_meeting

    if not in_meeting:
        return

    if action == ACTION_MUTE:
        ok, _ = toggle_mute()
        if ok:
            threading.Thread(target=_sync_mic, args=(ws, context, state), daemon=True).start()
        else:
            show_alert(ws, context)

    elif action == ACTION_CAMERA:
        ok, _ = toggle_camera()
        if ok:
            threading.Thread(target=_sync_camera, args=(ws, context, state), daemon=True).start()
        else:
            show_alert(ws, context)

    elif action == ACTION_HAND:
        ok, _ = toggle_hand()
        if ok:
            threading.Thread(target=_sync_hand, args=(ws, context, state), daemon=True).start()
        else:
            show_alert(ws, context)

    elif action == ACTION_LEAVE:
        ok, _ = leave_meeting()
        if not ok:
            show_alert(ws, context)


def handle_will_appear(ws: websocket.WebSocket, action: str, context: str, state: PluginState) -> None:
    with state.lock:
        state.contexts[context] = action
        in_meeting = state.in_meeting
    if in_meeting:
        set_image(ws, context, _image_for(action, state))
    else:
        set_image(ws, context, IDLE_IMAGE.get(action, "idle_mic.png"))


def handle_will_disappear(_ws: websocket.WebSocket, _action: str, context: str, state: PluginState) -> None:
    with state.lock:
        state.contexts.pop(context, None)


def run(port: int, plugin_uuid: str) -> None:
    ws = websocket.create_connection(f"ws://127.0.0.1:{port}")
    send(ws, "registerPlugin", {"uuid": plugin_uuid})

    state = PluginState()
    poll_meeting(ws, state)

    while True:
        message = json.loads(ws.recv())
        event = message.get("event")
        action = message.get("action", "")
        context = message.get("context", "")

        if event == "keyDown" and action:
            handle_key_down(ws, action, context, state)
        elif event == "willAppear" and action:
            handle_will_appear(ws, action, context, state)
        elif event == "willDisappear" and action:
            handle_will_disappear(ws, action, context, state)
        elif event in ("titleParametersDidChange", "didReceiveSettings") and action:
            with state.lock:
                in_meeting = state.in_meeting
            if in_meeting:
                set_image(ws, context, _image_for(action, state))
            else:
                set_image(ws, context, IDLE_IMAGE.get(action, "idle_mic.png"))


def main() -> int:
    args = sys.argv[1:]
    try:
        port = int(args[args.index("-port") + 1])
        plugin_uuid = args[args.index("-pluginUUID") + 1]
    except (ValueError, IndexError):
        print("Expected -port <port> -pluginUUID <uuid>", file=sys.stderr)
        return 2
    run(port, plugin_uuid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
