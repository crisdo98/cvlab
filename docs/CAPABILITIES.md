# CVLab — Capabilities

Complete reference for what CVLab can do, feature by feature, with the HTTP API
behind each one. For installation and day-to-day use see the
[README](../README.md).

**Contents**

1. [Architecture](#1-architecture)
2. [CV authoring](#2-cv-authoring)
3. [Sections](#3-sections)
4. [Import](#4-import)
5. [Export](#5-export)
6. [Typography and templates](#6-typography-and-templates)
7. [AI features](#7-ai-features)
8. [Job matching and tailoring](#8-job-matching-and-tailoring)
9. [Application tracker](#9-application-tracker)
10. [Backup and restore](#10-backup-and-restore)
11. [Housekeeping](#11-housekeeping)
12. [Command-line tools](#12-command-line-tools)
13. [Privacy and security](#13-privacy-and-security)
14. [Full API index](#14-full-api-index)
15. [Known limits](#15-known-limits)
16. [Known test failures](#16-known-test-failures)

---

## 1. Architecture

One container serves everything on port 8000 (published as 8002):

```
Browser
  │
  ├── /            static Next.js export (output: "export"), served by FastAPI
  ├── /_next/…     hashed JS/CSS chunks
  ├── /api/…       FastAPI routers
  ├── /exports/…   generated files, served as static
  └── /health      toolchain validation
                     │
                     └── subprocess → scripts/export.sh → pandoc → xelatex
```

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16 (static export), React 19, TanStack Query, Zustand, dnd-kit, Tailwind 4 |
| Backend | FastAPI, Pydantic v2, uvicorn |
| Export | Pandoc 3.1, XeLaTeX (Tectonic supported as a fallback engine), python-docx |
| Storage | JSON files on disk — no database |
| AI | Pluggable providers behind one interface |

**Storage layout**

```
data/
  cvs/<uuid>.json          one file per CV
  cvs/metadata.json        id → title index
  applications.json        job application records
  application_history.json stage-change audit trail
  config/llm_config.json   provider settings + encrypted key
  config/.llm_key          Fernet key (0600)
  config/llm_consent_log.json
  backups/*.zip
  cleanup_config.json
exports/{pdf,docx,txt}/
cv/                        scratch Markdown for the export script
```

---

## 2. CV authoring

- Create, read, update, delete, and duplicate CVs. Any number of CVs coexist.
- Two schema versions are supported. V1 (flat: `personal_info`, `experience`,
  `education`, …) is migrated transparently to V2 (an ordered list of typed
  sections) on load, so older files keep working.
- Live preview renders the CV as it will export, with Markdown in text fields.
- Drafts are held client-side so an accidental navigation does not lose edits.
- Duplicating a CV is the safe way to experiment — the source is untouched.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/cvs` | List all CVs |
| POST | `/api/cvs` | Create a CV |
| GET | `/api/cvs/{cv_id}` | Fetch one CV |
| PUT | `/api/cvs/{cv_id}` | Update a CV (V1 and V2 payloads) |
| DELETE | `/api/cvs/{cv_id}` | Delete a CV |
| POST | `/api/cvs/{cv_id}/duplicate` | Copy a CV |

---

## 3. Sections

Thirteen section types: `personal_info`, `summary`, `experience`, `education`,
`skills`, `languages`, `software`, `certifications`, `accomplishments`,
`affiliations`, `interests`, `websites`, `custom`.

- Add a predefined section, or a custom section with any title you like.
- Multiple custom sections are allowed; duplicate predefined sections are not.
- Reorder by drag and drop; order is persisted and reindexed server-side.
- Toggle visibility to keep a section in the file but out of the export.
- Remove optional sections. `personal_info` is protected and cannot be removed.
- Whitespace-only titles are rejected; new sections are appended at the end.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/cvs/{cv_id}/sections/predefined` | Add a typed section |
| POST | `/api/cvs/{cv_id}/sections/custom` | Add a free-form section |
| DELETE | `/api/cvs/{cv_id}/sections/{section_id}` | Remove a section |
| PUT | `/api/cvs/{cv_id}/sections/order` | Reorder sections |
| PATCH | `/api/cvs/{cv_id}/sections/{section_id}/visibility` | Show/hide |

---

## 4. Import

**Markdown import** (`POST /api/cvs/import`) accepts `.md` / `.markdown` with
optional YAML frontmatter — round-trips anything CVLab exported. It parses
headings into sections, and recognises company / date / LinkedIn conventions in
experience blocks.

**AI import** (`POST /api/llm/parse-cv`) accepts PDF, DOCX, TXT or Markdown as
base64 and asks the configured provider to produce structured sections. Text is
extracted locally first (PyPDF2 / python-docx) — the provider only ever sees
plain text.

---

## 5. Export

Three formats, all driven through `scripts/export.sh`:

| Format | Engine | Use |
| --- | --- | --- |
| PDF | Pandoc → XeLaTeX with `templates/cv.latex` | Sending to humans |
| DOCX | Pandoc with a generated reference document | Recruiter portals that demand Word |
| TXT | Pandoc `--to=plain`, then `normalize_txt.sh` | ATS paste boxes |

Details:

- Filenames are `<cv-slug>-<timestamp>.<ext>`; nothing is ever overwritten.
- The LaTeX template is regenerated per export from the CV's typography, so font
  and spacing choices reach the PDF.
- The DOCX reference document is likewise generated per export, including
  bullet-glyph font rewriting.
- A Lua filter routes the contact line to the right representation per format;
  another strips em dashes.
- Export history is recorded per CV, and generated files can be validated,
  downloaded or deleted individually.
- `POST /api/export/{cv_id}/with-recommendations` produces an export plus an
  optimisation report.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/export/{cv_id}/{format}` | Export to `pdf`, `docx` or `txt` |
| POST | `/api/export/{cv_id}/with-recommendations` | Export + recommendations report |
| GET | `/api/export/history/{cv_id}` | Past exports for a CV |
| GET | `/api/export/download/{file_id}` | Download a generated file |
| GET | `/api/export/templates` | Available export templates |
| GET | `/api/export/files/{path}/validate` | Check a file is present and intact |
| DELETE | `/api/export/files/{path}` | Delete a generated file |

---

## 6. Typography and templates

Per-CV control over fonts, sizes, weights, colours, margins and line spacing,
applied consistently to PDF and DOCX. Built-in templates can be applied
wholesale, and your own settings saved as reusable named templates.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/typography/templates` | List templates |
| GET | `/api/typography/templates/{id}` | Fetch one |
| POST | `/api/typography/templates/save` | Save a custom template |
| PUT | `/api/typography/templates/{id}` | Update a custom template |
| DELETE | `/api/typography/templates/{id}` | Delete a custom template |
| GET | `/api/typography/cv/{cv_id}/typography` | Read a CV's typography |
| PUT | `/api/typography/cv/{cv_id}/typography` | Set a CV's typography |
| POST | `/api/typography/cv/{cv_id}/typography/apply-template` | Apply a template |

---

## 7. AI features

### Providers

| Provider | Transport | Notes |
| --- | --- | --- |
| `anthropic` | Anthropic API | API key |
| `openai` | OpenAI API | API key |
| `bedrock` | AWS Bedrock | Claude, Llama and Titan models; IAM role or keys. See [AWS_BEDROCK_SETUP.md](../backend/app/llm/providers/AWS_BEDROCK_SETUP.md) |
| `claude_code` | Claude Agent SDK | OAuth token from `claude setup-token`; the SDK bundles its own binary |
| `local` | Ollama HTTP | Fully offline |

All providers implement one interface, so every feature below works with any of
them. Failures are classified (auth, rate limit, timeout, content filter,
malformed response) and mapped to meaningful HTTP status codes, with retry and
backoff handled centrally.

### Features

| Feature | Endpoint | What it does |
| --- | --- | --- |
| Content generation | `POST /api/llm/generate-content` | Drafts prose for a section |
| Note expansion | `POST /api/llm/expand-notes` | Turns terse notes into full bullets, preserving facts |
| Achievement suggestions | `POST /api/llm/generate-achievements` | Proposes quantified achievement bullets |
| CV optimisation | `POST /api/llm/optimize-cv` | Weak language, passive voice, tense consistency, achievement formatting |
| Grammar check | `POST /api/llm/check-grammar` | Grammar and style issues with suggested fixes |
| ATS analysis | `POST /api/llm/analyze-ats` | ATS compatibility score, keyword coverage, keyword-stuffing detection |
| CV parsing | `POST /api/llm/parse-cv` | Unstructured document → structured sections |

A truthfulness constraint runs through the prompts and is covered by property
tests: the model rewrites and reorders what you wrote, it does not invent
employers, dates or numbers.

### Configuration, consent and control

| Method | Path | Purpose |
| --- | --- | --- |
| GET/PUT | `/api/llm/config` | Read / update provider, model, temperature, max tokens |
| GET | `/api/llm/status` | Whether AI is enabled, configured and consented |
| POST | `/api/llm/test-connection` | Live provider check |
| POST | `/api/llm/enable` · `/api/llm/disable` | Global kill switch |
| POST | `/api/llm/consent/grant` · `/consent/revoke` | Consent |
| GET | `/api/llm/consent/log` | Audit trail of consent changes |

---

## 8. Job matching and tailoring

| Feature | Endpoint | What it does |
| --- | --- | --- |
| Parse a job advert from a URL | `POST /api/llm/parse-job-url` | Scrapes and extracts title, company and requirements |
| Match score | `POST /api/llm/match-job` | Scores the CV against the advert and identifies gaps |
| Tailoring suggestions | `POST /api/llm/tailor-to-job` | Concrete, per-section changes |
| Create a tailored CV | `POST /api/llm/create-tailored-cv` | Writes a **new** CV; the original is never modified |
| Suitability analysis | `POST /api/job-suitability/analyze-suitability` | Longer-form fit assessment |
| Suitability history | `GET /api/job-suitability/cv/{cv_id}/suitability-history` | Past analyses for a CV |

Scoring methodology: [JOB_MATCHING_SCORER.md](../backend/app/llm/JOB_MATCHING_SCORER.md).
Scraper behaviour: [README_JOB_PARSER.md](../backend/app/services/README_JOB_PARSER.md).

---

## 9. Application tracker

A Kanban board over five stages: **wishlist → applied → interview → offer →
rejected**.

Each application holds company, position, stage, application date, deadline,
job-advert URL, recruiter name / email / phone, hiring manager, interviews,
tasks, notes, feedback, outcome, and a link to the CV version that was sent.
Every stage change is written to an immutable history trail.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/applications` | Create |
| GET | `/api/applications` | List, with search and filters |
| GET | `/api/applications/{id}` | Fetch one |
| PUT | `/api/applications/{id}` | Update |
| DELETE | `/api/applications/{id}` | Delete |
| PATCH | `/api/applications/{id}/stage` | Move stage |
| GET | `/api/applications/{id}/history` | Stage-change history |
| POST | `/api/applications/bulk/stage` | Move many at once |
| POST | `/api/applications/bulk/delete` | Delete many at once |
| GET | `/api/applications/export` | Download CSV |
| POST | `/api/applications/import` | Upload CSV |

---

## 10. Backup and restore

Creates a zip of `data/`, optionally including `exports/`. Restore validates the
archive before replacing anything.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/backup/create` | Create an archive |
| GET | `/api/backup/list` | List archives |
| GET | `/api/backup/download/{filename}` | Download one |
| POST | `/api/backup/restore` | Restore from an upload |
| POST | `/api/backup/restore/{filename}` | Restore an archive already on disk |
| DELETE | `/api/backup/{filename}` | Delete an archive |

Shell equivalent with rotation: `scripts/backup-cvlab.sh` —
see [BACKUP_SCRIPTS_README.md](../scripts/BACKUP_SCRIPTS_README.md).

---

## 11. Housekeeping

Exports accumulate. The cleanup service removes old ones on a configurable
policy, with a dry-run mode so you can see what would go first.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/export/cleanup?dry_run=true` | Preview or perform cleanup |
| GET/PUT | `/api/export/cleanup/config` | Retention policy |
| GET | `/api/export/cleanup/stats` | Counts and disk usage |

---

## 12. Command-line tools

| Script | Purpose |
| --- | --- |
| `scripts/export.sh` | Export Markdown in `cv/` to PDF/DOCX/TXT. `export.sh all` or `export.sh <basename> [pdf\|docx\|txt]`. **zsh** |
| `scripts/normalize_txt.sh` | Normalise plain-text output for ATS |
| `scripts/make-reference.sh` | Regenerate `scripts/reference.docx` |
| `scripts/tune_docx.py` | Adjust styles inside a DOCX reference document |
| `scripts/backup-cvlab.sh` | Backup with rotation, via the API |
| `scripts/validate-docker.sh` | Validate the Docker setup before building |
| `scripts/venv.sh`, `scripts/uv.sh` | Host-side Python environment helpers (install `backend/requirements.txt`, useful for IDE interpreter resolution) |

---

## 13. Privacy and security

- **Local-first.** All state is files on your disk. There is no server component
  beyond the one you run, and no telemetry.
- **Outbound traffic** happens only for a configured AI provider, or a job-advert
  URL you explicitly ask it to fetch.
- **Keys encrypted at rest** with Fernet; the key file `data/config/.llm_key` is
  mode 0600 and gitignored.
- **Consent gate** before the first remote AI call, with an append-only log.
- **Kill switch** — `POST /api/llm/disable` stops all AI paths.
- **Rate limiting** on LLM endpoints guards against runaway spend.
- **CORS** is restricted to localhost origins.
- **`.gitignore`** excludes `.env`, `data/`, `cv/`, `exports/`, IDE state and
  agent scratch directories.

---

## 14. Full API index

Interactive docs are served at **<http://localhost:8002/docs>** (Swagger) and
**`/redoc`** while the container is running.

| Prefix | Router |
| --- | --- |
| `/api/cvs` | CVs and sections |
| `/api/export` | Export, history, cleanup |
| `/api/llm` | AI features, config, consent |
| `/api/typography` | Typography and templates |
| `/api/job-suitability` | Suitability analysis |
| `/api/applications` | Application tracker |
| `/api/backup` | Backup and restore |
| `/health` | Toolchain health check |
| `/api` | API root |

---

## 15. Known limits

- **Single user, no authentication.** Bind it to localhost only. It is not
  designed to be exposed to a network.
- **Container-only backend.** Several services resolve `/app/...` paths
  literally, so running uvicorn on the host without those paths will not work.
- **Frontend is baked into the image.** Frontend changes need
  `docker-compose up -d --build`.
- **No concurrent-write protection.** JSON files are read-modify-written; two
  browser tabs editing the same CV can lose an edit.
- **PDF fonts are the container's.** `templates/cv.latex` selects Liberation
  Sans / Liberation Mono. Naming a font that is not installed in the image will
  fail the XeLaTeX run.

---

## 16. Known test failures

As of 2026-09-08 the backend suite runs **958 passed / 43 failed / 3 skipped**
(~4 min) and the frontend suite is **113 passed / 0 failed**. The failures are
pre-existing and cluster into six groups. None of them block building, running
or exporting — all of those were verified end to end.

| Group | Count | Cause |
| --- | --- | --- |
| `test_container_properties` | 8 | Expect a live Docker container and specific host paths; they cannot pass inside the test container itself |
| AI-parser suites (`test_ai_parser_*`, `test_ai_parsing_*`, `test_entity_extraction_*`, `test_section_identification_*`, `test_metrics_gap_*`) | ~19 | Test mocks return plain `Mock`s where the code awaits, producing `'coroutine' object is not subscriptable`. The production code in `ai_parser.py` awaits correctly — this is a test-harness defect, not a runtime one |
| Markdown import (`test_import_service`, `test_import_error_handling_*`, `test_markdown_import_round_trip_*`, `test_job_description_extraction_*`, `test_template_content_preservation_*`, `test_data_validation_*`) | ~10 | Assertions have drifted from the parser's current behaviour |
| `test_bedrock_integration` | 4 | Require real AWS credentials with Bedrock access |
| `test_performance_*` | 2 | Wall-clock thresholds; sensitive to how much CPU the Docker VM has |
| `test_backup_service::test_list_backups` | 1 | Backup filenames carry second-resolution timestamps, so two backups created in the same second collide and the first is silently overwritten. Worth fixing in `backup_service.py` — it is a real (if narrow) data-loss path |

The exact set of AI-parser and import failures shifts between runs because these
are Hypothesis property tests drawing random examples; the total stays around 43.
