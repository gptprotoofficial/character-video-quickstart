"""Minimal GPTProto video client: create task -> poll -> download.

Every fact below was verified against the live API on 2026-10-26:

    POST https://gptproto.com/api/v3/kwaivgi/{model}/reference-to-video
    GET  https://gptproto.com/api/v3/predictions/{id}/result
    Authorization: <api key>          # no "Bearer " prefix

Request body is JSON, and reference images travel as **URLs**, not uploads:

    {"prompt": "...", "images": ["https://..."], "duration": 3, "aspect_ratio": "9:16"}

Response:

    {"code": 200, "data": {"id": "...", "status": "processing|completed|failed",
                           "outputs": ["https://...mp4"], "error": null}}

Override any of it from .env when your account's reference differs:

    GPTPROTO_BASE_URL          default https://gptproto.com
    GPTPROTO_VIDEO_CREATE_PATH default /api/v3/kwaivgi/{model}/reference-to-video
    GPTPROTO_VIDEO_QUERY_PATH  default /api/v3/predictions/{task_id}/result
    GPTPROTO_MODEL             default kling-4.0

Run `python -m character_video selftest` first - it checks the key and the paths
without creating a task, so it costs nothing.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .retry import with_backoff

TERMINAL_OK = {"succeeded", "success", "completed", "complete", "done", "finished"}
TERMINAL_FAIL = {"failed", "failure", "error", "cancelled", "canceled", "rejected"}

DEFAULT_BASE_URL = "https://gptproto.com"
DEFAULT_CREATE_PATH = "/api/v3/kwaivgi/{model}/reference-to-video"
DEFAULT_QUERY_PATH = "/api/v3/predictions/{task_id}/result"


class VideoTaskFailed(RuntimeError):
    """The model returned a failed task. This request was still billed."""


class ApiError(RuntimeError):
    """The endpoint answered with a non-200 code in the body."""


@dataclass
class VideoClient:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = "kling-4.0"
    create_path: str = DEFAULT_CREATE_PATH
    query_path: str = DEFAULT_QUERY_PATH
    poll_interval: float = 5.0
    poll_timeout: float = 900.0
    request_timeout: float = 120.0
    verbose: bool = False

    @classmethod
    def from_env(cls, api_key: Optional[str] = None) -> "VideoClient":
        return cls(
            api_key=api_key or os.getenv("GPTPROTO_API_KEY", ""),
            base_url=os.getenv("GPTPROTO_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("GPTPROTO_MODEL", "kling-4.0"),
            create_path=os.getenv("GPTPROTO_VIDEO_CREATE_PATH", DEFAULT_CREATE_PATH),
            query_path=os.getenv("GPTPROTO_VIDEO_QUERY_PATH", DEFAULT_QUERY_PATH),
        )

    # ---------------------------------------------------------------- helpers
    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "Authorization": self.api_key}

    def create_url(self) -> str:
        return self._url(self.create_path.format(model=self.model))

    def query_url(self, task_id: str) -> str:
        return self._url(self.query_path.format(task_id=task_id))

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._url(path)
        if self.verbose:
            print(f"[post] {url}\n{json.dumps(payload, indent=2)[:1200]}")

        def call() -> Dict[str, Any]:
            res = requests.post(url, headers=self._headers(), json=payload, timeout=self.request_timeout)
            res.raise_for_status()
            return res.json()

        return with_backoff(call, on_retry=lambda n, e: print(f"  retry #{n}: {e}"))

    def _get(self, path: str) -> Dict[str, Any]:
        url = self._url(path)

        def call() -> Dict[str, Any]:
            res = requests.get(url, headers=self._headers(), timeout=self.request_timeout)
            res.raise_for_status()
            return res.json()

        return with_backoff(call)

    # ------------------------------------------------------------------- API
    def create(self, payload: Dict[str, Any]) -> str:
        """Submit a task and return its id. This is the call that costs money."""
        data = self._post(self.create_path.format(model=self.model), payload)
        body = _unwrap(data)
        code = data.get("code") if isinstance(data, dict) else None
        if code not in (None, 200, 0):
            raise ApiError(f"create rejected (code {code}): {_message(data)}")

        task_id = body.get("id") or body.get("task_id") or body.get("taskId")
        if not task_id:
            raise RuntimeError(f"no task id in response: {json.dumps(data)[:500]}")
        return str(task_id)

    def poll(self, task_id: str) -> str:
        """Poll until the task finishes and return the video URL."""
        deadline = time.time() + self.poll_timeout
        last_status = "unknown"

        while time.time() < deadline:
            data = self._get(self.query_path.format(task_id=task_id))
            body = _unwrap(data)
            last_status = str(body.get("status") or "unknown").lower()
            urls = _outputs(body)

            if last_status in TERMINAL_FAIL:
                detail = body.get("error") or _message(data) or "no detail"
                raise VideoTaskFailed(
                    f"task {task_id} ended as '{last_status}': {detail}. "
                    "Note: a failed task still consumed one request."
                )
            if last_status in TERMINAL_OK or (urls and last_status not in {"processing", "queued", "pending"}):
                if urls:
                    return urls[0]
                raise RuntimeError(f"task finished but no output url: {json.dumps(data)[:500]}")

            if self.verbose:
                print(f"[poll] {task_id} -> {last_status}")
            time.sleep(self.poll_interval)

        raise TimeoutError(f"task {task_id} not finished after {self.poll_timeout:.0f}s (last status: {last_status})")

    def probe(self, path: str) -> tuple:
        """One free GET, used by selftest to tell 404 from 'method not allowed'."""
        try:
            res = requests.get(self._url(path), headers=self._headers(), timeout=30)
            return res.status_code, res.text[:200]
        except requests.RequestException as exc:  # noqa: BLE001 - selftest reports
            return 0, f"{type(exc).__name__}: {exc}"

    def list_models(self) -> tuple:
        """Free key check: the OpenAI-compatible model list."""
        try:
            res = requests.get(self._url("/v1/models"), headers=self._headers(), timeout=30)
            return res.status_code, res.text[:200]
        except requests.RequestException as exc:  # noqa: BLE001 - selftest reports
            return 0, f"{type(exc).__name__}: {exc}"

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
def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def to_data_url(path: str | Path) -> str:
    """Local image as a data URL. Not documented by the API - prefer a real URL."""
    p = Path(path)
    suffix = p.suffix.lower().lstrip(".") or "png"
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def resolve_image(value: str) -> str:
    """Accept a public URL or a local path; return what goes into `images`."""
    return value if is_url(value) else to_data_url(value)


def build_payload(
    prompt: str,
    image: Optional[str] = None,
    duration: int = 5,
    aspect_ratio: str = "9:16",
) -> Dict[str, Any]:
    """Request body for a reference-to-video task.

    The model id lives in the URL, not the body. Images are a list of URLs.
    """
    body: Dict[str, Any] = {"prompt": prompt, "duration": duration}
    if image:
        body["images"] = [image]
    if aspect_ratio:
        body["aspect_ratio"] = aspect_ratio
    return body


def _unwrap(payload: Any) -> Dict[str, Any]:
    """Responses wrap the useful fields in `data`."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def _message(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("msg") or payload.get("error") or "")[:300]
    return str(payload)[:300]


def _outputs(body: Dict[str, Any]) -> List[str]:
    """Collect video urls from `outputs`, which may hold strings or objects."""
    out: List[str] = []
    for item in body.get("outputs") or []:
        if isinstance(item, str) and item.startswith("http"):
            out.append(item)
        elif isinstance(item, dict):
            for key in ("url", "video_url", "file_url", "download_url"):
                if isinstance(item.get(key), str):
                    out.append(item[key])
                    break
    if not out and isinstance(body.get("urls"), dict):
        get_url = body["urls"].get("get")
        if isinstance(get_url, str) and get_url.endswith(".mp4"):
            out.append(get_url)
    return out
