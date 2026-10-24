# Contributing

Thanks for helping! whycached is small on purpose: standard library only, no telemetry.

```sh
git clone https://github.com/mrzroot/whycached && cd whycached
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
python -m whycached --demo
```

Ground rules

- **No new runtime dependencies**, and Python 3.9 must keep working.
- **No false claims.** "STALE" is only for confirmed evidence (the cached body differs from the origin's). Everything else is "LIKELY" or "NOTE". A new finding needs a test where it fires and a test where it must stay silent.
- **Knowledge lives in tables** (`layers.py` for CDN header signatures, `FIXES` in `analyze.py` for purge commands). Link the vendor documentation in the PR.
- Tests use a local server (`tests/conftest.py`): no test may touch the internet.
- Add your change to `CHANGELOG.md`.
- Found a tool that already does this? Open an issue; it will be linked in the README and NOVELTY.md.
