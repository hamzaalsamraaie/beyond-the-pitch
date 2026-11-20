import pytest
from src.core.kill_switch import arm, disarm, is_active, require_clear


def test_disarmed_by_default():
    disarm()
    assert not is_active()


def test_arm_and_disarm():
    arm()
    assert is_active()
    disarm()
    assert not is_active()


def test_require_clear_raises_when_armed():
    arm()
    with pytest.raises(RuntimeError, match="Kill switch is ARMED"):
        require_clear("test_action")
    disarm()


def test_require_clear_passes_when_disarmed():
    disarm()
    require_clear("test_action")  # must not raise
