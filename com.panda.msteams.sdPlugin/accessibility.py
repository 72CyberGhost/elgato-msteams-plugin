from __future__ import annotations

import subprocess
import time
from typing import Any, Iterable

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
)

AX_ROLE = "AXRole"
AX_TITLE = "AXTitle"
AX_DESC = "AXDescription"
AX_VALUE = "AXValue"
AX_CHILDREN = "AXChildren"
AX_BUTTON = "AXButton"
AX_PRESS = "AXPress"
kAXEnhancedUserInterfaceAttribute = "AXEnhancedUserInterface"

MIC_TERMS = ("mute mic", "unmute mic", "microphone", "microfono",
             "disattiva audio", "attiva audio")
CAM_TERMS = ("turn camera off", "turn camera on")
# NB: match uses substring casefold. Order matters: longer/more specific first.
# In New Teams the button label is simply "Raise" / "Lower".
HAND_TERMS = ("raise your hand", "lower your hand", "raise", "lower",
              "alza la mano", "abbassa la mano")
LEAVE_TERMS = ("leave", "end meeting", "hang up", "esci", "termina riunione",
               "abbandona", "riaggancia")

# Terms that appear only during an active meeting
_IN_MEETING_TERMS = MIC_TERMS + LEAVE_TERMS


def _ax_get(element: Any, attribute: str) -> Any:
    try:
        error, value = AXUIElementCopyAttributeValue(element, attribute, None)
        return value if error == 0 else None
    except Exception:
        return None


def _label_of(element: Any) -> str:
    parts = []
    for attr in (AX_TITLE, AX_DESC, AX_VALUE):
        value = _ax_get(element, attr)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " | ".join(dict.fromkeys(parts))


def _children_of(element: Any) -> list[Any]:
    value = _ax_get(element, AX_CHILDREN)
    return list(value) if value else []


def _walk(element: Any, depth: int = 0, limit: int = 35) -> Iterable[Any]:
    if depth > limit:
        return
    yield element
    for child in _children_of(element):
        yield from _walk(child, depth + 1, limit)


_pid_cache: tuple[int | None, float] = (None, 0.0)
_PID_TTL = 3.0  # seconds before re-running pgrep


def _find_teams_pid() -> int | None:
    global _pid_cache
    pid, ts = _pid_cache
    if time.monotonic() - ts < _PID_TTL and pid is not None:
        return pid
    for name in ("Microsoft Teams", "MSTeams"):
        result = subprocess.run(
            ["pgrep", "-x", name],
            capture_output=True, text=True, check=False,
        )
        for line in result.stdout.splitlines():
            try:
                found = int(line.strip())
                _pid_cache = (found, time.monotonic())
                return found
            except ValueError:
                pass
    _pid_cache = (None, time.monotonic())
    return None


def teams_running() -> bool:
    return _find_teams_pid() is not None


def _teams_app() -> Any | None:
    pid = _find_teams_pid()
    if not pid:
        return None
    app = AXUIElementCreateApplication(pid)
    if app is not None:
        AXUIElementSetAttributeValue(app, kAXEnhancedUserInterfaceAttribute, True)
    return app


def _find_button(app: Any, terms: tuple[str, ...]) -> tuple[Any, str] | None:
    candidates = []
    for element in _walk(app):
        if _ax_get(element, AX_ROLE) != AX_BUTTON:
            continue
        label = _label_of(element)
        if any(t in label.casefold() for t in terms):
            candidates.append((element, label))

    for term in terms:
        for element, label in candidates:
            if term in label.casefold():
                return element, label
    return candidates[0] if candidates else None


def _press_button(terms: tuple[str, ...]) -> tuple[bool, str]:
    app = _teams_app()
    if app is None:
        return False, "Teams not found"
    match = _find_button(app, terms)
    if not match:
        return False, "Button not found"
    element, label = match
    error = AXUIElementPerformAction(element, AX_PRESS)
    if error != 0:
        return False, f"AXPress failed ({error}) on: {label}"
    return True, label


def toggle_mute() -> tuple[bool, str]:
    return _press_button(MIC_TERMS)


def toggle_camera() -> tuple[bool, str]:
    return _press_button(CAM_TERMS)


def toggle_hand() -> tuple[bool, str]:
    return _press_button(HAND_TERMS)


def leave_meeting() -> tuple[bool, str]:
    return _press_button(LEAVE_TERMS)


def meeting_state() -> tuple[bool, bool | None, bool | None, bool | None]:
    """Returns (in_meeting, mic_muted, cam_off, hand_raised)."""
    app = _teams_app()
    if app is None:
        return False, None, None, None

    mic_btn = _find_button(app, MIC_TERMS)
    if mic_btn is None:
        # Viewer/live event mode: only Leave button is present
        leave_btn = _find_button(app, LEAVE_TERMS)
        if leave_btn is not None:
            return True, None, None, None
        return False, None, None, None

    _, mic_label = mic_btn
    mic_muted = "unmute" in mic_label.casefold()

    cam_btn = _find_button(app, CAM_TERMS)
    if cam_btn is not None:
        _, cam_label = cam_btn
        cam_off = "turn camera on" in cam_label.casefold()
    else:
        cam_off = None

    # Detect hand state from AXStaticText status label (New Teams: "Your hand is raised." / "Your hand is lowered")
    hand_raised = False
    for el in _walk(app):
        if _ax_get(el, AX_ROLE) == "AXStaticText":
            val = (_ax_get(el, AX_VALUE) or "").casefold()
            if "hand is raised" in val or "mano alzata" in val:
                hand_raised = True
                break
            if "hand is lowered" in val or "mano abbassata" in val:
                hand_raised = False
                break

    return True, mic_muted, cam_off, hand_raised


def is_in_meeting() -> bool:
    in_meeting, *_ = meeting_state()
    return in_meeting
