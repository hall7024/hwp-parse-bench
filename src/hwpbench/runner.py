"""어댑터를 별도 프로세스로 돌리고 원 출력과 실행 기록을 남긴다."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .corpus import ROOT, Case, tests

REGISTRY = ROOT / "adapters" / "registry.json"
RESULTS = ROOT / "results"
TIMEOUT = 60.0
WARMUP_TIMEOUT = 900.0

# 어댑터 프로세스에 넘기는 환경. 키·토큰 같은 다른 변수는 넘기지 않는다
_PASS_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR")
_OFFLINE_ENV = {"KORDOC_OFFLINE": "1", "DO_NOT_TRACK": "1", "HF_HUB_OFFLINE": "1", "PYTHONIOENCODING": "utf-8"}
# 측정 실행은 네트워크를 막는다. macOS는 sandbox-exec, 그 밖에서는 컨테이너(--network none)로 돌리라고 안내한다
_SANDBOX_PROFILE = "(version 1)(allow default)(deny network*)"


def network_isolation() -> str:
    return "sandbox-exec" if sys.platform == "darwin" and shutil.which("sandbox-exec") else "none"


def _isolated(command: list[str]) -> list[str]:
    if network_isolation() == "sandbox-exec":
        return ["sandbox-exec", "-p", _SANDBOX_PROFILE, *command]
    return command


@dataclass
class Adapter:
    name: str
    command: list[str]
    output: str  # markdown | text
    formats: list[str]
    package: str = ""
    version: str = ""
    license: str = ""
    notes: str = ""
    status: str = "ok"
    env: dict[str, str] | None = None
    setup: list[str] | None = None


@dataclass
class Run:
    adapter: str
    test: str
    status: str  # ok | error | timeout | empty | unsupported
    seconds: float | None
    error: str = ""


def adapters(registry: Path = REGISTRY) -> list[Adapter]:
    data = json.loads(registry.read_text(encoding="utf-8"))
    return [Adapter(**{k: v for k, v in a.items() if k in Adapter.__dataclass_fields__}) for a in data]


def _env(adapter: Adapter, offline: bool) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASS_ENV if k in os.environ}
    env.update(_OFFLINE_ENV)
    if offline:
        env["UV_OFFLINE"] = "1"
    env.update(adapter.env or {})
    return env


def run_one(adapter: Adapter, test: Case, out: Path, timeout: float = TIMEOUT, offline: bool = False) -> Run:
    """offline=True면 네트워크를 막고 uv도 캐시만 쓴다(측정 실행). 준비 실행은 패키지를 받아야 해서 False."""
    if test.format not in adapter.formats:
        return Run(adapter.name, test.key, "unsupported", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            _isolated([*adapter.command, str(test.path), str(out)]) if offline else [*adapter.command, str(test.path), str(out)],
            cwd=ROOT,
            env=_env(adapter, offline),
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return Run(adapter.name, test.key, "timeout", timeout)
    seconds = time.perf_counter() - start
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        return Run(adapter.name, test.key, "error", seconds, (err[-1] if err else f"exit {proc.returncode}")[:300])
    if not out.exists() or not out.read_text(encoding="utf-8", errors="replace").strip():
        return Run(adapter.name, test.key, "empty", seconds)
    return Run(adapter.name, test.key, "ok", seconds)


def warm_up(adapter: Adapter, sample: Case, log=print) -> None:
    """uv·npm 환경을 미리 만들어 첫 실행의 설치 시간이 측정에 섞이지 않게 한다."""
    if adapter.setup:
        subprocess.run(adapter.setup, cwd=ROOT, check=True, timeout=WARMUP_TIMEOUT)
    tmp = RESULTS / ".warmup" / f"{adapter.name}.out"
    run = run_one(adapter, sample, tmp, timeout=WARMUP_TIMEOUT)
    log(f"준비 {adapter.name}: {run.status} {run.error}")


def environment() -> dict:
    def version(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except OSError:
            return ""

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "uv": version(["uv", "--version"]),
        "node": version(["node", "--version"]),
        "network_isolation": network_isolation(),
    }


def run(names: set[str] | None = None, only: set[str] | None = None, jobs: int = 4, log=print) -> Path:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = RESULTS / run_id
    selected = [a for a in adapters() if (not names or a.name in names) and a.status != "broken"]
    cases = [t for t in tests() if not only or t.doc_id in only]
    base.mkdir(parents=True)
    meta = {
        "run_id": run_id,
        "environment": environment(),
        "adapters": [asdict(a) for a in selected],
        "tests": len(cases),
    }
    (base / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for a in selected:
        sample = next((t for t in cases if t.format in a.formats), None)
        if sample:
            warm_up(a, sample, log)
    jobs_list = [(a, t) for a in selected for t in cases]

    def work(item: tuple[Adapter, Case]) -> Run:
        a, t = item
        return run_one(a, t, base / "raw" / a.name / f"{t.key}.out", offline=True)

    with ThreadPoolExecutor(max_workers=jobs) as pool, (base / "runs.jsonl").open("w", encoding="utf-8") as f:
        for i, r in enumerate(pool.map(work, jobs_list), 1):
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
            if r.status != "ok" or i % 50 == 0:
                log(f"[{i}/{len(jobs_list)}] {r.adapter} {r.test} {r.status} {r.error}")
    return base
