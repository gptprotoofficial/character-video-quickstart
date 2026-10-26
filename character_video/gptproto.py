"""Minimal GPTProto video client: create task -> poll -> download.

Endpoint paths follow the API reference for video models
(https://docs.gptproto.com -> <provider> -> gptproto-format -> image-to-video).
Override them with environment variables if your account's reference differs:

    GPTPROTO_BASE_URL          default https://gptproto.com/v1
    GPTPROTO_VIDEO_CREATE_PATH default /videos/generations
    GPTPROTO_VIDEO_QUERY_PATH  default /videos/generations/{task_id}
    GPTPROTO_MODEL             default kling-4.0

Run `python -m character_video selftest` first: it prints the raw request and
raw response so you can see immediately whether the paths match your account.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .retry import with_backoff

TERMINAL_OK = {"succeeded", "success", "completed", "complete", "done", "finished"}
TERMINAL_FAIL = {"failed", "failure", "error", "cancelled", "canceled", "rejected"}


class VideoTaskFailed(RuntimeError):
    """The model returned a failed task. This request was still billed."""


@dataclass
class VideoClient:
    api_key: str
    base_url: str = "https://gptproto.com/v1"
    model: str = "kling-4.0"
    create_path: str = "/videos/generations"
    query_path: str = "/videos/generations/{task_id}"
    poll_interval: float = 5.0
    poll_timeout: float = 900.0
    request_timeout: float = 120.0
    verbose: bool = False

    @classmethod
    def from_env(cls, api_key: Optional[str] = None) -> "VideoClient":
        return cls(
            api_key=api_key or os.getenv("GPTPROTO_API_KEY", ""),
            base_url=os.getenv("GPTPROTO_BASE_URL", "https://gptproto.com/v1"),
            model=os.getenv("GPTPROTO_MODEL", "kling-4.0"),
            create_path=os.getenv("GPTPROTO_VIDEO_CREATE_PATH", "/videos/generations"),
            query_path=os.getenv("GPTPROTO_VIDEO_QUERY_PATH", "/videos/generations/{task_id}"),
        )

    # ---------------------------------------------------------------- helpers
    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _headers(self, bearer: bool = False) -> Dict[str, str]:
        token = f"Bearer {self.api_key}" if bearer else self.api_key
        return {"Content-Type": "application/json", "Authorization": token}

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._url(path)
        if self.verbose:
            print(f"[post] {url}\n{json.dumps(payload, indent=2)[:1200]}")

        def call() -> Dict[str, Any]:
            res = requests.post(url, headers=self._headers(), json=payload, timeout=self.request_timeout)
            if res.status_code == 401:
                # Some deployments expect the "Bearer " prefix; try once.
                res = requests.post(url, headers=self._headers(bearer=True), json=payload, timeout=self.request_timeout)
            res.raise_for_status()
            return res.json()

        return with_backoff(call, on_retry=lambda n, e: print(f"  retry #{n}: {e}"))

    def _get(self, path: str) -> Dict[str, Any]:
        url = self._url(path)

        def call() -> Dict[str, Any]:
            res = requests.get(url, headers=self._headers(), timeout=self.request_timeout)
            if res.status_code == 401:
                res = requests.get(url, headers=self._headers(bearer=True), timeout=self.request_timeout)
            res.raise_for_status()
            return res.json()

        return with_backoff(call)

    # ------------------------------------------------------------------- API
    def create(self, payload: Dict[str, Any]) -> str:
        """Submit a task and return its id."""
        body = dict(payload)
        body.setdefault("model", self.model)
        data = self._post(self.create_path, body)
        task_id = _find_first(data, ("task_id", "id", "taskId", "request_id"))
        if not task_id:
            raise RuntimeError(f"no task id in response: {json.dumps(data)[:500]}")
        return str(task_id)

    def poll(self, task_id: str) -> str:
        """Poll until the task finishes and return the video URL."""
        deadline = time.time() + self.poll_timeout
        path = self.query_path.format(task_id=task_id)
        last_status = "unknown"

        while time.time() < deadline:
            data = self._get(path)
            last_status = str(_find_first(data, ("status", "state", "task_status")) or "unknown").lower()

            if last_status in TERMINAL_FAIL:
                raise VideoTaskFailed(
                    f"task {task_id} ended as '{last_status}'. "
                    "Note: a failed task still consumed one request."
                )
            if last_status in TERMINAL_OK:
                url = _find_first(data, ("video_url", "url", "output_url", "file_url", "download_url"))
                if url:
                    return str(url)
                raise RuntimeError(f"task ok but no video url in response: {json.dumps(data)[:500]}")

            if self.verbose:
                print(f"[poll] {task_id} -> {last_status}")
            time.sleep(self.poll_interval)

        raise TimeoutError(f"task {task_id} not finished after {self.poll_timeout:.0f}s (last status: {last_status})")

    def download(self, url: str, out_path: str | Path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        def call() -> None:
            with requests.get(url, stream=True, timeout=self.request_timeout) as res:
                res.raise_for_status()
                with out.open("wb") as fh:
                    for chunk in res.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)

        with_backoff(call)
        return out


# --------------------------------------------------------------- utilities
def image_payload(path: str | Path) -> str:
    """Reference image as a data URL (most video endpoints accept base64)."""
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".") or "png"
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_payload(
    model: str,
    prompt: str,
    image_data_url: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
) -> Dict[str, Any]:
    """Request body for a reference-to-video task."""
    return {
        "model": model,
        "prompt": prompt,
        "image": image_data_url,          # reference frame
        "duration": duration,             # seconds
        "aspect_ratio": aspect_ratio,
    }


def _find_first(node: Any, keys: tuple) -> Any:
    """Depth-first search for the first matching key in a nested JSON response."""
    if isinstance(node, dict):
        for key in keys:
            if key in node and node[key] not in (None, ""):
                return node[key]
        for value in node.values():
            found = _find_first(value, keys)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first(item, keys)
            if found is not None:
                return found
    return None
