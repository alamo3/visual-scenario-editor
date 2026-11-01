"""File-based "new editor is ready" handoff used on Windows.

On POSIX the relaunching editor passes the new process an inherited pipe
(VSE_HANDOFF_FD, see relaunch.py). Windows has neither ``pass_fds`` nor a
selectable pipe, so there the new process creates a marker file instead and the
old process polls for it from its main loop. The POSIX pipe path is untouched.
"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Dict, Optional

ENV_VAR = "VSE_HANDOFF_FILE"
_PREFIX = "vse_handoff_"
_SUFFIX = ".ready"


def prepare(env: Dict[str, str]) -> str:
    """Choose a unique marker path for a child about to be launched and put it in ``env``."""
    path = os.path.join(
        tempfile.gettempdir(), f"{_PREFIX}{os.getpid()}_{time.time_ns()}{_SUFFIX}"
    )
    env[ENV_VAR] = path
    return path


def signal_ready(path: Optional[str]) -> None:
    """Child side: create the marker atomically (never observed half-written)."""
    if not path:
        return
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as fh:
            fh.write("1")
        os.replace(tmp, path)
    except OSError:
        pass


def consume_if_ready(path: Optional[str]) -> bool:
    """Parent side: True (and delete the marker) once the child has signalled."""
    if not path or not os.path.exists(path):
        return False
    discard(path)
    return True


def discard(path: Optional[str]) -> None:
    for candidate in (path, (path + ".tmp") if path else None):
        if not candidate:
            continue
        try:
            os.remove(candidate)
        except OSError:
            pass


def cleanup_stale(max_age_s: float = 3600.0) -> None:
    """Remove markers left behind by parents that exited without consuming them."""
    try:
        directory = tempfile.gettempdir()
        now = time.time()
        for name in os.listdir(directory):
            if name.startswith(_PREFIX) and (name.endswith(_SUFFIX) or name.endswith(_SUFFIX + ".tmp")):
                full = os.path.join(directory, name)
                try:
                    if now - os.path.getmtime(full) > max_age_s:
                        os.remove(full)
                except OSError:
                    pass
    except OSError:
        pass
