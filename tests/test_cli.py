import json
import subprocess
import sys

from whycached.cli import main


def test_demo_runs(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "STALE" in out and "Cloudflare" in out and "OK (1)" in out


def test_json_and_exit_codes(box, capsys):
    box.routes["/"] = lambda h: (200, {"Content-Type": "text/html", "Cache-Control": "no-cache"}, "<h1>x</h1>")
    assert main([box.base + "/", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["worst"] == "OK" and "probes" in data
    box.routes["/c"] = lambda h: (200, {"Content-Type": "text/html", "Cache-Control": "max-age=3600"}, "<h1>x</h1>")
    assert main([box.base + "/c", "--no-assets"]) == 1


def test_error_exit(capsys):
    assert main(["http://127.0.0.1:1/", "--timeout", "1"]) == 2


def test_module_entry():
    p = subprocess.run([sys.executable, "-m", "whycached", "--version"], capture_output=True, text=True)
    assert p.returncode == 0 and "whycached" in p.stdout
