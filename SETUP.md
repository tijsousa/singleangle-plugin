# singleangle plugin — setup

This plugin bundles the **singleangle** skill (with the added **LinkedIn** source)
so it can be installed via a Claude Code marketplace and used in Cowork.

## What's inside
- `plugins/singleangle/skills/singleangle/` — the full skill + research engine
- LinkedIn source is **on by default** (reuses your OpenAI key); disable per-run with `--no-linkedin`

## API keys — REQUIRED for full coverage

The engine reads keys from **environment variables first**, then from
`~/.config/singleangle/.env`. In Cowork (or any cloud/sandbox), the local
`.env` does NOT travel with you — so set the keys as environment variables/secrets
in that environment:

| Env var | Powers | Get it at | Notes |
|---------|--------|-----------|-------|
| `OPENAI_API_KEY` | Reddit **and** LinkedIn | platform.openai.com | required for the two strongest lanes |
| `XAI_API_KEY` | X / Twitter | console.x.ai | key must have **credits** on the xAI team, or Live Search returns permission-denied |

Without any keys, the skill falls back to WebSearch-only mode (thinner, no engagement signal).

## Install locally (this machine)

```bash
# In an interactive `claude` session:
/plugin marketplace add ~/Claude\ Code/singleangle-plugin
/plugin install singleangle@singleangle-marketplace
```

## Use in Cowork
1. Bring this plugin folder (or the `.zip`) into the Cowork environment.
2. Add it as a marketplace and install it (same commands as above), OR install
   via the Cowork plugin management flow.
3. Set `OPENAI_API_KEY` and `XAI_API_KEY` as environment variables/secrets in Cowork.
4. Verify:
   ```bash
   python3 <plugin>/skills/singleangle/scripts/singleangle-research.py --check
   ```

## LinkedIn caveat
LinkedIn has no public search API and blocks scraping. The LinkedIn lane returns
only PUBLIC, search-indexed posts/articles (`/posts/`, `/pulse/`) and does not
include engagement metrics. Treat it as qualitative signal — sharp takes and
practitioner vocabulary — not engagement-ranked data.
