"""OS-specific process helpers for managing the local CARLA server.

On POSIX these wrap the original behaviour (process groups via setsid/killpg,
``lsof`` / ``pgrep`` lookups, ``/proc`` zombie filtering) unchanged. On Windows
they use ``psutil`` (``pip install psutil``; see requirements.txt), and a
"group id" is simply the PID of the root process whose tree we manage.

Helpers raise on lookup failure (missing ``lsof``, no psutil, ...) so callers can
keep their existing "best effort + warn" handling.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

IS_WINDOWS = sys.platform == "win32"

CARLA_PROCESS_MARKER = "CarlaUE4"


def _psutil():
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("psutil is required on Windows: pip install psutil") from exc
    return psutil


# --------------------------------------------------------------------------- paths

def carla_executable_name() -> str:
    return "CarlaUE4.exe" if IS_WINDOWS else "CarlaUE4.sh"


def default_server_log_path() -> str:
    return os.path.join(tempfile.gettempdir(), "carla_server.log")


# ------------------------------------------------------------------------- launching

def new_process_group_popen_kwargs() -> Dict:
    """Popen kwargs that put the child in its own process group / session."""
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"preexec_fn": os.setsid}


# ------------------------------------------------------------------------- lookups

def find_listening_pid(port: int) -> Optional[int]:
    """PID of the process listening on a local TCP port, or None."""
    if IS_WINDOWS:
        psutil = _psutil()
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port and conn.pid:
                return conn.pid
        return None
    result = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
    if result.returncode == 0:
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if lines:
            return int(lines[0])
    return None


def find_pids_by_name(marker: str = CARLA_PROCESS_MARKER) -> List[int]:
    """PIDs of processes whose name or command line contains ``marker``."""
    if IS_WINDOWS:
        psutil = _psutil()
        pids = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            info = proc.info
            haystack = (info.get("name") or "") + " " + " ".join(info.get("cmdline") or [])
            if marker.lower() in haystack.lower():
                pids.append(info["pid"])
        return pids
    result = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [int(line) for line in result.stdout.split() if line.strip()]


def pid_alive(pid: int) -> bool:
    """True if a process with this PID exists (POSIX: also true for zombies / EPERM)."""
    pid = int(pid)
    if IS_WINDOWS:
        return _psutil().pid_exists(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True  # e.g. EPERM: process exists but isn't ours


# ------------------------------------------------------------- group / tree control

def get_group_id(pid: int) -> Optional[int]:
    """Identifier for the process group/tree containing ``pid``; None if unknown."""
    if IS_WINDOWS:
        return int(pid) if pid_alive(pid) else None
    try:
        return os.getpgid(pid)
    except OSError:
        return None


def _windows_tree(root_pid: int) -> list:
    psutil = _psutil()
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return []
    try:
        return [root] + root.children(recursive=True)
    except psutil.NoSuchProcess:
        return [root]


def terminate_group(pgid: int, force: bool = False) -> None:
    """Ask (SIGTERM) or force (SIGKILL) the whole group/tree to stop.

    Windows has no graceful signal for a console-less UE4 process, so both modes
    terminate the tree; ``force`` additionally kills anything still alive.
    """
    if IS_WINDOWS:
        psutil = _psutil()
        procs = _windows_tree(pgid)
        for proc in procs:
            try:
                proc.kill() if force else proc.terminate()
            except psutil.NoSuchProcess:
                pass
        return
    os.killpg(pgid, signal.SIGKILL if force else signal.SIGTERM)


def terminate_pid(pid: int, force: bool = False) -> None:
    """Stop a single known CARLA PID (and, on Windows, its children)."""
    if IS_WINDOWS:
        terminate_group(pid, force=force)
        return
    os.kill(int(pid), signal.SIGKILL if force else signal.SIGTERM)


def group_alive(pgid: int) -> bool:
    """True while the group/tree still has a live (non-zombie) member."""
    if IS_WINDOWS:
        psutil = _psutil()
        for proc in _windows_tree(pgid):
            try:
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    return True
            except psutil.NoSuchProcess:
                continue
        # Root may be gone while the UE4 shipping binary lives on.
        return any(True for _ in find_pids_by_name(CARLA_PROCESS_MARKER))
    return _posix_group_alive(pgid)


def _posix_group_alive(pgid) -> bool:
    """True while the group has a member that is not a zombie.

    A plain killpg(pgid, 0) probe is not enough: an orphaned CarlaUE4.sh
    wrapper (its launching VSE exited during a map-switch handoff) stays
    as an unreaped ZOMBIE after it dies, and zombies still count as group
    members -- the probe then reports a fully dead server as alive for as
    long as init takes to reap it (observed live 2026-07-07: ~20 s hang on
    exit + false 'survived SIGKILL' warning). Zombies hold no resources,
    so they are ignored here.
    """
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        # e.g. EPERM: the group exists but isn't ours -- treat as alive
        return True
    # Group exists -- check for at least one non-zombie member.
    # /proc/<pid>/stat: "pid (comm) state ppid pgrp ..." -- comm may
    # contain spaces/parens, so parse from the LAST ')'.
    pgid = int(pgid)
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue
        try:
            with open('/proc/%s/stat' % pid, 'rb') as f:
                data = f.read()
            fields = data[data.rindex(b')') + 2:].split()
            state, pgrp = fields[0], int(fields[2])
        except (OSError, ValueError, IndexError):
            continue  # process vanished mid-scan or malformed
        if pgrp == pgid and state != b'Z':
            return True
    return False
