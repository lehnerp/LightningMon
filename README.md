# Lightning Monitor · v2.0

One Python process that:

- collects live strikes from the LightningMaps / Blitzortung WebSocket around a configured point,
- keeps a 30-day SQLite history with reverse-geocoded locality names,
- pushes aggregate metrics to Zabbix (`zabbix_sender`),
- sends warning / critical e-mails with an embedded satellite PNG and storm-trend analysis,
- serves a live dashboard on TCP/8097 (Leaflet satellite map, activity timeline, strike table, health, EN/CZ, light/dark, in-browser settings and restart).

> Lightning data here is community-sourced and the LightningMaps endpoint is unofficial. Do not treat this as an official severe-weather or life-safety warning service.

## Quick start (Linux / Raspberry Pi)

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp -n config.example.json config.json
nano config.json            # coordinates, SMTP, Zabbix …
./run.sh
```

Open `http://<host-ip>:8097/`. Everything (`config.json`, `templates/`, `static/`, `lightning.db`) is resolved relative to `lightning.py`, so the folder can live anywhere and run as any normal user. To keep the config elsewhere: `LIGHTNING_CONFIG=/path/to/config.json ./run.sh`.

## Windows

Use a virtual environment in the project folder (the background task runs as the system account and needs the packages inside the folder):

```bat
py -3 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy config.example.json config.json
notepad config.json
```

Everything else is done with `run.bat`:

| Command | What it does |
|---|---|
| `run.bat` | Run in the current window (Ctrl+C stops it). |
| `run.bat install` | Register the **"Lightning Monitor"** scheduled task: starts at boot (before anyone logs in), restarts after a crash or a dashboard restart, no time limit, and opens the dashboard port in Windows Firewall for private/domain networks. Asks for administrator rights. |
| `run.bat status` | Task state, whether the dashboard is listening, last 15 log lines. |
| `run.bat stop` / `run.bat start` | Stop or start the background task. |
| `run.bat uninstall` | Remove the task and the firewall rule (files and database stay). |

Background output goes to `lightning.log` beside `lightning.py` (rotated to `lightning.log.old` at 10 MB). Run `run.bat install` again after moving the folder or recreating the venv.

Notes:
- The Microsoft Store Python cannot run as a background task; `install` detects it and asks for the python.org installer.
- `zabbix_sender` is usually not installed on Windows. Set `"zabbix": {"enabled": false}`, or install the Zabbix agent tools and put `zabbix_sender.exe` on PATH.
- If your network is set to *Public* in Windows, other computers cannot reach the dashboard (the firewall rule covers private/domain networks only).
- Snapshot labels use Segoe UI / Arial from `C:\Windows\Fonts` automatically.

## Run as a service (systemd)

```bash
./install-systemd.sh                       # writes the unit with this folder + your user
sudo systemctl enable --now lightning-dashboard.service
journalctl -u lightning-dashboard.service -f
```

If an older `lightning.service` exists, disable it first (`sudo systemctl disable --now lightning.service`) so two copies don't compete for the port. A second copy now exits immediately with:

```text
Cannot bind dashboard to 0.0.0.0:8097: address already in use or not available (is another copy of the monitor running?)
```

## Configuration

All settings are in `config.json`. On startup, missing keys are added from the built-in defaults and the file is rewritten atomically; existing values are never changed. Most settings can also be edited live from **Settings** in the dashboard.

| Section | Key | Meaning |
|---|---|---|
| `monitoring` | `center_lat`, `center_lon` | Monitored point. Changing it live re-subscribes the feed automatically. |
| | `max_radius_km` | Collection radius (strikes further away are ignored). |
| | `window_seconds` | Live window for the "10 min" metrics. |
| | `history_retention_days` | SQLite history kept (default 30). |
| | `send_interval_seconds` | Periodic Zabbix push interval. |
| `alerts` | `warning_radius_km`, `critical_radius_km` | Alert zones. The dashboard rings, legend, table colours and PNG follow these values. |
| | `*_cooldown_seconds`, `max_strike_age_seconds` | E-mail rate limiting and staleness guard. |
| `smtp` | `enabled` | **new** – `false` disables all e-mail (health shows SMTP as disabled). |
| | `send_startup_email` | **new** – send the "monitor online" mail at start. |
| | `server`, `port`, `mail_from`, `mail_to` | Plain SMTP relay (no auth / STARTTLS). |
| `zabbix` | `enabled` | **new** – `false` disables `zabbix_sender`. |
| | `server`, `host` | Zabbix server and trapper host name. |
| `web` | `host`, `port` | Dashboard bind address (restart required). |
| | `allow_config_write`, `allow_restart` | Allow editing / restarting from the browser. |
| | `admin_password` | **new** – when set, Settings and Restart ask for this password (HTTP Basic, any user name). Empty = open (as before). |
| `geocoding` | `enabled`, `url`, `user_agent`, … | Nominatim reverse geocoding. Please put a contact e-mail in `user_agent` (Nominatim usage policy). |
| `map` | `sat_tile_url`, `snapshot_*` | PNG snapshot. `font_path` (**new**) optionally points to a .ttf font. |
| `localization` | `default_language`, `email_language` | `en` or `cs` (`cz` is still accepted). |
| `intelligence` | trend / burst thresholds | Storm-trend analysis used by alerts and the dashboard. |

