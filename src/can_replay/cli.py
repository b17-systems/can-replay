import argparse
import sys
from pathlib import Path

import can

from .replay import replay_messages


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
