# singleangle

> Ensure AI starts at the blue ocean of ideas.

A [Claude Code](https://claude.com/claude-code) skill that researches a topic across Reddit, X, and the web — then extracts the **single strongest angle** for one deep long-form post, plus the hooks, pro/con arguments, stats, quotes, story moments, and closing lines you need to write it.

It's for when you want to write a LinkedIn longform, a Substack essay, an X article, or a newsletter piece on a specific topic — and you want the AI to do the hard part: find the non-obvious cut that most people in your space aren't making yet.

## What makes it different

Most AI content tools pick the first plausible angle and run with it. singleangle doesn't. It runs your topic through **six different reasoning lenses** in parallel, generating one candidate angle per lens:

- **Reframe** — What's the popular interpretation missing? What's the hidden mechanism?
- **Tension** — Where's the real disagreement among credible operators?
- **Hidden cost** — What downstream price is nobody pricing in?
- **Leading indicator** — What's this trend a canary for?
- **Category error** — Is the debate asking the wrong question?
- **Counter-case** — What named company breaks the consensus?

Each candidate is then scored against four tests (stop-scroll, compression, non-consensus, relevance). The winner can come from any lens — the lenses exist to prevent blind spots, not force a shape. You learn which lens produced the winning angle, and which runner-ups are worth a second post.

## Installation

**Requires:** Claude Code, Python 3.8+. No Python packages to install — the skill uses stdlib only.

```bash
# 1. Clone into your Claude Code skills directory
git clone https://github.com/searchbrat/singleangle ~/.claude/skills/singleangle

# 2. Configure your API keys
mkdir -p ~/.config/singleangle
cat > ~/.config/singleangle/.env <<'EOF'
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...
EOF

# 3. Verify
python3 ~/.claude/skills/singleangle/scripts/singleangle-research.py --check
```

You should see both keys resolve with ✅.

### Where to get keys

- **OpenAI** — [platform.openai.com](https://platform.openai.com) → used for Reddit search via the Responses API
- **xAI** — [x.ai](https://x.ai) → used for X (Twitter) search via Live Search
- **Perplexity** (optional, for web) — [perplexity.ai](https://www.perplexity.ai)

Both OpenAI and xAI keys are recommended for full coverage. If either is missing, the skill falls back to WebSearch-only mode — still usable, but Reddit/X engagement data will be thin.

## Usage

In Claude Code, just type:

```
/singleangle <topic>
```

The skill will:

1. **Ask for audience context** — optional. You can paste a description, point to a file, or skip. Providing context dramatically sharpens the winning angle.
2. **Research the topic** (2–5 minutes) — Reddit discussions, X posts, web articles, engagement signals.
3. **Run the six-lens angle generator** — one candidate per lens, scored against the four tests.
4. **Assemble the single-post ingredient pack** — the winning angle, 3 hooks, pro/con arguments, key stats with sources, quotable lines from named operators, an anchor story moment, and 3 closing-line variants.

Output is saved to `~/.local/share/singleangle/out/<topic-slug>.md` and presented inline for review.

## Output structure

Every singleangle output follows the same shape:

- **The Angle** — one-paragraph POV, readable aloud, non-hedged
- **Why this angle for this audience** — maps to specific pain points
- **Hooks (×3)** — contrast / curiosity gap / surprising number
- **Pro arguments (×2–3)** — each backed by a named source
- **Counter arguments (×2–3)** — objections pre-empted with rebuttals
- **Key stats** — 5–8 hard numbers with citations
- **Notable quotes** — 3–5 quotable lines, including at least one steel-man
- **Story moment** — one anchor anecdote, 150–250 words, named actors, clear turn
- **Closing lines (×3)** — non-hedged final takes, ≤30 words each
- **Sources** — URLs + publication dates for verification

Write the post from these ingredients — or hand them to another tool / writer. Either way, you start with a sharper angle than you would have on your own.

## Philosophy

Most AI content fails the *non-consensus test*: it says what the reader already half-believes. singleangle rejects those angles explicitly — if your cut is "X is broken" or "You should do Y," it regenerates. The goal is to surface the thing only a practitioner would notice, and hand you the raw material to defend it.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built by [Kieran Flanagan](https://www.kieranflanagan.io/). Issues and PRs welcome.
