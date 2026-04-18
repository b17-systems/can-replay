import argparse
import copy
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay RX frames from a CAN log file onto a CAN bus."
    )
    parser.add_argument(
        "logfile",
        type=Path,
        help="Path to the CAN log file. Loaded with can.LogReader.",
    )
    parser.add_argument(
        "--interface",
        default="socketcan",
        help="python-can bus interface name, e.g. socketcan.",
    )
    parser.add_argument(
        "--channel",
        default="vcan0",
        help="CAN channel/device, e.g. can0 or vcan0.",
    )
    parser.add_argument(
        "--bitrate",
        type=int,
        default=None,
        help="Optional CAN bitrate in bits/s.",
    )
    parser.add_argument(
        "--classic-can",
        action="store_true",
        help="Disable CAN FD mode and use classic CAN bus settings.",
    )
    return parser


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
            outbound.channel = None
            bus.send(outbound)
            stats.replayed_rx_frames += 1
        except can.CanError:
            stats.send_errors += 1

    return stats


def run(args: argparse.Namespace) -> int:
    try:
        with can.LogReader(args.logfile) as reader:
            fd_mode = not args.classic_can
            if args.bitrate is None:
                bus = can.Bus(
                    interface=args.interface,
                    channel=args.channel,
                    fd=fd_mode,
                )
            else:
                bus = can.Bus(
                    interface=args.interface,
                    channel=args.channel,
                    bitrate=args.bitrate,
                    fd=fd_mode,
                )
            with bus:
                stats = replay_messages(reader, bus, target_channel=args.channel)
    except (FileNotFoundError, OSError, ValueError, can.CanError) as exc:
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Replay complete: "
        f"total={stats.total_frames}, "
        f"replayed_rx={stats.replayed_rx_frames}, "
        f"dropped_tx={stats.dropped_tx_frames}, "
        f"invalid_ts={stats.skipped_invalid_timestamp_frames}, "
        f"send_errors={stats.send_errors}"
    )

    if stats.replayed_rx_frames == 0:
        print("No replayable RX frames were sent.", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
