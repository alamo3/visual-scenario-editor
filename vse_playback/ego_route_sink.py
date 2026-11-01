"""Agent-less delivery of the scenario's ego route to an external stack.

VSE does not load an agent for an externally controlled ego. If the scenario
defines ego waypoints, they can still be handed to the external stack (e.g. to
set a destination) through a sink chosen by ``--ego-route-sink`` or the
``VSE_EGO_ROUTE_SINK`` environment variable:

    none             do not deliver anything (external ego, no route handoff)
    file:<path>      atomically write the latest event as JSON to <path>
    http(s)://<url>  POST each event as JSON (best effort, 2 s timeout)

Events are JSON objects with an ``event`` field:

    {"event": "route", "scenario": "...", "map": "Town10HD",
     "waypoints": [{"x":..,"y":..,"z":..,"yaw":..}, ...],
     "destination": {"x":..,"y":..,"z":..,"yaw":..}, "timestamp": 1.7e9}
    {"event": "cancel", "scenario": "...", "timestamp": ...}

Coordinates are CARLA world coordinates (metres, yaw in degrees). Only the
stdlib is used, so this works unchanged on every OS.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request
from typing import Callable, Dict, List, Optional, Sequence, Tuple

ENV_VAR = "VSE_EGO_ROUTE_SINK"
_POST_TIMEOUT_S = 2.0


def sink_spec_from_env(cli_value: Optional[str] = None) -> Optional[str]:
    """Return the configured sink spec (CLI wins over env), or None if unset."""
    value = cli_value if cli_value else os.environ.get(ENV_VAR)
    value = (value or "").strip()
    return value or None


class EgoRouteSink:
    def __init__(self, spec: str, log: Callable[[str], None] = print):
        spec = spec.strip()
        self.spec = spec
        self._log = log
        low = spec.lower()
        if low == "none":
            self.kind, self.target = "none", None
        elif low.startswith("file:"):
            self.kind, self.target = "file", os.path.abspath(os.path.expanduser(spec[5:]))
        elif low.startswith(("http://", "https://")):
            self.kind, self.target = "http", spec
        else:
            raise ValueError(
                f"Invalid ego route sink '{spec}': expected 'none', 'file:<path>' or an http(s) URL"
            )

    @staticmethod
    def build_route_event(
        scenario: str,
        map_name: str,
        waypoints: Sequence[Tuple[float, float, float, float]],
    ) -> Dict:
        points: List[Dict[str, float]] = [
            {"x": float(x), "y": float(y), "z": float(z), "yaw": float(yaw)}
            for x, y, z, yaw in waypoints
        ]
        return {
            "event": "route",
            "scenario": scenario,
            "map": map_name,
            "waypoints": points,
            "destination": points[-1] if points else None,
            "timestamp": time.time(),
        }

    def send(self, event: Dict) -> None:
        """Deliver an event without blocking the caller or raising."""
        if self.kind == "none":
            return
        threading.Thread(target=self._deliver, args=(event,), daemon=True).start()

    def _deliver(self, event: Dict) -> None:
        try:
            payload = json.dumps(event).encode("utf-8")
            if self.kind == "file":
                directory = os.path.dirname(self.target) or "."
                os.makedirs(directory, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(payload)
                os.replace(tmp, self.target)  # atomic on POSIX and Windows
            else:
                req = urllib.request.Request(
                    self.target, data=payload, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=_POST_TIMEOUT_S):
                    pass
            self._log(f"[EgoRoute] sent '{event.get('event')}' to {self.spec}")
        except Exception as exc:
            self._log(f"[EgoRoute] failed to send '{event.get('event')}' to {self.spec}: {exc}")
