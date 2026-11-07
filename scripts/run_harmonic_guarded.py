"""Run one UTide fit with a process-tree RSS, host-memory, and time watchdog."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time


def _proc_table() -> dict[int, tuple[int, int]]:
    page_size = os.sysconf("SC_PAGE_SIZE")
    result: dict[int, tuple[int, int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().split(")", 1)[1].split()
            pid = int(entry.name)
            ppid = int(fields[1])
            rss_bytes = int(fields[21]) * page_size
            result[pid] = (ppid, rss_bytes)
        except (OSError, ValueError, IndexError):
            continue
    return result


def _tree_rss(root_pid: int) -> int:
    table = _proc_table()
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _) in table.items():
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return sum(table[pid][1] for pid in descendants if pid in table)


def _available_bytes() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return sys.maxsize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--max-rss-gib", type=float, default=3.0)
    parser.add_argument("--min-available-gib", type=float, default=2.44)
    parser.add_argument("--timeout-minutes", type=float, default=60.0)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    config = args.config.resolve()
    if not config.is_file():
        parser.error(f"config not found: {config}")
    repo = Path.cwd()
    log_path = args.log or (repo / "reports" / f"{config.stem}_guarded.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    for name in (
        "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
    ):
        env[name] = "1"
    env.setdefault("MPLCONFIGDIR", "/tmp/mpl-cache")
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-u", "-m", "tide", "harmonic", "--config", str(config)],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    output: queue.Queue[str | None] = queue.Queue()

    def forward_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            output.put(line)
        output.put(None)

    threading.Thread(target=forward_output, daemon=True).start()
    began = time.monotonic()
    last_report = began
    peak_rss = 0
    stream_finished = False
    rss_limit = int(args.max_rss_gib * 1024**3)
    available_floor = int(args.min_available_gib * 1024**3)
    deadline = args.timeout_minutes * 60
    reason = None

    with log_path.open("w", encoding="utf-8") as log:
        while process.poll() is None or not stream_finished:
            try:
                line = output.get(timeout=1)
                if line is None:
                    stream_finished = True
                else:
                    log.write(line)
                    log.flush()
                    print(line, end="", flush=True)
            except queue.Empty:
                pass

            rss = _tree_rss(process.pid)
            available = _available_bytes()
            peak_rss = max(peak_rss, rss)
            now = time.monotonic()
            if now - last_report >= 10:
                print(
                    f"WATCHDOG elapsed={now-began:.0f}s rss={rss/1024**3:.2f}GiB "
                    f"peak={peak_rss/1024**3:.2f}GiB available={available/1024**3:.2f}GiB",
                    flush=True,
                )
                last_report = now
            if rss > rss_limit:
                reason = f"process-tree RSS exceeded {args.max_rss_gib:g} GiB"
            elif available < available_floor:
                reason = f"host available RAM fell below {args.min_available_gib:g} GiB"
            elif now - began > deadline:
                reason = f"time limit exceeded ({args.timeout_minutes:g} minutes)"
            if reason:
                print(f"WATCHDOG_STOP {reason}; terminating fit", flush=True)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break

    return_code = process.wait()
    print(
        f"PROCESS_EXIT code={return_code} elapsed={time.monotonic()-began:.1f}s "
        f"peak_rss={peak_rss/1024**3:.2f}GiB log={log_path}",
        flush=True,
    )
    if reason:
        return 124
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
