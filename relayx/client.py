from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Mapping


class RelayXError(RuntimeError):
    def __init__(self, status: int, body: Any):
        super().__init__(f"RelayX request failed with status {status}")
        self.status = status
        self.body = body


@dataclass(slots=True)
class RelayXClient:
    api_key: str
    base_url: str = "https://gateway.relayx.vexarr.com"
    timeout: float = 60.0
    headers: Mapping[str, str] = field(default_factory=dict)

    def chat_completions(self, request: Mapping[str, Any]) -> Any:
        return self._post_json("/v1/chat/completions", request)

    def completions(self, request: Mapping[str, Any]) -> Any:
        return self._post_json("/v1/completions", request)

    def embeddings(self, request: Mapping[str, Any]) -> Any:
        return self._post_json("/v1/embeddings", request)

    def responses(self, request: Mapping[str, Any]) -> Any:
        return self._post_json("/v1/responses", request)

    def models(self) -> Any:
        return self._request_json("GET", "/v1/models")

    def stream_chat_completions(
        self, request: Mapping[str, Any]
    ) -> Iterator[dict[str, Any]]:
        body = {**request, "stream": True}
        return self._post_stream("/v1/chat/completions", body)

    def stream_responses(
        self, request: Mapping[str, Any]
    ) -> Iterator[dict[str, Any]]:
        body = {**request, "stream": True}
        return self._post_stream("/v1/responses", body)

    def _post_json(self, path: str, body: Mapping[str, Any]) -> Any:
        return self._request_json("POST", path, body)

    def _request_json(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            method=method,
            data=data,
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
                "x-relayx-sdk": "python",
                **dict(self.headers),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise RelayXError(error.code, _decode_body(error.read())) from error

        return json.loads(response_body) if response_body else None

    def _post_stream(
        self, path: str, body: Mapping[str, Any]
    ) -> Iterator[dict[str, Any]]:
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            method="POST",
            data=data,
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
                "x-relayx-sdk": "python",
                **dict(self.headers),
            },
        )

        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            raise RelayXError(error.code, _decode_body(error.read())) from error

        try:
            yield from _iter_sse(response)
        finally:
            response.close()


def _iter_sse(response: Any) -> Iterator[dict[str, Any]]:
    buf = b""
    for chunk in _read_chunks(response):
        buf += chunk
        while b"\n\n" in buf:
            frame, buf = buf.split(b"\n\n", 1)
            for line in frame.split(b"\n"):
                decoded = line.decode("utf-8", errors="replace")
                if decoded.startswith("data: "):
                    payload = decoded[6:]
                    if payload.strip() == "[DONE]":
                        return
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        continue


def _read_chunks(response: Any, size: int = 4096) -> Iterator[bytes]:
    while True:
        chunk = response.read(size)
        if not chunk:
            break
        yield chunk


def _decode_body(body: bytes) -> Any:
    if not body:
        return None
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
