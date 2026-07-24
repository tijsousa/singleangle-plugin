---
name: singleangle
description: "Research a topic and produce the ingredients for ONE deep post on it — a single sharp angle, hooks, pro/con arguments, key stats, notable quotes, a story moment, and closing lines. Optionally pair with audience context to sharpen the angle for a specific ICP. Use when the user wants a single deep post on one topic — a LinkedIn longform, a Substack essay, an X article, or a newsletter piece. Also trigger when the user mentions 'write a deep post about', 'give me a single-post brief on', 'what's the angle on X', 'expand this into a post', or provides a tweet/article they want to riff off."
---

# singleangle

## Overview

This skill researches a single topic, evaluates multiple candidate angles across six reasoning lenses, picks the sharpest cut for a specific audience, then assembles the raw material needed to write one deep, structured post.

singleangle is a **standalone, self-contained skill**. It includes its own research engine and bundled library — no dependencies on other skills.

Use singleangle when the output is a single long-form piece (LinkedIn longform, Substack essay, X article, newsletter).

## When to Use This Skill

Use when:
- User wants a single deep post on one topic, not multiple content ideas
- User has a source (tweet, article, observation) they want to expand into a unified take
- User wants the strongest angle on a specific topic for their audience

Do NOT use when:
- User wants multiple independent content pieces from one topic — singleangle produces ingredients for ONE unified piece
- User just wants raw research or a market overview with no content framing
- User wants a broad multi-source investigation without angle selection

## Setup (one-time, for first-time users)

This skill is self-contained — everything it needs lives inside `~/.claude/skills/singleangle/`. To unlock the full research engine, the user needs three API keys.

### 1. Install the skill

Drop the `singleangle/` folder into `~/.claude/skills/`. That's it — Claude Code picks it up automatically.

### 2. Configure API keys

Create `~/.config/singleangle/.env` with the following:

```bash
OPENAI_API_KEY=sk-...       # For Reddit search via OpenAI Responses API
XAI_API_KEY=xai-...         # For X (Twitter) search via xAI Live Search
```

Optional third key for deeper web synthesis:
```bash
PERPLEXITY_API_KEY=pplx-... # For web research via Perplexity
```

### 3. Verify setup

```bash
python3 ~/.claude/skills/singleangle/scripts/singleangle-research.py --check
```

Expected output: "OpenAI key: ✓", "xAI key: ✓". If a key is missing, the skill falls back to WebSearch-only mode — still usable, but Reddit and X coverage will be thinner.

### Notes

- **Where to get keys:** OpenAI (platform.openai.com), xAI (x.ai), Perplexity (perplexity.ai). All three have free or low-cost tiers sufficient for single-topic research.
- **No audience profile is installed with the skill.** You can optionally provide audience context each time you invoke singleangle — see Inputs below.

## Inputs Required

### 1. Topic (Required)

The topic to cover. Can be:
- A concept: *"TokenMaxing for companies"*
- A trend: *"Controller models for AI agents"*
- A question: *"Should marketing teams mandate AI tools or open access?"*
- A seed tweet/article URL — singleangle will treat it as the trigger source

### 2. Audience Context (Recommended, not required)

Angle selection sharpens dramatically when the skill knows who the post is for. You can provide audience context in any of three ways — pick whichever fits:

1. **Point to an audience profile file** — any format, any location. The skill will read whatever you provide. Useful if you've built a detailed ICP doc.
2. **Describe the audience in a sentence or two** — e.g. *"Senior B2B SaaS marketing leaders, allergic to hype, want practitioner specifics from named operators."*
3. **Skip it** — the skill will run on the topic alone, flag in the output that no audience context was provided, and produce more generic angles.

What helps the scoring most, in priority order:
- Pain points the audience is actively living with
- Vocabulary they use — and the terms they reject as outsider-speak
- Specific decisions they're currently trying to make
- Proof types that build or destroy credibility for them

