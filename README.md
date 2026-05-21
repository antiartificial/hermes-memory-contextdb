# hermes-memory-contextdb

**ContextDB Memory Provider for Hermes Agent**

This plugin turns [ContextDB](https://github.com/antiartificial/contextdb) into a first-class epistemic memory backend for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Instead of plain vector recall, you get credibility tracking, source reputation, narrative explanations, conflict awareness, and realistic memory decay — all exposed through Hermes' clean `MemoryProvider` interface.

## Features

- **Epistemic memory** — Credibility scores, source tracking, and confidence calibration
- **Narrative retrieval** — `contextdb_explain` tool returns evidence chains and reasoning
- **Smart prefetch** — Credibility-biased context injection before every turn
- **Minimal tool surface** — Only two high-value tools (`contextdb_search` + `contextdb_explain`)
- **CLI support** — `hermes contextdb status`, `search`, `explain`, `init`
- **Postgres + pgvector ready** — Works with your existing `hermes_contextdb` database
- **Graceful fallback** — Falls back to embedded BadgerDB mode when no database is configured

## Installation

```bash
mkdir -p ~/.hermes/plugins/contextdb
cd ~/.hermes/plugins/contextdb
git clone https://github.com/antiartificial/hermes-memory-contextdb.git .
```

Or install directly into your Hermes plugins directory.

## Configuration

### 1. Environment Variables (recommended)

Add to `~/.hermes/.env`:

```bash
CONTEXTDB_HOST=localhost
CONTEXTDB_PORT=5432
CONTEXTDB_USER=hermes
CONTEXTDB_PASSWORD=your_password
CONTEXTDB_DATABASE=hermes_contextdb
```

### 2. Hermes Config

In `~/.hermes/config.yaml`:

```yaml
memory:
  provider: contextdb
  contextdb:
    namespace: "hermes-agent"
    mode: "agent_memory"
```

## Usage

### CLI Commands

```bash
hermes contextdb status          # Health check + connection info
hermes contextdb init            # Verify namespace
hermes contextdb search "topic"
hermes contextdb explain "topic" # Narrative explanation with sources
```

### In Agent Conversations

The provider automatically injects high-quality context on every turn. You can also explicitly call:

- `contextdb_search`
- `contextdb_explain`

## Related Projects

- [ContextDB](https://github.com/antiartificial/contextdb) — The epistemic graph-vector database
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — The agent framework
- Integration Skill: `contextdb-hermes-memory-integration`

## License

MIT

## Contributing

Contributions are welcome. Please open an issue first to discuss major changes.