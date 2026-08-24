# 19 — What two outputs buy an attacker

## The question we had been putting off

Everything so far asked whether the mark *survives*: substitutions, crops, the other strand, deleted
bases. That is the wrong question to end on, because it assumes an attacker who is trying to erase
something. There is a second attacker who wants the opposite — to make a sequence the generator never
wrote look like one it did.

And there is a fact about deployment we had not yet exploited: a real generator **reuses its key**. Sign
a thousand sequences and an attacker collects a thousand examples, all produced under the same secret.

So: what do those examples buy them?

## The structural weakness, stated before any measurement

Recall what the detector actually does. At each 6-mer position `i`, it uses the key to split the 4,096
possible 6-mers into two halves, flips a keyed coin to pick one half, and asks: *is the 6-mer I'm
looking at in the chosen half?* Then it counts how often the answer is yes.

The split at position `i` depends on the key, the setup label, and the number `i`. It does **not** depend
on what DNA is actually there. And the split at position `i` tells you nothing about the split at
position `j`.

Two consequences follow, and neither of them requires the key:

1. A 6-mer observed at position `i` of a real watermarked sequence is *already in the right half* for
   position `i`. Drop it into position `i` of any other sequence and the detector is still satisfied.
2. A 6-mer moved to a *different* position is in the right half only by luck, because that position's
   split is unrelated.

Consequence 1 is a forgery recipe. Consequence 2 is an erasure recipe. We wrote both down as
predictions, then measured them.

## The forgery: take two sequences, make a third

The attack is almost embarrassingly simple. Take two watermarked sequences. For each 6-mer position,
flip a coin and copy that position's 6-mer from one or the other. The result is a sequence that has
never existed — a genuine novel sequence, not a copy of either donor. We explicitly reject and redraw
any attempt that happens to take everything from one donor, so nothing counted here is a copy.

The verifier accepts it. Every time.

| Model policy | Genuine sequence score | Forgery from 2 / 4 / 8 donors |
|---|---|---|
| `C_tok` | 21.91 | 21.87 / 21.79 / 21.93 |
| `G_tok` | 22.25 | 22.24 / 22.22 / 22.19 |
| `G_bp` | 22.48 | 22.47 / 22.51 / 22.46 |

Detection rate on forgeries: **1.000**, at every length we tested, on every model. The scores are not
merely above the threshold — they are indistinguishable from real watermarked output to two decimal
places.

**Two donors is enough.** More donors add nothing, because each position is satisfied on its own.

This is the one number in this whole project where 1.000 is bad news. Everywhere else, "detected every
time" is the result we wanted. Here it means the verifier cannot tell the difference between provenance
and a collage.

## Why this is not a bug we can fix

The temptation is to treat this as an implementation slip. It is not. Go back to the structure: the
score is a *sum of independent per-position checks*, and each check is blind to the DNA content. There
is nothing in the design that ties position 5 to position 400, or ties the sequence to its length, or
to a serial number, or to anything at all about the sequence as a whole.

So the honest one-line statement is:

> **This construction authenticates a distribution, not a sequence.**

It can tell you "this DNA was drawn using my key". It cannot tell you "this *particular* DNA came from
me". Fixing that means a different construction — binding the mark to the content, or carrying a
per-sequence serial number inside the sequence, or adding a coding layer. We have not built any of
those, and we are not going to claim they would work without building them.

## The erasure: shuffle it

The mirror attack. Take one watermarked sequence and rearrange its 6-mers. Each 6-mer now sits at a
position whose secret split is unrelated to it, so each check becomes a coin flip and the score
collapses to the noise level.

A complete shuffle drops detection to **0.000** on every model at every length. The mark is gone.

More interesting is a *bounded* shuffle, where the attacker only permutes within small blocks and so
disturbs the sequence less. Here something worth knowing showed up.

Shuffling within pairs of 6-mers leaves about **half** the score — which is what we predicted. But we
had not thought through the consequence: the score grows with the square root of the sequence length,
so half of a big score is still a big score. Detection after a pairwise shuffle therefore *rises* with
length:

| Block width | 384 bases | 1,536 bases | 3,072 bases |
|---|---|---|---|
| 2 | mark often survives | mark survives | mark survives |
| 4 | mark gone | partly survives | partly survives |
| 8–16 | mark gone | mark gone | mark gone (16–32 for one model) |

