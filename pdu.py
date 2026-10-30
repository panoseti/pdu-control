#!/usr/bin/env python3
"""Control a UniFi Power Distribution Pro through the local UniFi OS console (e.g. UCG-Fiber).

Only uses the Python standard library. Credentials must be a *local* UniFi OS user
with admin rights on the Network application (cloud/SSO accounts can't log in locally).

Environment (also read from a .env file next to this script; real environment
variables take precedence):
    UNIFI_HOST   console address, e.g. 192.168.1.1
    UNIFI_USER   local username
    UNIFI_PASS   local password
    UNIFI_SITE   site name (default: "default")

The login session is cached in ~/.cache/pdu-control/session.json and reused across runs,
so repeated invocations don't hit the console's login rate limit.

Usage:
    pdu.py list
    pdu.py on 3
    pdu.py off 3
    pdu.py cycle 3 --delay 10
Add --mac aa:bb:cc:dd:ee:ff if more than one outlet-capable device is adopted.
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request


def load_dotenv(path):
    """Load KEY=VALUE lines from path into os.environ without overriding existing variables."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key, value)


SESSION_FILE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                            "pdu-control", "session.json")


class UniFi:
    def __init__(self, host, user, password, site="default", session_file=SESSION_FILE):
        self.base = f"https://{host}"
        self.host = host
        self.site = site
        self.user = user
        self.password = password
        self.session_file = session_file
        self.cookies = {}
        self.csrf = None
        # UniFi OS consoles ship with a self-signed certificate.
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        self._load_session()

    def _load_session(self):
        try:
            with open(self.session_file, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        # Only reuse a session that belongs to the same console and account.
        if saved.get("host") == self.host and saved.get("user") == self.user:
            self.cookies = saved.get("cookies", {})
            self.csrf = saved.get("csrf")

    def _save_session(self):
        os.makedirs(os.path.dirname(self.session_file), mode=0o700, exist_ok=True)
        # The token grants console access, so keep the file private to the current user.
        fd = os.open(self.session_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"host": self.host, "user": self.user,
                       "cookies": self.cookies, "csrf": self.csrf}, f)

    def _send(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()))
        if self.csrf:
            req.add_header("X-CSRF-Token", self.csrf)
        with self.opener.open(req, timeout=15) as resp:
            for header in resp.headers.get_all("Set-Cookie") or []:
                # Only the leading name=value pair matters. SimpleCookie is not used because it
                # silently drops the whole header when it meets an attribute it doesn't know.
                name, sep, value = header.split(";", 1)[0].partition("=")
                if sep:
                    self.cookies[name.strip()] = value.strip()
            token = resp.headers.get("X-Updated-CSRF-Token") or resp.headers.get("X-CSRF-Token")
            if token:
                self.csrf = token
            raw = resp.read()
        self._save_session()
        return json.loads(raw) if raw else {}

    def _request(self, method, path, body=None):
        try:
            fresh = not self.cookies
            if fresh:
                self.login()
            try:
                return self._send(method, path, body)
            except urllib.error.HTTPError as e:
                # A 401 right after a fresh login won't be fixed by logging in again.
                if e.code != 401 or fresh:
                    raise
            # Cached session expired: log in once and retry.
            self.login()
            return self._send(method, path, body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                sys.exit("Login rate limit reached on the console (HTTP 429); wait a while before retrying.")
            sys.exit(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='replace')}")

    def login(self):
        self.cookies, self.csrf = {}, None
        try:
            self._send("POST", "/api/auth/login",
                       {"username": self.user, "password": self.password, "remember": True})
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403):
                sys.exit(f"Login failed (HTTP {e.code}): check UNIFI_USER/UNIFI_PASS and that it is a local account.")
            raise
        if not self.cookies:
            sys.exit("Login succeeded but the console returned no session cookie.")

    def devices(self):
        return self._request("GET", f"/proxy/network/api/s/{self.site}/stat/device")["data"]

    def set_outlet_overrides(self, device_id, overrides):
        self._request("PUT", f"/proxy/network/api/s/{self.site}/rest/device/{device_id}",
                      {"outlet_overrides": overrides})


def find_pdu(devices, mac=None):
    candidates = [d for d in devices if d.get("outlet_table")]
    if mac:
        candidates = [d for d in candidates if d.get("mac", "").lower() == mac.lower()]
    if not candidates:
        sys.exit("No outlet-capable device found" + (f" with MAC {mac}" if mac else ""))
    if len(candidates) > 1:
        names = ", ".join(f"{d.get('name', d.get('model'))} ({d['mac']})" for d in candidates)
        sys.exit(f"Multiple outlet devices found, pick one with --mac: {names}")
    return candidates[0]


def print_outlets(pdu):
    print(f"{pdu.get('name', pdu.get('model'))}  model={pdu.get('model')}  mac={pdu.get('mac')}")
    for o in sorted(pdu["outlet_table"], key=lambda o: o["index"]):
        state = "ON " if o.get("relay_state") else "OFF"
        power = f"{o['outlet_power']} W" if "outlet_power" in o else ""
        print(f"  {o['index']:>2}  {state}  {o.get('name', ''):<24} {power}")


def set_relay(api, pdu, index, on):
    outlets = {o["index"]: o for o in pdu["outlet_table"]}
    if index not in outlets:
        sys.exit(f"Outlet {index} does not exist (valid: {sorted(outlets)})")
    # The controller replaces the whole override list, so send every existing entry back.
    overrides = [dict(o) for o in pdu.get("outlet_overrides", [])]
    entry = next((o for o in overrides if o["index"] == index), None)
    if entry is None:
        entry = {"index": index, "name": outlets[index].get("name", f"Outlet {index}"),
                 "cycle_enabled": outlets[index].get("cycle_enabled", False)}
        overrides.append(entry)
    entry["relay_state"] = on
    api.set_outlet_overrides(pdu["_id"], overrides)
    pdu["outlet_overrides"] = overrides


def main():
    p = argparse.ArgumentParser(description="UniFi Power Distribution Pro local control")
    p.add_argument("--mac", help="MAC of the PDU if several outlet devices are adopted")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("on", "off"):
        sub.add_parser(name).add_argument("outlet", type=int)
    cyc = sub.add_parser("cycle")
    cyc.add_argument("outlet", type=int)
    cyc.add_argument("--delay", type=float, default=5, help="seconds to stay off (default 5)")
    args = p.parse_args()

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    try:
        api = UniFi(os.environ["UNIFI_HOST"], os.environ["UNIFI_USER"], os.environ["UNIFI_PASS"],
                    os.environ.get("UNIFI_SITE", "default"))
    except KeyError as e:
        sys.exit(f"Missing environment variable {e}")
    pdu = find_pdu(api.devices(), args.mac)

    if args.cmd == "list":
        print_outlets(pdu)
    elif args.cmd in ("on", "off"):
        set_relay(api, pdu, args.outlet, args.cmd == "on")
        print(f"Outlet {args.outlet} -> {args.cmd.upper()}")
    elif args.cmd == "cycle":
        set_relay(api, pdu, args.outlet, False)
        print(f"Outlet {args.outlet} -> OFF, waiting {args.delay}s")
        time.sleep(args.delay)
        set_relay(api, pdu, args.outlet, True)
        print(f"Outlet {args.outlet} -> ON")


if __name__ == "__main__":
    main()
