# oopsys-server

Central monitoring server for the oopsys stack. Remote **oopsys-agent** instances push metrics, container state, and application errors over HTTP. The web UI groups data by project, deduplicates errors, tracks agent liveness, and can forward alerts to Telegram.

## Requirements

- Docker 24+ and Docker Compose v2 (recommended), **or**
- Python 3.13+, [uv](https://docs.astral.sh/uv/), PostgreSQL 16+
- Optional: NATS with JetStream (required only if you use the Telegram bot worker)

## Quick start (Docker Compose)

This is the intended production layout: one host runs the server, Postgres, NATS, and bot-worker. Agents run on other machines and call your public URL.

### 1. Clone and configure

```bash
git clone <repository-url> oopsys-server
cd oopsys-server
cp .env.example .env
```

Edit `.env` before starting:

| Variable | Action |
|----------|--------|
| `SECURITY__SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SECURITY__BOT_TOKEN_KEY` | Generate a **different** long random string |
| `POSTGRESQL__PASSWORD` | Strong password |
| `DEV` | `false` in production |
| `OOPSYS_PUBLIC_IP` | Your server's **public** IPv4 — enables automatic HTTPS (leave empty for plain HTTP) |
| `OOPSYS_ACME_EMAIL` | Email for Let's Encrypt (required when `OOPSYS_PUBLIC_IP` is set) |
| `SECURITY__COOKIE_SECURE` | `true` with `OOPSYS_PUBLIC_IP`; `false` for plain HTTP |

`nginx` listens on ports **80** and **443**. With `OOPSYS_PUBLIC_IP` set, Certbot obtains a certificate automatically; open both ports on the firewall.

### 2. Start the stack

Production with HTTPS — set in `.env`:

```env
OOPSYS_PUBLIC_IP=203.0.113.10
OOPSYS_ACME_EMAIL=you@example.com
SECURITY__COOKIE_SECURE=true
```

Plain HTTP — leave `OOPSYS_PUBLIC_IP` empty, `SECURITY__COOKIE_SECURE=false`.

```bash
docker compose up -d --build
```

| Service | Role |
|---------|------|
| `server` | FastAPI app (internal) |
| `nginx` | reverse proxy; Certbot inside when `OOPSYS_PUBLIC_IP` is set |
| `postgres` | database |
| `nats` | JetStream |
| `bot-worker` | Telegram |

```bash
docker compose ps
docker compose logs -f server
docker compose logs -f nginx
```

### 3. Create a web account

Credentials are shown **once**:

```bash
docker compose exec server oopsys-server account create
```

Optional flags: `--login NAME --password SECRET`.

### 4. Open the UI and bind agents

1. Browse to `https://<your-public-ip>` or `http://<your-host>`.
2. Log in with the credentials from step 3.
3. On **Agents**, paste an agent token from the remote host:

   ```bash
   # on the machine running oopsys-agent
   oopsys-agent token create --label production-1
   ```

4. Configure each agent to reach this server (HTTPS in production):

   ```env
   SERVER__URL=https://YOUR.PUBLIC.IP
   ```

The token is stored as a SHA-256 hash only; it cannot be read back from the UI. Revoking a token makes ingest return `401` for that agent.

### 5. Telegram bots (optional)

1. Create a bot via [@BotFather](https://t.me/BotFather).
2. In the web UI (**Bots**), add the bot token. You receive an invite key and `/start <invite_key>` instruction.
3. The `bot-worker` service must be running (`NATS__ENABLED=true`).

## HTTPS

Service `nginx` in `docker-compose.yml` — configs in `docker/nginx/`:

- `OOPSYS_PUBLIC_IP` empty → HTTP on port 80
- `OOPSYS_PUBLIC_IP` set → Certbot gets a Let's Encrypt cert for that IP, HTTPS on 443, auto-renewal every 6 hours

Test first with `OOPSYS_ACME_STAGING=true` if you want.

## Local development (without Docker)

### Dependencies

```bash
uv sync
```

### Database

Run PostgreSQL locally, then set in `.env`:

```env
DEV=true
POSTGRESQL__HOST=localhost
POSTGRESQL__PORT=5432
POSTGRESQL__USERNAME=postgres
POSTGRESQL__PASSWORD=postgres
POSTGRESQL__DATABASE=postgres
NATS__ENABLED=false
SECURITY__COOKIE_SECURE=false
```

Apply migrations and create an account:

```bash
uv run oopsys-server migrate
uv run oopsys-server account create
uv run oopsys-server run
```

UI: `http://127.0.0.1:8000`

With NATS and bots locally, start NATS, set `NATS__ENABLED=true` and `NATS__SERVERS=["nats://localhost:4222"]`, then in another terminal:

```bash
uv run oopsys-bot
```

### UI preview (no database)

Renders all pages on mock data. Requires `DEV=true`:

```bash
DEV=true uv run oopsys-server preview
```

Open `http://127.0.0.1:8001/__preview` (port **8001** so it does not clash with the main server).

## CLI reference

All commands are available inside the `server` container as `oopsys-server`, or locally via `uv run oopsys-server`.

```bash
oopsys-server account create [--login L] [--password P]
oopsys-server account list
oopsys-server account reset-password <login> [--password P]

oopsys-server token list
oopsys-server token revoke <token_id>

oopsys-server bot list

oopsys-server migrate
oopsys-server run
oopsys-server preview    # DEV=true only
```

## Agent ingest API

- **Endpoint:** `POST /agents/ingest`
- **Auth:** `Authorization: Bearer <agent-token>`
- **Body:** JSON `Envelope` (`schema_version`, `agent_id`, `source`, `occurred_at`, `payload`)
- **Sources:** `projects` (errors), `server` (metrics), `docker` (containers), `agent` (agent faults)

Response semantics (agent retries on `>= 400`):

| Code | Meaning |
|------|---------|
| `401` | Invalid or revoked token |
| `202` | Accepted (including malformed payloads logged as self-errors) |
| `5xx` | Temporary server/DB failure — agent should retry |

## Architecture

```
Apps (oopsys-python) → agent POST /reports
  → agent local NATS outbox → HTTP POST /agents/ingest → oopsys-server
      → PostgreSQL, dedup, liveness
      → SSE (web UI)
      → NATS oopsys.notify.<account_id> → bot-worker → Telegram
```

Package layout (clean architecture + [dishka](https://github.com/reagento/dishka)):

- `domain/` — agent contracts, enums, fingerprinting
- `application/` — ingest, notifications, auth, projects, tokens, liveness
- `infrastructure/` — SQLAlchemy, Alembic, security, NATS, SSE hub
- `presentation/` — FastAPI routes, Jinja2 templates, static assets, preview mode
- `oopsys_bot/` — Telegram multibot worker

## Testing and linting

```bash
uv run pytest tests/units
POSTGRESQL__HOST=localhost POSTGRESQL__PORT=5432 uv run pytest tests/integrations
uv run ruff check src
uv run bandit -q -c pyproject.toml -r src
```

Integration tests expect PostgreSQL; see `tests/integrations/conftest.py` for defaults.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Preview refuses to start | `DEV=true` in environment or `.env` |
| `ValidationError: server_port` | Fixed in current code (`extra="ignore"`); pull latest |
| Agent always `401` | Token revoked or not bound to an account; re-bind in UI |
| Agent shows `down` | No ingest for `LIVENESS__STALE_SECONDS` (default 90s); check `SERVER__URL` and firewall |
| Login fails locally | `SECURITY__COOKIE_SECURE=false` for plain HTTP |
| `nginx` restart loop / cert fails | Ports 80/443 open; `OOPSYS_PUBLIC_IP` matches public IP; try `OOPSYS_ACME_STAGING=true` |
| Bot messages missing | `bot-worker` running, NATS up, bot linked via `/start`, account has bot configured |