So **a longer watermarked sequence is harder to strip by local rearrangement**. The attacker has to
scramble across a wider window to overcome the extra signal. That is a small piece of good news in an
otherwise negative section, and it fell out of a prediction being right about the score and incomplete
about the consequence.

## The uncomfortable part: our own measuring instruments can't see the attack

"The mark can be removed" is a worthless claim on its own. Anyone can remove a watermark by replacing
the DNA with random letters. The question is always: *what did the attack cost?*

So we measured all nine of our sequence-quality proxies before and after. The largest change from a
full shuffle was 12–17%, on `longest_homopolymer_run` — a single extreme-value statistic. GC content,
base and pair and triplet entropy, purine fraction: essentially unchanged.

By our own numbers, the removal attack is nearly free.

**That conclusion is about our proxies, not about the attack.** The shuffle moves whole 6-mers around,
so the *bag* of 6-mers is exactly the same before and after — we test this as an invariant. Every one
of our nine proxies is a composition or complexity statistic, and a suite of composition statistics is
constitutionally blind to a rearrangement of the very units it counts.

What a shuffle actually destroys is long-range structure: reading frames, anything that spans a
junction, anything that depends on order rather than content. Measuring *that* needs the two
instruments our own baseline document promised — open-reading-frame summaries and scoring the sequence
under an independent model.

So we built both. Neither works.

### The instrument that was blind, and the one that only looked like it wasn't

The **independent-model score** — how likely the sequence looks under a small statistical model of DNA
fitted on genome windows we held out — barely moves: at most 2.4%. The reason is simple once you see
it. Generated DNA from these models is close to random-looking, so a small model gives it about the
same score as it gives anything else, and shuffling 6-mers leaves most of the short neighbourhoods that
the model actually looks at intact.

The **reading-frame measure** looked like a success. A reading frame is a stretch of DNA that reads as a
continuous instruction, and it spans 6-mer boundaries, so shuffling should shred it. And indeed the
longest reading frame changes a lot — by 7% to 43%, more than any composition measure.

Then we asked whether it changes in the *same direction* across our eight sequences. It does not.
Under the bounded shuffles — the ones an attacker would actually use, and the ones that strip the
watermark — the longest reading frame gets **longer** about as often as it gets shorter.

Here is why, and it is worth internalising. Random DNA contains long reading frames purely by chance: a
1.8 kb random sequence usually carries one over 200 bases, with no meaning at all. So the "longest
reading frame" of a high-entropy sequence is mostly a lottery result. Shuffling the sequence does not
destroy a structure; it buys a fresh lottery ticket. Sometimes the new ticket is better.

Measuring the *size* of the change captures the lottery. Only checking the *direction* reveals there
was no structure being destroyed.

### The pattern, for the seventh time

This is the seventh time in this project that a big number turned out to be a magnitude with no
direction behind it, and a properly paired test dissolved it. The previous six were a comparison that
counted ties on the wrong side, a search range that could not reach half the cases it was meant to, a
confidence interval that ignored one of its two sources of noise, a shuffle test that ignored a shared
fitted direction, an interval that treated an estimated threshold as exact, and an interval that
depended on which of two lists got concatenated first.

Every one was caught the same way: a number looked too clean, so we rebuilt the procedure on data whose
answer we already knew.

### Where that leaves the removal attack

Unpriced, and we say so. We are not reporting that we forgot to measure the cost. We are reporting that
we built both instruments we had named in advance for exactly this job, and neither can see a bounded
6-mer rearrangement. Anyone who wants to claim this attack is expensive needs a measure of long-range
order that we do not have.

That is a worse-sounding result than "the attack costs 17%", and it is the true one.

One small irony worth noting: the **forgery** disturbs the proxies *more* than the erasure does (up to
42% on CpG content), because splicing mixes DNA from different organisms. A defender screening for
composition anomalies would be more likely to catch the fake than the strip.

## Where this leaves the project

Stated plainly, without hedging in either direction:

**What the construction does.** Distribution-preserving, model-free provenance detection that a
standalone verifier can recover from DNA and a key alone, that survives one base in five being
substituted and survives cropping and reverse complementation, and whose false-alarm rate is honestly
calibrated over every alignment the detector actually searches.

**What it does not do.** Protect against anyone holding two outputs from the same key. Not partially —
at all.

Both halves are results. A paper that reported only the first would be advertising, and one that
reported only the second would be throwing away real measurements. The reason the second half exists as
a number rather than a worry is that we went looking for it on purpose.
