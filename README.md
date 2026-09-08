# CVLab

A local-first CV workbench. Write and version CVs in a browser, tailor them to a
job advert with an AI provider of your choosing, export ATS-friendly PDF / DOCX /
plain text through Pandoc + XeLaTeX, and track the applications you send.

Everything runs on your machine. Your CVs, job applications and exports live in
directories on the host and are never uploaded anywhere — except the text you
explicitly send to an AI provider, and only after you grant consent.

- **Full feature list:** [docs/CAPABILITIES.md](docs/CAPABILITIES.md)
- **Stack:** FastAPI backend, statically-exported Next.js frontend, Pandoc +
  XeLaTeX export pipeline, all in one container.

---

## 1. Requirements

| Tool | Version tested | Notes |
| --- | --- | --- |
| Docker | 29.x | Docker Desktop, Colima, or any Linux daemon |
| Docker Compose | v2 or v5 | `docker compose` or `docker-compose` |
| Disk | ~3 GB | The image bundles a TeX distribution |
| RAM | 2 GB | Allocated to the Docker VM |

Nothing else is needed. Python, Node, Pandoc and XeLaTeX all live inside the
image — you do **not** need them on the host unless you want to develop against
the source (see [§6](#6-developing)).

> **Compose command:** if `docker compose version` fails but `docker-compose
> version` works, you have the standalone binary. Use `docker-compose` in place
> of `docker compose` in every command below, or link it as a CLI plugin:
> `mkdir -p ~/.docker/cli-plugins && ln -s "$(which docker-compose)" ~/.docker/cli-plugins/docker-compose`

---

## 2. Quick start

```bash
git clone <your-fork-url> cvlab
cd cvlab
cp .env.example .env          # optional: only needed for AI features
docker-compose up --build -d  # first build takes 5-10 min (TeX layer)
```

Open **<http://localhost:8002>**.

Confirm the toolchain came up correctly:

```bash
curl -s http://localhost:8002/health | python3 -m json.tool
```

A healthy response reports `"status": "healthy"` with `pandoc`, `xelatex`,
`data_directory` and `required_files` all `ok`. If any check fails, see
[§8 Troubleshooting](#8-troubleshooting).

Stop and start:

```bash
docker-compose down     # stop (your data on the host is untouched)
docker-compose up -d    # start again
```

---

## 3. Where your data lives

Three host directories are bind-mounted into the container. They are the only
places CVLab writes, and all three are excluded from git.

| Host path | Container path | Contents |
| --- | --- | --- |
| `./data/` | `/app/data` | CVs (`data/cvs/`), job applications, AI config and key, backups |
| `./exports/` | `/app/exports` | Generated `pdf/`, `docx/` and `txt/` files |
| `./cv/` | `/app/cv` | Scratch Markdown used by the export script |

Back these up and you have backed up everything. See [§7](#7-backups).

---

## 4. First run

### 4.1 Create or import a CV

On the **CVs** page:

- **New CV** starts an empty CV with a Personal Information section.
- **Import** accepts a Markdown file (`.md` / `.markdown`) that CVLab previously
  exported, including its YAML frontmatter.
- **AI Import** accepts a PDF, DOCX, TXT or Markdown file and asks the
  configured AI provider to parse it into structured sections. This requires AI
  to be switched on first (§4.2).

### 4.2 Turn on AI features (optional)

Everything except the AI panels works with no provider configured. To enable
them, go to **Settings → AI** (the gear icon, `/settings/llm/`) and pick a
provider:

| Provider | What you need |
| --- | --- |
| `anthropic` | An API key from <https://console.anthropic.com/> |
| `openai` | An API key from <https://platform.openai.com/api-keys> |
| `bedrock` | AWS credentials or an IAM role with Bedrock access |
| `claude_code` | A Claude Code OAuth token from `claude setup-token` |
| `local` | An Ollama server (see §4.3) — nothing leaves your machine |

The key you paste is encrypted at rest with a Fernet key held in
`data/config/.llm_key` and stored in `data/config/llm_config.json`. You must
grant consent once before any text is sent to a remote provider; each grant and
revocation is appended to `data/config/llm_consent_log.json`.

You can supply credentials through the environment instead of the UI — copy
`.env.example` to `.env`, uncomment the relevant lines, and restart. `.env` is
gitignored.

Verify the provider works:

```bash
curl -s -X POST http://localhost:8002/api/llm/test-connection | python3 -m json.tool
```

### 4.3 Running a local model (fully offline AI)

```bash
docker-compose --profile local-llm up -d
docker exec cvlab-ollama ollama pull llama3
```

Then set provider `local` with base URL `http://ollama:11434` in Settings → AI.

---

## 5. Everyday use

### 5.1 Editing

The CV editor (`/cv/`) shows a section rail on the left, the editor in the
middle and a live preview on the right. Sections can be added from a predefined
list or created as free-form custom sections, reordered by drag and drop, hidden
without deleting, and edited with a Markdown toolbar. Personal Information
cannot be removed.

### 5.2 Exporting

Use the **Export** panel, or:

```bash
curl -X POST http://localhost:8002/api/export/<cv-id>/pdf
curl -X POST http://localhost:8002/api/export/<cv-id>/docx
curl -X POST http://localhost:8002/api/export/<cv-id>/txt
```

Files land in `exports/pdf`, `exports/docx` and `exports/txt`, named
`<cv-slug>-<timestamp>.<ext>`. PDF is rendered by XeLaTeX through
`templates/cv.latex`; DOCX uses a reference document generated from the CV's
typography settings; TXT is the ATS-safe plain-text form.

### 5.3 Tailoring to a job

The **Job Match** panel takes a job advert (pasted text or a URL it will scrape)
and returns a match score, gap analysis and tailoring suggestions. "Create
tailored CV" writes a new CV rather than overwriting the original, so your
master CV is never modified.

### 5.4 Tracking applications

`/applications/` is a Kanban board across five stages — wishlist, applied,
interview, offer, rejected. It supports interviews, tasks, notes, recruiter
contacts, bulk stage changes, bulk delete, search/filter, and CSV import and
export.

---

## 6. Developing

Source changes need the toolchains on the host.

```bash
# Backend with live reload -> http://localhost:8003
docker-compose --profile dev up cvlab-dev

# Frontend with hot reload -> http://localhost:3000
cd frontend-next && npm install && npm run dev
```

The dev frontend calls the backend cross-origin at `http://localhost:8002/api`
(the backend allows `localhost:3000` in CORS). To point it at the reload backend
instead, set `NEXT_PUBLIC_API_BASE=http://localhost:8003/api` before `npm run
dev`.

The backend is importable as the `app` package with `backend/` on `PYTHONPATH`
(that is why the container sets `PYTHONPATH=/app/backend` and runs
`uvicorn app.main:app`). Several services resolve `/app/...` paths directly, so
running the backend outside a container is not supported.

### Tests

```bash
# Backend (~1,000 tests, mostly Hypothesis property tests; ~5 min)
docker run --rm -v "$PWD/backend:/app/backend" -w /app/backend \
  -e PYTHONPATH=/app/backend cvlab:latest python -m pytest -q

# Frontend (113 tests)
cd frontend-next && npm test
```

Tests import the backend as `app.*`. A handful of backend tests fail today —
see [docs/CAPABILITIES.md §16](docs/CAPABILITIES.md#16-known-test-failures) for
the breakdown. The frontend suite is green.

### Rebuilding after a change

```bash
docker-compose up -d --build cvlab
```

Frontend changes require a rebuild because the static bundle is baked into the
image at build time.

---

## 7. Backups

In the app, **Backup** (`/backup/`) creates a zip of `data/` (optionally
including `exports/`), lists existing backups, downloads them, restores one, and
deletes them. Archives are written to `data/backups/`.

From the shell:

```bash
./scripts/backup-cvlab.sh --host localhost:8002 --dest ~/Backups/cvlab --keep 7
./scripts/backup-cvlab.sh --help
```

See [scripts/BACKUP_SCRIPTS_README.md](scripts/BACKUP_SCRIPTS_README.md) for
scheduling it with cron or launchd.

---

## 8. Troubleshooting

**`docker compose: unknown command`** — you have standalone Compose. Use
`docker-compose`, or link it as a plugin (see §1).

**Health check reports `pandoc` or `xelatex` error** — the image did not build
its TeX layer. Rebuild with `docker-compose build --no-cache cvlab`.

**Export returns 500, logs show `Export script failed with code 127`** — a
command the export pipeline shells out to is missing from the image.
`scripts/export.sh` is a **zsh** script; the image installs `zsh` for exactly
this reason. If you have edited the Dockerfile, check it is still there.

**Export returns 500, logs mention a missing `.sty`** — `templates/cv.latex`
gained a `\usepackage` that the installed TeX packages do not provide. Add the
relevant `texlive-*` package to the Dockerfile and rebuild.

**Blank page, console 404s on `/_next/...`** — the static bundle in the image is
stale or missing. Rebuild: `docker-compose up -d --build cvlab`.

**AI panels say unavailable** — check `GET /api/llm/status`. Most often either
the provider is unconfigured, or consent has not been granted
(`POST /api/llm/consent/grant`).

**Port 8002 in use** — change the left-hand side of the `ports:` mapping in
`docker-compose.yml`.

Logs: `docker logs -f cvlab`.

---

## 9. Privacy

- No telemetry. The backend makes outbound network calls only to the AI provider
  you configure, and to a job-advert URL when you explicitly ask it to parse one.
- API keys are encrypted at rest; the encryption key lives in
  `data/config/.llm_key`, which is gitignored.
- Consent is required before the first remote AI call and is logged.
- Everything under `data/`, `cv/` and `exports/` is gitignored — see the
  "Personal data" block in [.gitignore](.gitignore). Keep it that way if you
  fork this repo, and never commit `.env`.

---

## 10. Licence

See [LICENSE](LICENSE).
