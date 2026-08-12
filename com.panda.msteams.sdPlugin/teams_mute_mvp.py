#!/usr/bin/env python3
"""Minimal macOS Teams mute controller via Accessibility API.

Usage:
  python teams_mute_mvp.py inspect
  python teams_mute_mvp.py mute
  python teams_mute_mvp.py mute --dry-run

Grant Accessibility permission to the terminal/Python process:
System Settings > Privacy & Security > Accessibility.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any, Iterable

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
)

AX_ROLE = "AXRole"
AX_TITLE = "AXTitle"
AX_DESC = "AXDescription"
AX_VALUE = "AXValue"
AX_CHILDREN = "AXChildren"
AX_WINDOWS = "AXWindows"
AX_ACTIONS = "AXActions"
AX_CHECKED = "AXChecked"
AX_BUTTON = "AXButton"
AX_PRESS = "AXPress"

MUTE_TERMS = (
    "mute",
    "unmute",
    "microphone",
    "microfono",
    "microphone off",
    "microphone on",
    "disattiva audio",
    "attiva audio",
)


def ax_get(element: Any, attribute: str) -> Any:
    try:
        error, value = AXUIElementCopyAttributeValue(element, attribute, None)
        return value if error == 0 else None
    except Exception:
        return None


def text_of(element: Any) -> str:
    parts = []
    for attribute in (AX_TITLE, AX_DESC, AX_VALUE):
        value = ax_get(element, attribute)
        if isinstance(value, str):
            parts.append(value)
    return " | ".join(dict.fromkeys(parts))


def children_of(element: Any) -> list[Any]:
    children = ax_get(element, AX_CHILDREN)
    return list(children) if children else []


def iter_tree(element: Any, depth: int = 0, max_depth: int = 30) -> Iterable[tuple[Any, int]]:
    if depth > max_depth:
        return
    yield element, depth
    for child in children_of(element):
        yield from iter_tree(child, depth + 1, max_depth)


def teams_pid() -> int:
    candidates = (
        "Microsoft Teams",
        "MSTeams",
    )
    for name in candidates:
        result = subprocess.run(
            ["pgrep", "-x", name],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            try:
                return int(line.strip())
            except ValueError:
                pass
    raise RuntimeError("Processo Microsoft Teams non trovato.")


def app_element(pid: int) -> Any:
    element = AXUIElementCreateApplication(pid)
    if element is None:
        raise RuntimeError("Impossibile creare l'elemento Accessibility di Teams.")
    return element


def meeting_controls(app: Any) -> list[tuple[Any, str, int]]:
    matches = []
    for element, depth in iter_tree(app):
        role = ax_get(element, AX_ROLE)
        label = text_of(element)
        normalized = label.casefold()
        if role == AX_BUTTON and any(term in normalized for term in MUTE_TERMS):
            matches.append((element, label, depth))
    return matches


def inspect(app: Any) -> None:
    for element, depth in iter_tree(app):
        role = ax_get(element, AX_ROLE)
        label = text_of(element)
        if role or label:
            print(f"{'  ' * depth}{role or '-'}: {label or '-'}")


def press_mute(app: Any, dry_run: bool) -> int:
    matches = meeting_controls(app)
    if not matches:
        print(
            "Nessun pulsante mute trovato nella gerarchia Accessibility di Teams.\n"
            "Avvia una riunione e verifica con: python teams_mute_mvp.py inspect",
            file=sys.stderr,
        )
        return 2

    if len(matches) > 1:
        print("Più controlli candidati trovati:")
        for _, label, depth in matches:
            print(f"  profondità={depth}: {label}")

    element, label, _ = matches[0]
    if dry_run:
        print(f"[dry-run] premerei: {label}")
        return 0

    error = AXUIElementPerformAction(element, AX_PRESS)
    if error != 0:
        print(f"AXPress fallito per '{label}', codice={error}", file=sys.stderr)
        return int(error)

    print(f"Comando mute inviato a Teams: {label}")
    return 0


def inspect_button(app: Any) -> None:
    """Dump every AX attribute of the mute button — use to find the right state attribute."""
    matches = meeting_controls(app)
    if not matches:
        print("No mute button found. Start a Teams meeting first.", file=sys.stderr)
        return
    element, label, depth = matches[0]
    print(f"Found button: '{label}'  (depth={depth})\n")
    # Dump all known attributes
    all_attrs = [
        "AXRole", "AXRoleDescription", "AXTitle", "AXDescription", "AXValue",
        "AXChecked", "AXEnabled", "AXFocused", "AXHelp", "AXIdentifier",
        "AXLabel", "AXSelected", "AXPressed",
    ]
    for attr in all_attrs:
        val = ax_get(element, attr)
        if val is not None:
            print(f"  {attr:25s} = {val!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Controllo mute di Microsoft Teams su macOS")
    parser.add_argument("command", choices=("inspect", "inspect-button", "mute"))
    parser.add_argument("--pid", type=int, help="PID Teams, opzionale")
    parser.add_argument("--dry-run", action="store_true", help="Non premere il pulsante")
    args = parser.parse_args()

    try:
        pid = args.pid or teams_pid()
        print(f"Teams PID: {pid}", file=sys.stderr)
        app = app_element(pid)
        if args.command == "inspect":
            inspect(app)
            return 0
        if args.command == "inspect-button":
            inspect_button(app)
            return 0
        return press_mute(app, args.dry_run)
    except RuntimeError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except ImportError:
        print(
            "Dipendenze mancanti. Installa: "
            "python -m pip install pyobjc-framework-ApplicationServices",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
