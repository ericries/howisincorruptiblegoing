# Drafting: how to write for this site without sounding like a machine

Eric, 2026-11-01, on an entry summary: *"careful about AI-ese, this reads like
LLM speak."* He was right, and the sentence he quoted is the worked example
below.

This page is the standing guidance. `scripts/summary_tics.py` enforces the part
a machine can be sure about and runs in the pre-commit hook on changed entries.

## The measurement that prompted it

CLAUDE.md has said summaries are *"concise, 1-2 sentences"* since the site was
built. Median summary length, by month:

| 2026-01 | 2026-04 | 2026-05 | 2026-08 | 2026-10 | 2026-11 |
|---|---|---|---|---|---|
| 20 words | 26 | 38 | 57 | 65 | **102** |

A five-fold drift nobody chose. No summary was unreasonable beside the one
before it, which is the whole mechanism: a rule written in prose gives you
nothing to measure against, so the baseline becomes *yesterday's output*.
`summary_tics.py --trend` reprints that table on demand.

## The worked example

The flagged summary, at 127 words:

> Balayan heads Maure Inmobiliaria, analyses the Buenos Aires property market
> and has a standing books slot on Neura, where she recommended Incorruptible
> last Thursday. Her written summary is unusually faithful for a second-hand
> account: financial gravity as a silent force that grows with investors and
> short-term return pressure, the diagnosis located in governance and legal
> structure rather than in human greed, and Costco and Patagonia as the
> structural answers. **Her own verdict is that trust is the most underrated
> asset in business.** The line she opens on — that doing the right thing
> carries tangible costs and intangible benefits, so ROI logic pushes the other
> way — **is Eric's own argument rendered in Spanish, not her coinage**; he puts
> it almost identically on the Yaniv Bernstein podcast.

Four faults, in order of how much they cost:

1. **Sentence 3 restates the blockquote**, which is printed two inches below it.
   The summary introduces the quote; it never previews it.
2. **Sentence 4 narrates my own research.** Checking that she had not coined
   Eric's argument was the right thing to do — that is
   `feedback_third_party_concept_attribution` working. Publishing the check is
   not. Verification belongs in my head and in `source_urls`, never in prose.
3. **"is Eric's own argument … not her coinage"** — the corrective antithesis,
   the most recognisable LLM tell there is.
4. **"unusually faithful for a second-hand account"** — editorialising a grade
   onto someone's work. State what she wrote; the reader grades it.

At 53 words:

> Balayan runs Maure Inmobiliaria in Buenos Aires and has a standing books slot
> on Neura, where she recommended Incorruptible on air last Thursday. Her
> written summary tracks the book closely: financial gravity growing with
> investors and short-term return pressure, governance and legal structure as
> what fixes it, Costco and Patagonia as the examples.

Nothing factual was lost. The Yaniv Bernstein check still happened.

## Rules

### Hard — `summary_tics.py` fails the commit

- **2 sentences, 60 words.** CLAUDE.md's rule, with numbers attached so it can
  be checked. If it will not fit, you are summarising the source instead of
  introducing it.
- **No corrective antithesis** — *"not X, but Y"*, *"isn't X — it's Y"*,
  *"…, not her coinage."* Say the half you mean and delete the other.
  [Colin Gorrie][gorrie] names this, parallelism and the tricolon as the three
  devices LLMs reach for: *"what the LLM lacks is not technical ability, but
  taste"* — they are good devices, applied without discrimination.
- **No summary that quotes the blockquote back.** Six shared words trips it.
- **No blacklist words**: delve, leverage, tapestry, testament, realm, beacon,
  robust, pivotal, seamless, multifaceted, underscore, cutting-edge,
  game-changer, transformative, unlock, unleash, myriad, plethora, showcase,
  "landscape of". Words inside quotation marks are exempt — someone else may
  well have said "testament", and reporting it is not writing it.

### Soft — reported, your judgement

- **More than one em dash.** One sharp aside is good writing; a second usually
  means a sentence wants splitting. The tell is density, not presence.
- **Tricolons.** Fine once. A tell when every summary has one — 27% of this
  site's do.
- **Narrated candor**: *"the honest answer"*, *"worth saying plainly"*,
  *"I would rather flag this than…"*. Moral framing of my own process. State
  the fact and let the reader decide whether it was honest. (This one is mine
  rather than the literature's; [Bronsdon][bronsdon] files it under misapplied
  moral adjectives.)

### Not mechanised — read for these

- **The grade.** "unusually faithful", "remarkably specific", "precisely the
  argument". Report what someone said, not how well they said it.
- **Significance inflation.** A 16-reaction post is a 16-reaction post.
- **Setup/reversal as a substitute for a claim.** *"That floor exists because I
  trimmed the row three times. It does not bind Eric."* Two beats where one
  sentence of fact would do. I do this constantly in reports; it reads as
  cadence standing in for content.
- **Uniform rhythm.** Three sentences of the same length in a row is the
  [rhythm tell][oliviacal]. Vary deliberately.

## What this does not apply to

Blockquotes, titles and `attribution_title` are **source text or close to it**
and are governed by the quote rules in CLAUDE.md, not by this page. Never edit a
quote for style. `summary_tics.py` only ever reads `summary`.

## Sources

- [Colin Gorrie, *Why ChatGPT writes like that*][gorrie] — parallelism,
  antithesis, tricolon, and why taste rather than capability is what is missing.
- [finngi/tics][tics] — 27 deterministic rules in five categories (contrast,
  rhetoric, vocabulary, chatbot residue, formatting). Rust, so not installed
  here; `summary_tics.py` implements the subset that fits an entry summary.
- [conorbronsdon/avoid-ai-writing][bronsdon] — tiered severity, narrated
  candor, invented contrasts, hedge stacking, em-dash density.
- [Olivia Cal, *AI writing tells*][oliviacal] — the rhythm tell and the 2026
  word blacklist.

[gorrie]: https://www.deadlanguagesociety.com/p/rhetorical-analysis-ai
[tics]: https://github.com/finngi/tics
[bronsdon]: https://github.com/conorbronsdon/avoid-ai-writing/blob/main/SKILL.md
[oliviacal]: https://www.oliviacal.com/post/ai-writing-tells