Changes to `web.host`, `web.port`, `database.path` and `geocoding.queue_maxsize` are saved but need a restart (**Save & restart** in the dashboard).

### Protecting the dashboard

The dashboard listens on all interfaces by default. If it is reachable by people who shouldn't change settings, set `web.admin_password` (or set `allow_config_write` / `allow_restart` to `false`). Viewing the dashboard and switching its language stay open; reading or changing the configuration and restarting require the password. The password is never sent back to the browser (shown as `********`).

## Dashboard

- live satellite / street map with configurable alert rings; strike markers fade with age and the newest strike pulses
- range selector: 10 min … 30 days (remembered per browser)
- **activity timeline**: stacked bars of critical / warning / further strikes over the selected range
- stats: 10-minute count, closest strike, last strike, e-mail status
- storm intelligence: distance trend, activity trend, nearby activity
- **system health** with a chip per component (DB, feed, SMTP, Zabbix, geocoder; disabled ones greyed out)
- recent-detections table with localities ("open area / water" when the geocoder finds no place)
- when the tab is in the background, its title flashes on a new strike inside the warning zone
- EN/CZ and light/dark switches; Settings editor (Tab indents, Ctrl+S saves)

## HTTP API

| Endpoint | Description |
|---|---|
| `GET /api/status` | Live metrics, zones/rings, feed and e-mail status |
| `GET /api/strikes?minutes=60&limit=500` | Strike history (max 5000 rows) |
| `GET /api/timeline?minutes=60` | 60 time buckets split by zone |
| `GET /api/intelligence` | Storm trend analysis |
| `GET /api/health` | Component health (HTTP 503 when degraded) |
| `GET /api/snapshot/latest.png?lang=cs` | Satellite PNG of the latest strike |
| `GET/POST /api/config` | Read / update configuration (password if set) |
| `POST /api/restart` | Restart the process (password if set) |

## Zabbix trapper keys

```text
lightning.closest.age_sec
lightning.closest.distance_km
lightning.strikes.5km.10min
lightning.strikes.10km.10min
lightning.strikes.25km.10min
lightning.strikes.50km.10min
lightning.strikes.100km.10min
```

Metrics are pushed every `send_interval_seconds` and immediately (at most once per burst) when a strike lands inside the warning zone.

## Alerting behaviour

- A burst of strikes produces **one** alert check for the closest strike in the burst. Alerts run in a background worker, so e-mail, geocoding and tile downloads never stall the live feed.
- Same-level alerts respect the cooldowns. Escalation to critical, a strike significantly closer than the last alert, or an approaching / intensifying storm can send an earlier update (guarded by `min_smart_resend_seconds`).
- E-mails include an inline satellite PNG with the alert rings, the alert strike and the other strikes in the live window, plus the same PNG as an attachment.

## Changes in 2.0

**Fixes**
- Geocoder retries no longer sleep inside the only queue consumer. Previously a retry could deadlock the geocoder when the queue was full, and every backoff stalled all live localities.
- Open-water / unnamed locations are stored as "no place" instead of being retried forever and flagging the geocoder as failing.
- A strike burst inside the warning zone could block the WebSocket reader for several seconds per strike (SMTP + geocode + tile download each time). This now runs in a coalescing background worker.
- Locality names were inserted into the page as raw HTML. They are now escaped.
- Werkzeug's "address in use" exit bypassed the friendly bind error, and the post-restart port retry never triggered. Both are fixed.
- Changing the monitored point or radius live now re-subscribes the feed; previously the old bounding box was kept until restart.
- Dashboard rings, legend and zone colours used hard-coded 10 / 25 km instead of the configured radii.
- Restart from the web now works on Windows (`os.execv` does not replace the process there).
- Windows: `run.bat install` sets it up as a background task (boot start, crash restart, firewall rule, log file).
- The startup e-mail no longer delays the first feed connection.

**Additions**
- `smtp.enabled`, `smtp.send_startup_email`, `zabbix.enabled`, `web.admin_password`, `map.font_path`
- activity timeline, per-component health chips, recenter button, newest-strike pulse, age-faded markers, background-tab strike alert
- satellite tile cache, SQLite WAL mode, automatic reconnect when the feed goes silent, hourly re-run of the locality backfill, `run.bat`
