"""Direct HTTP client for the Rive MCP server.

The Rive desktop app serves MCP over plain HTTP JSON-RPC at
`http://127.0.0.1:9791/mcp`. Normally the harness registers those tools, but the
registration is per-session: if the desktop app restarts mid-session the tools
vanish from the session even though the server is running and reachable.

This client talks to the same endpoint directly, so authoring work can continue
without waiting for a session restart. It is also what makes the pipeline
scriptable from Python at all — `genassets` can drive Rive end to end rather
than depending on an agent harness to relay every call.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

__all__ = ["RiveMCP", "RiveMCPError"]

DEFAULT_URL = "http://127.0.0.1:9791/mcp"


class RiveMCPError(RuntimeError):
    pass


class RiveMCP:
    """Minimal MCP client: initialize once, then call tools."""

    def __init__(self, url: str = DEFAULT_URL, *, timeout: int = 60):
        self.url = url
        self.timeout = timeout
        self._id = 0
        self._session: str | None = None
        self._initialized = False

    # ---------------------------------------------------------------- transport

    def _post(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        body = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            body["params"] = params

        headers = {
            "Content-Type": "application/json",
            # The server may reply as JSON or as a one-event SSE stream.
            "Accept": "application/json, text/event-stream",
        }
        if self._session:
            headers["Mcp-Session-Id"] = self._session

        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self._session = sid
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raise RiveMCPError(
                f"{method} -> HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}"
            ) from e
        except urllib.error.URLError as e:
            raise RiveMCPError(
                f"{method} -> cannot reach {self.url}: {e.reason}. "
                "Is the Rive desktop app running with a file open?"
            ) from e

        # An SSE reply arrives as `data: {...}` lines.
        payload = raw
        if raw.lstrip().startswith("event:") or raw.lstrip().startswith("data:"):
            for line in raw.splitlines():
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    break

        try:
            msg = json.loads(payload)
        except json.JSONDecodeError as e:
            raise RiveMCPError(f"{method} -> unparsable reply: {raw[:200]}") from e

        if "error" in msg:
            raise RiveMCPError(f"{method} -> {json.dumps(msg['error'])[:300]}")
        return msg.get("result", {})

    def _notify(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification.

        A notification has NO `id` — that is what distinguishes it from a
        request. Sending one with an id makes the server treat it as a request,
        so the handshake never completes and every subsequent `tools/call` is
        rejected with "Received tools/call before notifications/initialized".
        The server replies 202 with an empty body, so nothing is parsed.
        """
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=headers)
        try:
            urllib.request.urlopen(req, timeout=self.timeout).read()
        except urllib.error.HTTPError as e:
            raise RiveMCPError(
                f"{method} -> HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            ) from e

    def connect(self) -> dict:
        if self._initialized:
            return {}
        info = self._post("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "genassets", "version": "0.1.0"},
        })
        self._notify("notifications/initialized")
        self._initialized = True
        return info

    # -------------------------------------------------------------------- tools

    def list_tools(self) -> list[str]:
        self.connect()
        return sorted(t["name"] for t in self._post("tools/list").get("tools", []))

    def call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a Rive tool and return its decoded payload.

        Rive wraps results as `{success, errors, content}` where `content` is
        itself a JSON string. This unwraps both layers and raises on failure, so
        callers get data rather than nested envelopes.
        """
        self.connect()
        result = self._post("tools/call", {"name": tool, "arguments": arguments or {}})

        text = ""
        for part in result.get("content", []):
            if part.get("type") == "text":
                text += part.get("text", "")

        if not text:
            return result

        try:
            outer = json.loads(text)
        except json.JSONDecodeError:
            # Some tools return a bare error string rather than JSON.
            if text.lower().startswith("error"):
                raise RiveMCPError(f"{tool} -> {text[:300]}")
            return text

        if isinstance(outer, dict) and outer.get("errors"):
            raise RiveMCPError(f"{tool} -> {json.dumps(outer['errors'])[:300]}")

        inner = outer.get("content") if isinstance(outer, dict) else None
        if isinstance(inner, str):
            try:
                decoded = json.loads(inner)
            except json.JSONDecodeError:
                if inner.lower().startswith("error"):
                    raise RiveMCPError(f"{tool} -> {inner[:300]}")
                return inner
            if isinstance(decoded, dict) and decoded.get("success") is False:
                raise RiveMCPError(f"{tool} -> {json.dumps(decoded)[:300]}")
            return decoded
        return outer