### 3. Source Trigger (Optional)

A specific tweet, article, data point, or observation the user wants the post to riff off. Include in the output header for traceability.

## Workflow

### Step 1: Gather Inputs

Ask for (if not already provided):
1. What topic do you want to cover?
2. Path to the audience profile?
3. Any specific source trigger (tweet, article) you want the post to riff off? (optional)

### Step 2: Read the Audience Profile

Read and internalise the profile. Pay close attention to:
- Pain points (P1, P2, P3) — these determine which angle will *land*
- Vocabulary library (words they use vs. vendor-speak they reject)
- Anti-triggers (patterns that destroy credibility on sight)
- Proof types ranked
- Situational framings

Angle selection in Step 5 must reference these directly.

### Step 3: Run the Research Engine

```bash
python3 ~/.claude/skills/singleangle/scripts/singleangle-research.py "<topic>" --emit=compact [--deep] [--days=N]
```

The engine will:
- Search Reddit for relevant discussions (threads, comments, debates) via OpenAI Responses API
- Search X for relevant posts (takes, hot takes, data shares, stories) via xAI Live Search
- Search LinkedIn for public posts & articles (B2B practitioner takes) via OpenAI web_search, constrained to `linkedin.com/posts` and `linkedin.com/pulse` — reuses the OpenAI key, on by default (disable with `--no-linkedin`)
- Score and deduplicate results by engagement signal
- Save structured research to `~/.local/share/singleangle/out/research.md`

Typically takes 2-5 minutes. If API keys are missing, the script automatically falls back to WebSearch-only mode.

**LinkedIn caveat (important):** LinkedIn has no public search API and blocks scraping, so the LinkedIn lane returns only PUBLIC, search-indexed posts/articles and does NOT include engagement metrics (reactions/comments are behind auth). Treat LinkedIn items as qualitative signal — sharp takes and vocabulary from named operators — not as engagement-ranked data.

### Step 4: Supplement with WebSearch

Use WebSearch (or perplexity_search) for 5-10 additional sources:
- Blog posts, articles, reports, op-eds
- EXCLUDE reddit.com, x.com, and linkedin.com (already covered)
- Focus on the last 30-60 days unless the topic is evergreen
- Prioritise named operators, named companies, hard numbers

### Step 5: Multi-Lens Angle Generation (THE CRITICAL STEP)

**Do not predetermine the angle shape.** Different topics have different sharpest cuts. Your job is to evaluate multiple candidate angles and pick the one that scores highest — not to default to any one pattern.

**Run all six lenses.** Each lens is a different question to ask of the topic + audience combination. Generate one candidate angle per lens.

#### The Six Lenses

1. **Reframe lens** — *What's the popular interpretation missing? What's the hidden mechanism beneath the visible phenomenon?*
   Template: *"[Topic] isn't [popular interpretation] — it's [hidden mechanism]."*

2. **Tension lens** — *Where is there real disagreement among credible operators? What decision is the audience stuck between?*
   Template: *"Operators are split between [Pole A] and [Pole B]. Most [ICP] don't know where they should be."*

3. **Hidden cost lens** — *What downstream consequence is nobody pricing in? What second-order effect will leadership notice in 18 months?*
   Template: *"Everyone's focused on [visible cost]. The real cost is [hidden consequence]."*

4. **Leading indicator lens** — *What's this trend a canary for? What bigger shift does it signal?*
   Template: *"[Topic] isn't the story. It's the first visible sign of [bigger shift]."*

5. **Category error lens** — *Is the audience debating the wrong question? Is there a premise everyone's accepting that shouldn't be?*
   Template: *"Everyone's asking [consensus question]. The real question is [reframed question]."*

6. **Counter-case lens** — *Is there a named, credible company breaking the consensus in an instructive way?*
   Template: *"While everyone does X, [Company] is doing Y — and it's working. Here's what that proves."*

#### Score Each Candidate

