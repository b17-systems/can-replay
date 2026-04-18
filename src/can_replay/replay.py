import copy
import math
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

import can


class CanBus(Protocol):
    def send(self, msg: can.Message) -> None:
        """Send one CAN frame."""


@dataclass(slots=True)
class ReplayStats:
    total_frames: int = 0
    replayed_rx_frames: int = 0
    dropped_tx_frames: int = 0
    skipped_invalid_timestamp_frames: int = 0
    send_errors: int = 0


def replay_messages(
    messages: Iterable[can.Message],
    bus: CanBus,
    *,
    target_channel: str | None = None,
    clock: Callable[[], float] = time.perf_counter,
    sleep: Callable[[float], None] = time.sleep,
) -> ReplayStats:
    stats = ReplayStats()
    log_zero_ts: float | None = None
    wall_zero_ts: float | None = None

    for msg in messages:
        stats.total_frames += 1

        if msg.is_rx is not True:
            stats.dropped_tx_frames += 1
            continue

        timestamp = msg.timestamp
        if timestamp is None or not math.isfinite(timestamp):
            stats.skipped_invalid_timestamp_frames += 1
            continue

        if log_zero_ts is None:
            log_zero_ts = timestamp
            wall_zero_ts = clock()
        else:
            assert wall_zero_ts is not None
            target = wall_zero_ts + (timestamp - log_zero_ts)
            delay = target - clock()
            if delay > 0:
                sleep(delay)

        try:
            outbound = copy.copy(msg)
            outbound.channel = target_channel
            bus.send(outbound)
            stats.replayed_rx_frames += 1
        except can.CanError:
            stats.send_errors += 1

    return stats
