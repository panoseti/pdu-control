# pdu-control

English | [简体中文](README_CN.md)

A command-line script for controlling a UniFi Power Distribution Pro (USP-PDU-Pro) over the local network. It talks to the local API of the Network application built into a UniFi OS console (e.g. UCG-Fiber), without going through the Ubiquiti cloud.

Requires Python 3.14 or later. Uses only the standard library; no third-party packages are needed.

> Note: the script relies on UniFi Network's unofficial local API. It has not been fully verified on real hardware, and the API may change after firmware upgrades.

## Installation

### Python version

**Python 3.14 or later** is required. Check your current version:

```bash
python3 --version
```

If it is older than 3.14, install a newer one using any of the following:

```bash
# uv (cross-platform, recommended)
uv python install 3.14
uv run --python 3.14 ./pdu.py list

# pyenv
pyenv install 3.14
pyenv local 3.14

# Fedora
sudo dnf install python3.14

# macOS (Homebrew)
brew install python@3.14
```

On Windows, download the 3.14 installer from [python.org](https://www.python.org/downloads/).

### Dependencies

The script only uses the Python standard library (`urllib`, `http.cookiejar`, `ssl`, `json`, `argparse`, etc.). **No `pip install` is required**, and no virtual environment is needed.

### Getting the script

```bash
git clone <repository-url> pdu-control
cd pdu-control
chmod +x pdu.py
```

If your default `python3` is older than 3.14, run the script with an explicit interpreter:

```bash
python3.14 ./pdu.py list
```

## Prerequisites

- The PDU Pro is adopted by a UniFi console (UCG-Fiber, UDM, etc.) on your LAN
- The machine running the script can reach the console's HTTPS port
- A **local account** exists on the console (Ubiquiti cloud/SSO accounts will not work); see permissions below

To create a local account: UniFi OS → Admins & Users → add an admin, select "Restrict to local access only", and assign an appropriate role for the Network application.

## Account permissions

The script only needs permissions for the Network application. It does not need UniFi OS Super Admin/Owner, nor access to other applications such as Protect or Access.

| Operation | Required permission |
| --- | --- |
| `list` (view outlet state and power) | Network View Only should be sufficient |
| `on` / `off` / `cycle` (switch outlets) | Network management permission |

Switching an outlet is done by updating the device's `outlet_overrides` via `PUT rest/device/<id>`. This is a write operation, so a read-only account will receive 401/403.

Network role names and granularity vary between UniFi OS versions. Whether a limited role between View Only and full management can switch outlets has not been verified. Follow the principle of least privilege:

1. Start with a read-only account and run `./pdu.py list`; keep using it if you only need monitoring
2. When switching is needed, start from the lowest writable role and test `off` / `on` on a non-critical outlet, raising the role step by step if you get 403

Create a dedicated account for the script rather than using your personal account, so it can be revoked and audited independently.

## Configuration

Connection settings are provided through environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `UNIFI_HOST` | Console address, e.g. `192.168.1.1` | required |
| `UNIFI_USER` | Local account username | required |
| `UNIFI_PASS` | Local account password | required |
| `UNIFI_SITE` | Site name | `default` |

```bash
export UNIFI_HOST=192.168.1.1
export UNIFI_USER=pdu-admin
export UNIFI_PASS='your-password'
```

### Using a `.env` file

Instead of exporting variables by hand, copy the template and fill in real values:

```bash
cp .env.example .env
# edit .env: set UNIFI_HOST, UNIFI_USER, UNIFI_PASS
```

On startup the script automatically loads `.env` from the directory containing `pdu.py`, so you can run it directly from any working directory:

```bash
./pdu.py list
```

Variables already set in the environment take precedence over `.env`, so you can override a single value for one run, e.g. `UNIFI_HOST=10.0.0.1 ./pdu.py list`. Supported syntax: `KEY=VALUE` lines, `#` comments, optional `export ` prefix and optional surrounding quotes.

`.env` is listed in `.gitignore`, so your credentials will not be committed. Only `.env.example` (placeholder values) is tracked.

The console uses a self-signed certificate, so the script does not verify TLS certificates.

## Usage

```bash
./pdu.py list                 # list outlets with index, state, name and power
./pdu.py on 3                 # turn outlet 3 on
./pdu.py off 3                # turn outlet 3 off
./pdu.py cycle 3              # power off for 5 seconds, then back on
./pdu.py cycle 3 --delay 10   # custom off duration (seconds)
```

If the console has adopted more than one outlet-capable device (e.g. SmartPower plugs as well), select the PDU with `--mac`:

```bash
./pdu.py --mac aa:bb:cc:dd:ee:ff list
```

Example `list` output (the model field is whatever the controller reports):

```
Rack PDU  model=<model>  mac=aa:bb:cc:dd:ee:ff
   1  ON   NAS                      42.1 W
   2  OFF  Outlet 2
   ...
```

## Caveats

- Use a non-critical outlet for your first test. **Do not switch off the outlet powering the UCG-Fiber or your switches**, or the network will go down and the script will be unable to turn it back on.
- `cycle` is a two-step operation (off, wait, on). If the script is interrupted midway, the outlet stays off.
- If you get `HTTP 401/403`, check that the account is a local account with Network management permission.
- The console rate-limits logins (`HTTP 429`, `AUTHENTICATION_FAILED_LIMIT_REACHED`). To avoid this, the script caches its login session in `~/.cache/pdu-control/session.json` (permissions `600`) and only logs in again when the session expires. Delete this file to force a fresh login. If you do hit the limit, wait a while before retrying.
