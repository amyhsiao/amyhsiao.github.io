#!/usr/bin/env python3
"""Dependency-free Chrome DevTools smoke test for the locally served MVP.

Start Chrome with remote debugging before running this script. This helper is
intended for development verification and does not modify project data.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path


class DevToolsConnection:
    def __init__(self, websocket_url: str) -> None:
        parsed = urllib.parse.urlparse(websocket_url)
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.socket.sendall(request.encode("ascii"))
        response = self._read_http_headers()
        if " 101 " not in response.splitlines()[0]:
            raise RuntimeError(f"WebSocket upgrade failed: {response.splitlines()[0]}")
        self.next_id = 0

    def _read_http_headers(self) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            data += self.socket.recv(4096)
        return data.decode("latin-1")

    def _receive_exactly(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Chrome closed the DevTools connection")
            data += chunk
        return data

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        mask = os.urandom(4)
        length = len(data)
        header = bytearray([0x81])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        self.socket.sendall(bytes(header) + mask + masked)

    def _receive_json(self) -> dict:
        first, second = self._receive_exactly(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._receive_exactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._receive_exactly(8))[0]
        if second & 0x80:
            mask = self._receive_exactly(4)
        else:
            mask = None
        data = self._receive_exactly(length)
        if mask:
            data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
        if opcode == 0x9:  # ping
            return self._receive_json()
        if opcode == 0x8:
            raise ConnectionError("Chrome closed the WebSocket")
        return json.loads(data.decode("utf-8"))

    def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        request_id = self.next_id
        self._send_json({"id": request_id, "method": method, "params": params or {}})
        while True:
            response = self._receive_json()
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(f"{method}: {response['error']}")
                return response.get("result", {})

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", {
            "expression": expression, "awaitPromise": True, "returnByValue": True,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError(json.dumps(result["exceptionDetails"], ensure_ascii=False))
        return result["result"].get("value")


def open_target(debug_port: int, app_url: str) -> str:
    encoded = urllib.parse.quote(app_url, safe="")
    request = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json/new?{encoded}", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["webSocketDebuggerUrl"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug-port", type=int, default=9222)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--download-dir", type=Path, default=Path("/private/tmp/fish-mvp-smoke-downloads"))
    args = parser.parse_args()
    args.download_dir.mkdir(parents=True, exist_ok=True)
    before_downloads = set(args.download_dir.iterdir())
    connection = DevToolsConnection(open_target(args.debug_port, args.url))
    connection.call("Page.enable")
    connection.call("Runtime.enable")
    connection.call("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(args.download_dir)})

    result = connection.evaluate("""
      (async () => {
        const waitFor = async (predicate, timeout = 12000) => {
          const start = Date.now();
          while (!predicate()) {
            if (Date.now() - start > timeout) throw new Error('Timed out waiting for UI state');
            await new Promise(resolve => setTimeout(resolve, 80));
          }
        };
        await waitFor(() => !document.querySelector('#landing-screen').hidden);
        const landingLoaded = true;
        const input = document.querySelector('#display-name');
        input.value = 'Smoke Tester';
        document.querySelector('#name-form').requestSubmit();
        await waitFor(() => !document.querySelector('#dashboard-screen').hidden);
        const dashboardIsDefault = true;
        document.querySelector('[data-action="continue-labeling"]').click();
        await waitFor(() => !document.querySelector('#game-screen').hidden && document.querySelectorAll('.candidate-card').length > 0);
        const cards = [...document.querySelectorAll('.candidate-card')];
        const initialBatch = JSON.parse(localStorage.getItem('fish_labeler_mvp_v1_current_question'));
        document.querySelector('#submit-question').click();
        await waitFor(() => document.querySelector('#confirm-dialog').open);
        const allNoConfirmationWorks = document.querySelector('#confirm-message').textContent.includes('你沒有選取任何圖片');
        document.querySelector('#confirm-dialog [value="cancel"]').click();
        await waitFor(() => !document.querySelector('#confirm-dialog').open);
        cards[0].querySelector('.candidate-select').click();
        cards[1].querySelectorAll('.candidate-actions button')[0].click();
        cards[2].querySelectorAll('.candidate-actions button')[1].click();
        const selectedBatch = JSON.parse(localStorage.getItem('fish_labeler_mvp_v1_current_question'));
        return {
          landingLoaded, dashboardIsDefault,
          targetName: document.querySelector('#fish-name').textContent,
          referenceLoaded: document.querySelector('#reference-image').complete && document.querySelector('#reference-image').naturalWidth > 0,
          candidateCount: cards.length,
          allNoConfirmationWorks,
          yesWorks: cards[0].dataset.state === 'yes',
          unsureWorks: cards[1].dataset.state === 'unsure',
          brokenWorks: cards[2].dataset.state === 'broken',
          candidateIds: initialBatch.candidates.map(item => item.candidate_id),
          selections: selectedBatch.selections,
          batchId: initialBatch.question_batch_id,
        };
      })()
    """)
    print("Initial interaction:", json.dumps(result, ensure_ascii=False))

    connection.call("Page.reload", {"ignoreCache": False})
    restored = connection.evaluate(f"""
      (async () => {{
        const waitFor = async (predicate, timeout = 12000) => {{
          const start = Date.now();
          while (!predicate()) {{
            if (Date.now() - start > timeout) throw new Error('Timed out after reload');
            await new Promise(resolve => setTimeout(resolve, 80));
          }}
        }};
        await waitFor(() => !document.querySelector('#dashboard-screen').hidden);
        document.querySelector('[data-action="continue-labeling"]').click();
        await waitFor(() => !document.querySelector('#game-screen').hidden && document.querySelectorAll('.candidate-card').length > 0);
        const saved = JSON.parse(localStorage.getItem('fish_labeler_mvp_v1_current_question'));
        const sameOrder = JSON.stringify(saved.candidates.map(item => item.candidate_id)) === JSON.stringify({json.dumps(result['candidateIds'])});
        const sameBatch = saved.question_batch_id === {json.dumps(result['batchId'])};
        document.querySelector('#submit-question').click();
        await waitFor(() => {{
          const annotations = JSON.parse(localStorage.getItem('fish_labeler_mvp_v1_annotations') || '[]');
          const current = JSON.parse(localStorage.getItem('fish_labeler_mvp_v1_current_question') || 'null');
          return annotations.length >= saved.candidates.length && current?.question_batch_id !== saved.question_batch_id;
        }});
        const annotations = JSON.parse(localStorage.getItem('fish_labeler_mvp_v1_annotations'));
        const nextQuestionAppeared = !document.querySelector('#game-screen').hidden && document.querySelectorAll('.candidate-card').length > 0;
        document.querySelector('[data-action="dashboard"]').click();
        await waitFor(() => !document.querySelector('#dashboard-screen').hidden);
        const dashboardWorks = document.querySelector('#dashboard-completed').textContent === String(annotations.length)
          && document.querySelectorAll('.fish-progress-item').length > 0
          && document.querySelectorAll('.badge-card:not(.locked)').length > 0
          && document.querySelector('#today-questions').textContent === '1'
          && document.querySelector('#streak-days').textContent === '1'
          && document.querySelectorAll('.collection-card:not(.locked)').length === 1
          && document.querySelector('#milestone-name').textContent === '觀察之眼';
        document.querySelector('[data-action="continue-labeling"]').click();
        await waitFor(() => !document.querySelector('#game-screen').hidden);
        document.querySelector('[data-action="export-csv"]').click();
        document.querySelector('[data-action="export-json"]').click();
        return {{
          sameOrder, sameBatch,
          restoredSelections: saved.selections,
          annotationsSaved: annotations.length,
          judgments: [...new Set(annotations.map(item => item.judgment))].sort(),
          nextQuestionAppeared, dashboardWorks,
        }};
      }})()
    """)
    print("Reload and submission:", json.dumps(restored, ensure_ascii=False))
    time.sleep(2)
    downloads = [path for path in set(args.download_dir.iterdir()) - before_downloads if not path.name.endswith(".crdownload")]
    print("Exports:", ", ".join(sorted(path.name for path in downloads)) or "none")

    checks = [
        result["landingLoaded"], result["dashboardIsDefault"], result["targetName"], result["referenceLoaded"], 1 <= result["candidateCount"] <= 10,
        result["allNoConfirmationWorks"], result["yesWorks"], result["unsureWorks"], result["brokenWorks"],
        restored["sameOrder"], restored["sameBatch"],
        restored["annotationsSaved"] == result["candidateCount"], restored["nextQuestionAppeared"], restored["dashboardWorks"],
        any(path.suffix == ".csv" for path in downloads), any(path.suffix == ".json" for path in downloads),
    ]
    if not all(checks):
        raise SystemExit("Smoke test failed one or more checks")
    print("MVP browser smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
