import sys
import time
from pathlib import Path

import can
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .replay import ReplayStats, replay_messages

app = typer.Typer(
    help="Replay RX frames from a CAN log file onto a CAN bus.",
    no_args_is_help=True,
)

_THROTTLE_S = 0.1


def _live_description(stats: ReplayStats, elapsed_s: float) -> str:
    read_rps = stats.total_frames / elapsed_s if elapsed_s > 0 else 0.0
    rx_rps = stats.replayed_rx_frames / elapsed_s if elapsed_s > 0 else 0.0
    return (
        f"read {stats.total_frames} ({read_rps:.1f}/s) | "
        f"rx {stats.replayed_rx_frames} ({rx_rps:.1f}/s) | "
        f"drop_tx={stats.dropped_tx_frames} "
        f"bad_ts={stats.skipped_invalid_timestamp_frames} "
        f"err={stats.send_errors}"
    )


def _print_summary(stats: ReplayStats, console: Console) -> None:
    console.print(
        "Replay complete: "
        f"total={stats.total_frames}, "
        f"replayed_rx={stats.replayed_rx_frames}, "
        f"dropped_tx={stats.dropped_tx_frames}, "
        f"invalid_ts={stats.skipped_invalid_timestamp_frames}, "
        f"send_errors={stats.send_errors}"
    )


@app.command()
def main(
    logfile: Path = typer.Argument(
        ...,
        help="Path to the CAN log file (can.LogReader).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    interface: str = typer.Option(
        "socketcan",
        "--interface",
        "-i",
        help="python-can bus interface name, e.g. socketcan.",
    ),
    channel: str = typer.Option(
        "vcan0",
        "--channel",
        "-c",
        help="CAN channel/device, e.g. can0 or vcan0.",
    ),
    bitrate: int | None = typer.Option(
        None,
        "--bitrate",
        help="Optional CAN bitrate in bits/s.",
    ),
    fd: bool = typer.Option(
        True,
        "--fd/--no-fd",
        help="Use CAN FD on the bus (disable with --no-fd for classic CAN).",
    ),
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Disable Rich live progress (text summary only).",
    ),
) -> None:
    """Replay RX-only frames with log-relative timing."""
    err_console = Console(stderr=True, highlight=False)
    out_console = Console(highlight=False)
    fd_mode = fd
    use_progress = sys.stderr.isatty() and not plain

    try:
        with can.LogReader(logfile) as reader:
            if bitrate is None:
                bus = can.Bus(
                    interface=interface,
                    channel=channel,
                    fd=fd_mode,
                )
            else:
                bus = can.Bus(
                    interface=interface,
                    channel=channel,
                    bitrate=bitrate,
                    fd=fd_mode,
                )
            with bus:
                if use_progress:
                    t0 = time.perf_counter()
                    last_ui = t0

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        TimeElapsedColumn(),
                        console=err_console,
                        transient=False,
                    ) as progress:
                        task_id = progress.add_task("Starting…", total=None)

                        def on_tick(s: ReplayStats) -> None:
                            nonlocal last_ui
                            now = time.perf_counter()
                            if now - last_ui < _THROTTLE_S:
                                return
                            last_ui = now
                            progress.update(
                                task_id,
                                description=_live_description(s, now - t0),
                            )

                        stats = replay_messages(
                            reader,
                            bus,
                            target_channel=channel,
                            on_tick=on_tick,
                        )
                        progress.update(
                            task_id,
                            total=1,
                            completed=1,
                            description=_live_description(
                                stats, time.perf_counter() - t0
                            ),
                        )
                else:
                    stats = replay_messages(reader, bus, target_channel=channel)
    except (FileNotFoundError, OSError, ValueError, can.CanError) as exc:
        err_console.print(f"[red]Replay failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(stats, out_console)

    if stats.replayed_rx_frames == 0:
        err_console.print("[red]No replayable RX frames were sent.[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
