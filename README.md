# can-replay

Basically the same as python-can's [can.player][] tool, only with a hard-coded
RX-only filter on top of it.

## Usage

After `uv sync`:

```bash
uv run can-replay path/to/capture.log
uv run can-replay --help
python -m can_replay path/to/capture.log
```

[can.player]: https://python-can.readthedocs.io/en/stable/scripts.html#can-player
