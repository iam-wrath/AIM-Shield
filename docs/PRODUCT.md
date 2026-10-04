# Product context: Attack Lab

register: product

## What it is
The Attack Lab is the single screen of Aim Shield, a safety layer beside the SecureAI Guard (hackathon Challenge 3). It runs one message through two systems side by side: **Guard only** (what a typical app does today) and **Guard + Aim Shield** (our layers). The point is to show, live, that the Guard alone lets some attacks through and Aim Shield stops them, and to say why.

## Users
1. **Judges and organisers** watching a demo for about five minutes, often on a projector, 4 to 6 metres away. They are not security engineers. They must see the outcome in seconds and trust it.
2. **The two presenters**, who drive the demo and need controls that do not get in the way, and can type a message a judge suggests.
3. **Organisers running it themselves** from the README (with keys, or in recorded-run mode with none).

## Jobs to be done
- See at a glance which side was hurt and which side stopped the attack.
- Understand *why* (which layer fired) without reading logs.
- Try an attack or a normal question and see both sides react.
- Trust it: honest labels, nothing staged, a clear Live versus Replay indicator.

## Tone
Calm, plain, confident. Sentence case. No jargon on the surface (technical detail lives in disclosures). No marketing language, no exclamation marks, no em dashes.

## Anti-references
- A developer test harness: dense logs, tiny type, everything the same weight.
- A neon "cyber" dashboard: dark glow, red alarms everywhere, decorative motion.
- SaaS cream: gradient hero numbers, identical stat tiles, glass cards.

## Principles
1. **Verdict first.** Each side opens with a plain outcome headline; evidence follows.
2. **Green means the defence worked, red means harm happened.** Never the reverse, never colour alone.
3. **Everything visible for the story fits above the fold** at 1280 by 720.
4. **Honest state.** Pending, error, replay and degraded modes are always visible and labelled.
5. **Readable from the back of the room.** Light theme by default, large presenter mode, 4.5:1 contrast or better.
6. **Familiar controls.** Standard segmented controls, selects and buttons; the interface disappears into the task.
