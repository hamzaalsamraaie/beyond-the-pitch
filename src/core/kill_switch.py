"""
Kill switch: create config/kill_switch.flag to halt all automation immediately.
Every long-running action checks this before proceeding.
"""

from pathlib import Path

_FLAG = Path(__file__).resolve().parents[2] / "config" / "kill_switch.flag"


def is_active() -> bool:
    return _FLAG.exists()


def arm() -> None:
    _FLAG.touch()


def disarm() -> None:
    _FLAG.unlink(missing_ok=True)


def require_clear(action: str = "action") -> None:
    """Raise RuntimeError if the kill switch is armed."""
    if is_active():
        raise RuntimeError(
            f"Kill switch is ARMED — refusing to run '{action}'. "
            f"Remove {_FLAG} to continue."
        )
