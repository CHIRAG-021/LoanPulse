"""Real Browser Multi-Tab Verification Script for LoanPulse.

Uses headless Google Chrome via Chrome DevTools Protocol (CDP) to verify:
1. Public homepage accessible without login.
2. Manager logs into Tab 1.
3. Tab 2 opens clean copied URL -> redirected to login (does NOT inherit Tab 1).
4. Tab 3 opens copied URL with ?wid= -> fails closed and redirected to login.
5. Tab 2 logs in as Customer -> Tab 1 (Manager) and Tab 2 (Customer) run concurrently.
6. Tab 4 opens and logs in as Officer -> all 3 roles operate concurrently in the same browser.
7. Customer attempts to access Manager queue -> 403 Forbidden.
8. Second login to Manager account in Tab 5 invalidates Tab 1.
"""
import os
import sys
import time
import json
import base64
import socket
import struct
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path


class CDPClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.msg_id = 1
        # Parse host and path
        # ws://127.0.0.1:9455/devtools/page/UUID
        stripped = ws_url.replace("ws://", "")
        host_port, self.path = stripped.split("/", 1)
        self.path = "/" + self.path
        host, port = host_port.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=10)
        self._handshake(host_port)

    def _handshake(self, host: str):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        resp = self.sock.recv(4096)
        assert b"101" in resp, f"WebSocket handshake failed: {resp[:200]}"

    def send_cmd(self, method: str, params: dict | None = None) -> dict:
        cid = self.msg_id
        self.msg_id += 1
        payload = {"id": cid, "method": method}
        if params:
            payload["params"] = params
        data = json.dumps(payload).encode("utf-8")
        mask = os.urandom(4)
        length = len(data)
        if length < 126:
            frame = bytearray([0x81, 0x80 | length]) + mask
        elif length < 65536:
            frame = bytearray([0x81, 0x80 | 126]) + struct.pack(">H", length) + mask
        else:
            frame = bytearray([0x81, 0x80 | 127]) + struct.pack(">Q", length) + mask
        frame += bytearray(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(frame)

        # Read frames until we receive response matching cid
        while True:
            b1, b2 = self.sock.recv(2)
            masked = (b2 & 0x80) != 0
            len_field = b2 & 0x7F
            if len_field == 126:
                length = struct.unpack(">H", self.sock.recv(2))[0]
            elif len_field == 127:
                length = struct.unpack(">Q", self.sock.recv(8))[0]
            else:
                length = len_field
            if masked:
                mask_key = self.sock.recv(4)
            buf = bytearray()
            while len(buf) < length:
                chunk = self.sock.recv(length - len(buf))
                buf.extend(chunk)
            if masked:
                buf = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(buf))
            msg = json.loads(buf.decode("utf-8", errors="replace"))
            if msg.get("id") == cid:
                return msg

    def eval(self, expr: str):
        res = self.send_cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        result = res.get("result", {}).get("result", {})
        return result.get("value")

    def navigate(self, url: str):
        self.send_cmd("Page.navigate", {"url": url})
        time.sleep(1.2)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def run_tests():
    server_port = 5055
    cdp_port = 9466
    base_url = f"http://127.0.0.1:{server_port}"

    print(f"[*] Starting LoanPulse live server on port {server_port}...")
    server_env = os.environ.copy()
    server_env["FLASK_ENV"] = "development"
    server_env["SECRET_KEY"] = "very-secure-secret-key-for-test-at-least-32-chars-long"
    server_env["TESTING"] = "False"
    server_env["SESSION_COOKIE_SECURE"] = "False"

    venv_python = str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python")

    server_proc = subprocess.Popen(
        [venv_python, "-m", "flask", "--app", "wsgi:app", "run", "--port", str(server_port)],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=server_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to be responsive
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    print("[+] LoanPulse server is up and healthy!")
                    break
        except Exception:
            time.sleep(0.5)
    else:
        server_proc.terminate()
        raise RuntimeError("Server failed to start")

    print(f"[*] Starting Headless Google Chrome on CDP port {cdp_port}...")
    chrome_proc = subprocess.Popen(
        [
            "/usr/bin/google-chrome",
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={cdp_port}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    try:
        # Helper to open a new tab in Chrome
        def open_tab(url="about:blank") -> CDPClient:
            req_url = f"http://127.0.0.1:{cdp_port}/json/new?{urllib.parse.quote(url)}"
            req = urllib.request.Request(req_url, method="PUT")
            with urllib.request.urlopen(req) as r:
                info = json.loads(r.read().decode())
                return CDPClient(info["webSocketDebuggerUrl"])

        # ---------------------------------------------------------------------
        # TEST 1: Public Homepage
        # ---------------------------------------------------------------------
        print("\n=== TEST 1: Public Homepage Access ===")
        tab1 = open_tab(f"{base_url}/")
        time.sleep(1.0)
        title = tab1.eval("document.title")
        print(f"Tab 1 title: {title}")
        assert "LoanPulse" in title, f"Expected LoanPulse in title, got {title}"
        body_text = tab1.eval("document.body.innerText")
        assert "Log In" in body_text, "Expected 'Log In' button on public homepage"
        print("[PASS] Public homepage is accessible without login.")

        # ---------------------------------------------------------------------
        # TEST 2: Manager signs into Tab 1
        # ---------------------------------------------------------------------
        print("\n=== TEST 2: Manager Logs In to Tab 1 ===")
        tab1.navigate(f"{base_url}/login/admin")
        tab1.eval("document.getElementById('email').value = 'manager01@example.test'")
        tab1.eval("document.getElementById('password').value = 'demo123'")
        tab1.eval("document.getElementById('login-form').submit()")
        time.sleep(1.5)

        tab1_url = tab1.eval("window.location.href")
        tab1_wid = tab1.eval("sessionStorage.getItem('lp_wid')")
        print(f"Tab 1 URL after login: {tab1_url}")
        print(f"Tab 1 wid in sessionStorage: {tab1_wid}")
        assert "/manager/queue" in tab1_url, f"Expected /manager/queue in URL, got {tab1_url}"
        assert tab1_wid is not None and tab1_wid.startswith("win_"), "Expected tab1_wid in sessionStorage"
        assert f"wid={tab1_wid}" in tab1_url, "Expected wid in URL query params"
        header_text = tab1.eval("document.body.innerText")
        assert "Manager Queue" in header_text or "Manager" in header_text, "Expected Manager Workspace text"
        print("[PASS] Manager is successfully authenticated in Tab 1 with tab-scoped wid.")

        # ---------------------------------------------------------------------
        # TEST 3: Open Tab 2 with clean copied URL (Requirement 1 & 4)
        # ---------------------------------------------------------------------
        print("\n=== TEST 3: New Tab Opens Clean Dashboard URL (Requires Login) ===")
        clean_manager_url = f"{base_url}/manager/queue"
        tab2 = open_tab(clean_manager_url)
        time.sleep(1.5)

        tab2_url = tab2.eval("window.location.href")
        print(f"Tab 2 URL: {tab2_url}")
        assert "/login" in tab2_url, f"Expected Tab 2 to redirect to login, got {tab2_url}"
        tab2_body = tab2.eval("document.body.innerText")
        assert "Administration Login" in tab2_body or "Sign In" in tab2_body, "Expected login form"
        assert "Manager Queue" not in tab2_body, "New Tab must NOT display Manager Queue without logging in!"

        # Verify Tab 1 is STILL active and logged in
        tab1_body = tab1.eval("document.body.innerText")
        assert "Manager Queue" in tab1_body or "Manager" in tab1_body, "Tab 1 must remain active!"
        print("[PASS] New Tab 2 with clean copied URL was redirected to login. Did NOT inherit Tab 1!")

        # ---------------------------------------------------------------------
        # TEST 4: Open Tab 3 with URL containing Tab 1's wid (Guard Test)
        # ---------------------------------------------------------------------
        print("\n=== TEST 4: New Tab Opens Copied URL with Wid (Fails Closed) ===")
        tab3 = open_tab(tab1_url)
        time.sleep(1.5)

        tab3_url = tab3.eval("window.location.href")
        print(f"Tab 3 URL: {tab3_url}")
        assert "/login" in tab3_url, f"Expected Tab 3 to fail closed and redirect to login, got {tab3_url}"
        print("[PASS] New Tab 3 copying wid from Tab 1 was blocked and redirected to login.")

        # ---------------------------------------------------------------------
        # TEST 5: Tab 2 logs in as Customer (Multi-role concurrent sessions)
        # ---------------------------------------------------------------------
        print("\n=== TEST 5: Tab 2 Logs In as Customer (Multi-role tabs) ===")
        tab2.navigate(f"{base_url}/login/user")
        tab2.eval("document.getElementById('email').value = 'borrower01@example.test'")
        tab2.eval("document.getElementById('password').value = 'demo123'")
        tab2.eval("document.getElementById('login-form').submit()")
        time.sleep(1.5)

        tab2_url = tab2.eval("window.location.href")
        tab2_wid = tab2.eval("sessionStorage.getItem('lp_wid')")
        print(f"Tab 2 URL: {tab2_url}")
        print(f"Tab 2 wid: {tab2_wid}")
        assert "/customer/dashboard" in tab2_url, f"Expected customer dashboard, got {tab2_url}"
        assert tab2_wid != tab1_wid, "Tab 2 must have its own distinct window ID!"
        tab2_text = tab2.eval("document.body.innerText")
        assert "Dashboard" in tab2_text or "Borrower" in tab2_text

        # Verify Tab 1 STILL retains Manager workspace across reload
        tab1.eval("window.location.reload()")
        time.sleep(1.5)
        tab1_reloaded_text = tab1.eval("document.body.innerText")
        assert "Manager" in tab1_reloaded_text, "Tab 1 must retain Manager workspace after reload!"
        print("[PASS] Tab 1 (Manager) and Tab 2 (Customer) run concurrently in the same browser!")

        # ---------------------------------------------------------------------
        # TEST 6: Tab 4 logs in as Loan Officer (Three roles simultaneously)
        # ---------------------------------------------------------------------
        print("\n=== TEST 6: Tab 4 Logs In as Loan Officer ===")
        tab4 = open_tab(f"{base_url}/login/admin")
        tab4.eval("document.getElementById('email').value = 'officer01@example.test'")
        tab4.eval("document.getElementById('password').value = 'demo123'")
        tab4.eval("document.getElementById('login-form').submit()")
        time.sleep(1.5)

        tab4_url = tab4.eval("window.location.href")
        tab4_wid = tab4.eval("sessionStorage.getItem('lp_wid')")
        print(f"Tab 4 URL: {tab4_url}")
        print(f"Tab 4 wid: {tab4_wid}")
        assert "/officer/queue" in tab4_url
        assert tab4_wid not in (tab1_wid, tab2_wid)
        tab4_text = tab4.eval("document.body.innerText")
        assert "Officer" in tab4_text or "Loan Officer" in tab4_text

        # All 3 tabs verified
        print("[PASS] Three distinct roles (Customer, Officer, Manager) working simultaneously in separate tabs!")

        # ---------------------------------------------------------------------
        # TEST 7: Cross-role RBAC Enforcement
        # ---------------------------------------------------------------------
        print("\n=== TEST 7: Customer Tab Attempts Access to Manager Queue ===")
        tab2.navigate(f"{base_url}/manager/queue?wid={tab2_wid}")
        time.sleep(1.2)
        tab2_forbidden_text = tab2.eval("document.body.innerText")
        print(f"Tab 2 RBAC text snippet: {tab2_forbidden_text[:120]}...")
        assert "403" in tab2_forbidden_text or "Access Denied" in tab2_forbidden_text, "Expected 403 Access Denied!"
        assert "Back to Customer Workspace" in tab2_forbidden_text
        print("[PASS] Cross-role access denied with 403 and correct role-specific return button.")

        # ---------------------------------------------------------------------
        # TEST 8: Single Active Session Enforcement
        # ---------------------------------------------------------------------
        print("\n=== TEST 8: Re-login from Another Tab Invalidates Previous Session ===")
        tab5 = open_tab(f"{base_url}/login/admin")
        tab5.eval("document.getElementById('email').value = 'manager01@example.test'")
        tab5.eval("document.getElementById('password').value = 'demo123'")
        tab5.eval("document.getElementById('login-form').submit()")
        time.sleep(1.5)
        tab5_url = tab5.eval("window.location.href")
        assert "/manager/queue" in tab5_url, "Tab 5 should successfully log in as Manager"

        # Now reload Tab 1 (earlier session for manager01)
        tab1.eval("window.location.reload()")
        time.sleep(1.5)
        tab1_after_url = tab1.eval("window.location.href")
        print(f"Tab 1 URL after invalidation: {tab1_after_url}")
        assert "/login" in tab1_after_url, f"Expected Tab 1 to be redirected to login, got {tab1_after_url}"
        print("[PASS] Previous session in Tab 1 was successfully invalidated by new login in Tab 5.")

        print("\n" + "=" * 60)
        print(">>> ALL REAL-BROWSER MULTI-TAB TESTS PASSED PERFECTLY! <<<")
        print("=" * 60 + "\n")

    finally:
        chrome_proc.terminate()
        server_proc.terminate()


if __name__ == "__main__":
    run_tests()
