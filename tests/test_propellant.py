"""Unit tests for PropellantLedger — real logic only, no mocks."""
from nex.propellant import PropellantLedger


def test_default_max_is_3():
    led = PropellantLedger()
    assert led.max_burns == 3
    assert led.used == 0
    assert led.remaining == 3
    assert led.denied == 0


def test_can_burn_and_burn_decrements():
    led = PropellantLedger(max_burns=2)
    assert led.can_burn() is True
    assert led.burn() is True
    assert led.used == 1
    assert led.remaining == 1
    assert led.burn() is True
    assert led.used == 2
    assert led.can_burn() is False
    assert led.burn() is False
    assert led.denied == 1
    assert led.used == 2


def test_max_zero_denies_immediately():
    led = PropellantLedger(max_burns=0)
    assert led.can_burn() is False
    assert led.burn() is False
    assert led.denied == 1


def test_record_denied_without_burn():
    led = PropellantLedger(max_burns=1)
    led.record_denied()
    assert led.denied == 1
    assert led.used == 0


def test_snapshot_dict():
    led = PropellantLedger(max_burns=5)
    led.burn()
    snap = led.snapshot()
    assert snap["propellant_max"] == 5
    assert snap["propellant_used"] == 1
    assert snap["propellant_remaining"] == 4
    assert snap["propellant_denied"] == 0
