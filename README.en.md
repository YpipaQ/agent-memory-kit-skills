# agent-memory-kit — Workspace Memory System (Skill + Toolkit)

A system for directories where you work with an AI assistant over the long term:
**hot/cold memory separation, six-zone filing, volatile numbers handed to scripts,
finalized content into a handbook, and multi-agent testing via a protocol**.
It ships both as a DSH skill (`SKILL.md`) and as a set of directly runnable scripts.

## Why this exists

Chat history is not memory: as soon as a session is compressed or you switch windows,
the context is gone. This kit splits "what should be remembered long-term" into three
layers on disk, so any new session can rebuild the full context just by reading the
navigation table in `AGENTS.md`; it also makes **who wrote what** auditable when two
agents collaborate, instead of relying on blind trust.

## Directory

```
agent-memory-kit/
├── SKILL.md                 # Skill entry: rule summary + navigation + workflow (< 150 lines)
├── references/              # Details: memory system / exchange protocol / privacy & secrets / tools & scripts / review notes
├── scripts/
│   ├── _common.py           # Root resolution, config reading, reporter (shared)
│   ├── memory_doctor.py      # Health check: dead links / index / size / TL;DR-first / secrets / protocol / naming
│   ├── state_snapshot.py     # Generates STATE.md (single source of volatile numbers)
│   ├── new_exchange.sh       # Create a controlled exchange test directory
│   ├── bootstrap.sh          # Lay down the system in a new workspace
│   └── collectors/           # Optional example collectors (add/remove per your project, e.g. a market DB / a service's routes)
├── templates/               # Six-zone READMEs, AGENTS.md, settings.md, exchange templates, thin shells
└── VERSION
```

## Install / Enable (depends on your harness)

The skill is **harness-agnostic**: plain Markdown + scripts that take effect as soon as they
sit in any agent environment that reads `SKILL.md`. Pick whichever fits:

1. **Drop it in (simplest)**: clone or unpack this repo, then place the whole `agent-memory-kit/`
   directory into your skills folder — for example `.agent/skills/agent-memory-kit/` (most agent
   frameworks scan this path). Restart the session; **no npm needed**.
2. **npm**: `npm install agent-memory-kit`, then symlink or copy `node_modules/agent-memory-kit`
   into your harness's skills folder.
3. **Symlink (DSH, etc.)**: keep the skill body in one place and symlink it into the harness's
   skills directory (e.g. `~/.dsh/skills/agent-memory-kit`); adjust the paths to your environment,
   and replace the skill-directory prefix in the commands below with your actual one.

How to enable it depends on the runtime (e.g. in DSH, tick the corresponding slug in session skills).

## Usage

In any workspace:

```bash
python3 ~/.dsh/skills/agent-memory-kit/scripts/memory_doctor.py --root .
python3 ~/.dsh/skills/agent-memory-kit/scripts/state_snapshot.py --root .
```

Starting a new workspace:

```bash
bash ~/.dsh/skills/agent-memory-kit/scripts/bootstrap.sh --root /path/to/new-ws --preset <your-project> --name my-workspace
```

After installation, the workspace will contain
`scratch/memory-tooling/{memory_doctor.py,state_snapshot.py,new_exchange.sh}` — these are
**thin shells** that forward to the implementations in this skill, so there is only one
copy of the logic (don't edit logic inside the shells).

## Design tradeoffs

- **The skill knows nothing about your project**: all project differences live in
  `<workspace>/.memory-kit.toml` (thresholds, secret exemptions, STATE collectors).
- **Strict by default**: secret-like strings are ❌ by default; exemptions must be written
  explicitly in config.
- **Read-only**: collectors never modify what they collect; probes with side effects are
  blocked first.
- **Thin shell, not a copy**: the workspace keeps command entry points, but the
  implementation lives in one place; the skill body is also single-source (in the repo),
  changes take effect immediately.
- **The check catches form, not facts**: facts must be verified by real runs and
  cross-checked via `exchange/` — this is written into the skill's boundaries.

## Privacy

This directory **contains no credentials**: all templates are placeholders. Self-check:

```bash
python3 scripts/memory_doctor.py --root . --only secrets
```
