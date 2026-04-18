import can
import importlib.util
from pathlib import Path
import sys
from typing import Iterable

_SPEC = importlib.util.spec_from_file_location(
    "can_replay_main",
    Path(__file__).resolve().parents[1] / "main.py",
)
assert _SPEC is not None and _SPEC.loader is not None
main = importlib.util.module_from_spec(_SPEC)
sys.modules["can_replay_main"] = main
_SPEC.loader.exec_module(main)


class FakeBus:
    def __init__(self, fail_on_ids: Iterable[int] | None = None):
        self.fail_on_ids = set(fail_on_ids or [])
        self.sent: list[can.Message] = []

    def send(self, msg: can.Message) -> None:
        if msg.arbitration_id in self.fail_on_ids:
            raise can.CanError("simulated send failure")
        self.sent.append(msg)


class FakeTime:
    def __init__(self, start: float = 100.0):
        self.now = start
        self.sleeps = []

    def clock(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def make_msg(arbitration_id: int, *, is_rx: bool, timestamp: float) -> can.Message:
    return can.Message(
        arbitration_id=arbitration_id,
        data=[0xAA],
        is_extended_id=False,
        is_rx=is_rx,
        timestamp=timestamp,
    )


def test_replay_messages_sends_only_rx_and_drops_tx() -> None:
    messages = [
        make_msg(0x100, is_rx=True, timestamp=1.0),
        make_msg(0x200, is_rx=False, timestamp=1.2),
        make_msg(0x300, is_rx=True, timestamp=1.5),
    ]
    fake_time = FakeTime()
    bus = FakeBus()

    stats = main.replay_messages(
        messages,
        bus,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    )

    assert [msg.arbitration_id for msg in bus.sent] == [0x100, 0x300]
    assert stats.total_frames == 3
    assert stats.replayed_rx_frames == 2
    assert stats.dropped_tx_frames == 1
    assert stats.skipped_invalid_timestamp_frames == 0
    assert stats.send_errors == 0


def test_replay_messages_preserves_relative_timing() -> None:
    messages = [
        make_msg(0x101, is_rx=True, timestamp=10.0),
        make_msg(0x102, is_rx=True, timestamp=10.5),
        make_msg(0x103, is_rx=True, timestamp=11.0),
    ]
    fake_time = FakeTime()
    bus = FakeBus()

    main.replay_messages(
        messages,
        bus,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    )

    assert fake_time.sleeps == [0.5, 0.5]
    assert [msg.arbitration_id for msg in bus.sent] == [0x101, 0x102, 0x103]


def test_replay_messages_skips_invalid_timestamps_and_counts_send_errors() -> None:
    messages = [
        make_msg(0x111, is_rx=True, timestamp=float("nan")),
        make_msg(0x222, is_rx=True, timestamp=5.0),
        make_msg(0x333, is_rx=True, timestamp=5.2),
    ]
    fake_time = FakeTime()
    bus = FakeBus(fail_on_ids={0x333})

    stats = main.replay_messages(
        messages,
        bus,
        clock=fake_time.clock,
        sleep=fake_time.sleep,
    )

    assert [msg.arbitration_id for msg in bus.sent] == [0x222]
    assert stats.total_frames == 3
    assert stats.replayed_rx_frames == 1
    assert stats.skipped_invalid_timestamp_frames == 1
    assert stats.send_errors == 1