Apply four tests to each of the six candidates:

- **Stop-scroll test** — Would a knowledgeable audience member stop scrolling on this headline?
- **Compression test** — Can it be stated in ONE sentence? (Blob angles fail here — reject them.)
- **Non-consensus test** — Would this cause pushback at a dinner of peers, or unanimous nods? Unanimous nods = too obvious, reject.
- **Relevance test** — Does it attach to a decision or pain the audience is *actively* living with? Cross-reference the audience profile's P1/P2/P3.

#### Pick the Winner

Winners can come from ANY lens. Record which lens produced the winning angle — this helps the user understand why this cut, not another.

#### Reject-on-Sight Red Flags

If a candidate angle matches any of these, discard and regenerate:

- *"X is broken"* / *"X doesn't work"* / *"Here's what's wrong with X"* — these are verdicts, not insights
- *"You should [obvious action]"* — prescription without a fresh lens
- Anything that restates what the audience already half-believes
- Blob angles spanning multiple ideas without a single crisp POV

#### Green-Light Patterns

These usually score well:

- *"[Topic] isn't what you think — it's [reframe]"*
- *"You're stuck between X and Y — here's how to decide"*
- *"Everyone's watching the wrong metric"*
- *"[Named company] quietly did the opposite — and it worked"*

### Step 6: Assemble the Single-Post Ingredient Pack

Using the winning angle, produce these sections in order:

#### 1. Header
- Topic
- Audience (name from profile)
- Source trigger (if provided)
- Research period
- **Winning angle lens** (which of the six produced it)

#### 2. The Angle
One-paragraph statement of the POV. Readable aloud. Non-hedged. Must survive the compression test.

#### 3. Why this angle for this audience
2-3 sentences mapping the angle to specific pain points (P1/P2/P3) from the profile. This proves the angle was chosen deliberately, not accidentally.

#### 4. Hooks (3 variants)
- **Contrast hook** — two facts in tension
- **Curiosity-gap hook** — open loop the reader needs to close
- **Surprising-number hook** — number first, then context

Each hook ≤ 50 words. Every hook must use active verbs and the audience's vocabulary.

#### 5. Pro arguments (2-3)
Bullets supporting the angle. Each must include:
- A concrete claim
- A named source (company, stat, or quote)
- A connection back to the angle

#### 6. Counter arguments (2-3)
Objections a smart reader will raise. Each includes:
- The objection stated fairly (not strawmanned)
- A direct rebuttal with evidence
- Back-to-angle connection

This pre-empts pushback and makes the final post defensible.

#### 7. Key stats (5-8)
Hard numbers with sources. Prefer numbers that directly support the angle. Format: **[number]** — [what it measures] *(source)*.

#### 8. Notable quotes (3-5)
Quotable lines from named operators (CEOs, practitioners, researchers). Include at least one **steel-man quote** from the opposing view — this gives the writer cover for acknowledging the other side.

#### 9. Story moment (THE ANCHOR)
ONE anchor anecdote, 150-250 words. Must have:
- Named actors and specific details
- A turn (something surprising, a reveal, a breaking point)
- A clear moral that maps to the angle
- NO montage — one moment, not a highlight reel

The story moment is the most important section after the angle itself. If a reader only reads the hook and the story, the post should still land.

#### 10. Closing lines (3 variants)
Non-hedged final takes. Each ≤ 30 words. No "it will be interesting to see" hedging.

#### 11. Sources
List URLs + publication dates for writer verification.

### Step 7: Apply Voice & Style Rules

Check the output against these rules before saving:

- Active verbs only. No hedging (maybe, perhaps, could potentially, arguably).
- Maximum 22 words per sentence (aim for 15).
- **Check against the audience profile's anti-triggers list.** One "leverage," "unlock," "synergy," or "game-changing" destroys credibility. Strip them.
- Use in-group terms the audience uses without explanation. Do not define words they already know.
- Every stat must have a named source inline.
- Every quote must have named attribution unless anonymity itself is the point.
- Numbers should be specific: "$150K" not "hundreds of thousands."

