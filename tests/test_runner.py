import sys
from pathlib import Path

from hwpbench.corpus import Case
from hwpbench.runner import Adapter, run_one

SCRIPT = """
import os, sys, time
mode = os.environ["MODE"]
src, out = sys.argv[1], sys.argv[2]
if mode == "ok":
    open(out, "w", encoding="utf-8").write("# 제목\\n\\n" + open(src, encoding="utf-8").read())
elif mode == "error":
    print("깨진 파일", file=sys.stderr); sys.exit(3)
elif mode == "slow":
    time.sleep(5)
elif mode == "empty":
    open(out, "w").write("  \\n")
elif mode == "env":
    open(out, "w").write(os.environ.get("SECRET_TOKEN", "없음") + " " + os.environ.get("KORDOC_OFFLINE", ""))
"""


def setup(tmp_path: Path, mode: str):
    script = tmp_path / "fake.py"
    script.write_text(SCRIPT, encoding="utf-8")
    src = tmp_path / "doc.hwpx"
    src.write_text("본문", encoding="utf-8")
    adapter = Adapter("fake", [sys.executable, str(script)], "markdown", ["hwpx"], env={"MODE": mode})
    return adapter, Case("d1", "hwpx", "structure", "hwpx", src, ()), tmp_path / "out" / "d1.out"


def test_ok(tmp_path):
    adapter, test, out = setup(tmp_path, "ok")
    run = run_one(adapter, test, out)
    assert run.status == "ok" and run.seconds is not None
    assert out.read_text(encoding="utf-8") == "# 제목\n\n본문"


def test_error_keeps_last_stderr_line(tmp_path):
    run = run_one(*setup(tmp_path, "error"))
    assert (run.status, run.error) == ("error", "깨진 파일")


def test_timeout(tmp_path):
    adapter, test, out = setup(tmp_path, "slow")
    assert run_one(adapter, test, out, timeout=0.5).status == "timeout"


def test_empty(tmp_path):
    assert run_one(*setup(tmp_path, "empty")).status == "empty"


def test_unsupported_format(tmp_path):
    adapter, test, out = setup(tmp_path, "ok")
    hwp = Case("d1", "hwp", "structure", "hwpx", test.path, ())
    assert run_one(adapter, hwp, out).status == "unsupported"


def test_does_not_leak_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "abc123")
    adapter, test, out = setup(tmp_path, "env")
    run_one(adapter, test, out)
    assert out.read_text() == "없음 1"
