# can-replay

Basically the same as python-can's [can.player][] tool, only with a hard-coded
RX-only filter on top of it.

Requires **Python 3.14+**.

## Usage

After `uv sync`:

```bash
uv run can-replay path/to/capture.log
uv run can-replay --help
python -m can_replay path/to/capture.log
```

In a TTY, the CLI shows a Rich spinner and live rates (reads/s, RX replayed/s) plus counters; use `--plain` to disable that. Output goes to stderr (redirect stderr to drop the live display).

Bus mode defaults to **CAN FD**; use **`--no-fd`** for classic CAN only.

[can.player]: https://python-can.readthedocs.io/en/stable/scripts.html#can-player