### Step 8: Output

Save to `~/.local/share/singleangle/out/<topic-slug>.md` with the section structure above.

Present to the user with a brief summary:
- **Which lens produced the winning angle** and why it scored highest
- **Runner-up angles** that might be worth a second post (mention the lens each came from)
- Any notable gaps in the research (e.g., "no strong counter-case emerged — post will lean on the reframe")

## Output Format

```markdown
# singleangle: [Topic]

**Topic:** [Topic]
**Audience:** [Audience name from profile]
**Source trigger:** [If provided]
**Research period:** [Date range]
**Winning lens:** [Which of the six]

---

## The Angle

[One paragraph, non-hedged]

## Why this angle for this audience

[2-3 sentences mapping to P1/P2/P3]

---

## Hooks (pick one)

**A. Contrast**
> [Hook text]

**B. Curiosity gap**
> [Hook text]

**C. Surprising number**
> [Hook text]

---

## Pro arguments

**1. [Sub-claim title]**
[Bullet with named source]

**2. [Sub-claim title]**
[Bullet with named source]

**3. [Sub-claim title]** (optional)
[Bullet with named source]

---

## Counter arguments

**Objection: "[Stated fairly]"**
Rebuttal: [Direct rebuttal with evidence]

[Repeat for 2-3 objections]

---

## Key stats

- **[Number]** — [what it measures] *(source)*
- [5-8 total]

---

## Notable quotes

> "[Quote]"
> — **[Name, role, company]**

[3-5 quotes, at least one steel-man]

---

## Story moment

[150-250 words, one specific anecdote, named actors, clear moral]

---

## Closing lines (pick one)

**A.** [Non-hedged take, ≤30 words]
**B.** [Variant]
**C.** [Variant]

---

## Sources

- [Publication, title, URL, date]
```

## Common Failure Modes to Avoid

1. **Predetermining the angle shape.** Do not default to tension, reframe, or any pattern. Run all six lenses every time. Let the topic + audience determine which wins.

2. **Picking an obvious verdict.** If your angle is "X is bad" or "X doesn't work," the audience already half-believes it. Reject and regenerate from a different lens.

3. **Generic framing.** "Companies need to measure outcomes" is topic-less. The angle must be specific to THIS topic's mechanism — something you couldn't copy-paste into a different topic.

4. **Skipping the audience profile read.** Angle selection without audience context produces content that sounds plausibly-smart but doesn't land on the specific decisions this audience is making.

5. **Using hype vocabulary.** Check against the profile's anti-trigger list before saving. One vendor-speak phrase and credibility is gone.

6. **Padding the story moment.** The anchor anecdote should be one specific moment, not a montage of examples. 150-250 words max. If you need more, the story isn't tight enough.

7. **Writing for an abstract audience.** Don't write for "marketers" — write for the specific ICP described in the profile. The vocabulary, the situational framings, the pain points all come from there.

## Edge Cases

- **Very niche topic, thin research:** Note to the user and offer to broaden (*"TokenMaxing for companies"* vs *"TokenMaxing in marketing teams specifically"*).
- **No API keys:** Engine falls back to WebSearch-only. Flag this — results will be less engagement-weighted.
- **No audience context provided:** Proceed, but flag in the output header that the angle was generated against the topic alone. Expect more generic framing and note this in the summary.
- **Topic too broad:** *"AI for marketing"* is too broad. Ask for a specific cut.
- **All lenses produce weak angles:** The topic may be too consensus-baked. Offer to pair it with a sibling topic, or reframe via a specific source trigger (tweet/article) that gives a sharper entry point.
- **Multiple strong candidates tie:** Present the top 2 to the user and let them choose. Capture the losing candidate in the output as "alternate angle — worth a second post."
