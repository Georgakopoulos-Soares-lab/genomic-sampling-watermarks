# E11 and E12 protocol — key reuse, many-output leakage, spoofing, and removal

Frozen before any attack was scored. Predictions below were written before the runner existed.

A note on numbering: `docs/experiments.md` uses a different E-numbering for the later experiments than
the protocol documents do. The protocol documents are the operative convention, and in them E11 is key
reuse and many-output analysis and E12 is spoofing and removal. This document covers both because they
share one observation and one runner.

## The question

The verifier holds DNA, a runtime key, and public configuration. The attacker holds DNA only — but not
one sequence. A deployed generator reuses its key, so an attacker accumulates many watermarked outputs
under the *same* key and the *same* key-stream domain and offset.

What does that buy them?

## The structural fact this experiment is built around

The detector's decision at read position `i` depends on one thing: which half of the keyed partition at
stream index `i` the observed token falls into. The partition at index `i` is a function of the key, the
domain, and `i` — never of the observed DNA. So the statistic is a sum of per-position, content-blind
indicators.

Two consequences follow immediately, and neither needs the key:

1. A token seen at position `i` in one watermarked output carries the group membership that position
   `i` requires. Placed at position `i` of a different sequence, it satisfies the detector just as well.
2. A token seen at position `j` carries no information about the group at position `i` when `j ≠ i`,
   because the partition is redrawn per index.

The experiment measures whether these consequences hold in practice, and at what cost to the attacker.

## Attacks

All four are model-free. The attacker never queries the model, never sees a probability, and never
sees the key. The attacker sees only generated DNA.

| Attack | Attacker knowledge | Construction |
|---|---|---|
| A — positional splice forgery | `N` watermarked outputs under one key, and the public claim that the detector reads 6-mers from position zero | for each token position `i`, copy the 6-mer at position `i` from a uniformly chosen one of the `N` outputs |
| B — positional shuffle removal | one or more watermarked outputs | apply a uniformly random permutation to token positions, so the token that lands at `i` came from some `j ≠ i` |
| C — bounded local shuffle removal | one watermarked output | shuffle token positions only within consecutive blocks of `w` tokens, for `w` in 2, 3, 4, 6, 8, 16, 32 |
| D — verifier-side many-query null | none | one fixed key scored against many sequences it did not generate |

Attack A is a **spoofing** attack: it manufactures provenance the generator never granted. Attacks B
and C are **removal**. Attack D is not an attack but the calibration question key reuse raises for the
verifier.

Attack A needs `N ≥ 2` to produce a sequence that is not a verbatim copy of an observed output; with
`N` outputs and `n` token positions there are `N^n` distinct forgeries, so novelty is not the limit.

## Predictions, written before the run

1. **Attack A detects at essentially the rate a genuine output does**, close to 1.000 at every length
   E4 evaluated. Each spliced token inherits the group agreement its position needs, and the
   generator's own agreement rate is 0.984 to 0.997, so a splice should lose almost nothing. If this
   holds, the construction as specified **provides no defence against spoofing under key reuse**, and
   that is a limitation to state in the paper rather than a bug to fix in the sampler.
2. **Attack A works at `N = 2`** and improves negligibly with more outputs, because each position is
   satisfied independently and one donor per position is already enough.
3. **Attack B removes the mark.** The statistic should fall to about zero and detection to about the
   calibrated false-positive rate, because a permuted position is an independent fair coin.
4. **Attack C degrades smoothly with `w`**, and even `w = 2` should cost roughly half the signal: a
   swap inside a pair leaves each of the two positions matched only by chance. Concretely, a fraction
   `f` of positions displaced reduces the per-token signal by about `f`, so `w = 2` (half the positions
   displaced on average) should roughly halve the statistic, and the statistic should approach zero by
   `w = 16`.
5. **Attack D holds its calibration.** A fixed key scored against many sequences it did not generate
   should exceed the threshold at about the calibrated rate, because the wrong-key and any-key nulls
   already sampled exactly this event from the other direction.

Prediction 1 is the one that matters. If it is right, the honest headline is that this construction
authenticates a *distribution*, not a *sequence*, and anyone holding two outputs can mint a third.

## Frozen shape

| Item | Frozen choice |
|---|---|
| Policies | `C_tok`, `G_tok`, `G_bp` |
| Source outputs | the E4 corpus: 8 prompts, 512 tokens, one fixture key, one domain, offset 0 |
| Donor count `N` for attack A | 2, 4, and 8 |
| Block widths `w` for attack C | 2, 3, 4, 6, 8, 16, 32 |
| Evaluated lengths | 384, 768, 1,536, and 3,072 bases as prefixes |
| Detector search | the E4 search unchanged: 2 orientations x 6 phases x full prefix x 8 key-stream offsets |
| Target FPR | 0.01, calibrated on the E4 null families for that policy and length |
| Nulls | wrong key on the watermarked arm, and any key on the ordinary arm, exactly as E4 pools them |
| Attack randomness | a public replay seed derived from the policy, attack, and parameter; no secret input |
| Uncertainty | the joint resample: nulls resampled and the threshold recalibrated on every replicate, prompt clusters resampled independently, 20,000 replicates, seed 2718 |
| Utility accounting | the nine admitted sequence proxies, comparing each attacked sequence against its own source |

### What makes this a fair test of the attacks

The attacked sequences are scored by the **same** detector, against the **same** thresholds, calibrated
on the **same** nulls as the genuine E4 sequences. An attack that were scored against a threshold
calibrated on attacked material would be measuring something else.

For attack A the forged sequence is never one of the donors: a forgery whose every position happened to
come from a single donor is rejected and redrawn, so a reported success is never a verbatim copy.

## Preregistered reading

- Attack A is reported as a **detection rate**, and a high rate is a **vulnerability**, not a success.
  The sign of the conclusion is the opposite of every other detection rate in this project, and the
  paper must not present it on a shared axis with them.
- Attacks B and C are reported as detection rate against the attack parameter, with the proxy cost
  beside it. A removal that destroys the sequence is not a useful attack, so removal without a utility
  column is not a result.
- Attack D is reported as an achieved false-positive rate with its interval.
- Nothing here is a cryptographic claim. These are measurements against one specified construction
  under one specified attacker, not a security reduction.

## Boundary

Clean sequences, no edit channel: attacks are composed with neither substitutions nor indels. The
attacker is assumed to know the public configuration and to have aligned donors at offset zero, which
is the strongest reasonable assumption and therefore the right one for a limitation. Nothing here
speaks to whether a coding layer, a content-binding construction, or a per-sequence nonce would close
the spoofing gap; those are constructions this project has not built.

## Result, 2026-08-23

Three policies, the E4 corpus of eight watermarked outputs under one key, the E4 detector search and
the E4 null pooling unchanged. Validated by `validate_attack_report`, which recomputes every cell from
the stored per-trial rows, re-derives each statistic from its match count, and refuses a report whose
threshold was calibrated on anything but the unattacked nulls.

### Prediction 1 was right, and it is the headline

**Spliced forgeries are accepted at rate 1.000, at every length, on every policy**, with statistics
indistinguishable from genuine output:

| Policy | 3,072-base genuine statistic | spliced, 2 / 4 / 8 donors |
|---|---|---|
| `C_tok` | 21.91 | 21.87 / 21.79 / 21.93 |
| `G_tok` | 22.25 | 22.24 / 22.22 / 22.19 |
| `G_bp` | 22.48 | 22.47 / 22.51 / 22.46 |

Two donors are enough, and more donors change nothing, exactly as prediction 2 said. Every forgery
scored here is novel: a draw that took all positions from one donor was rejected and redrawn, so no
reported success is a verbatim copy.

**Read the sign carefully.** This is the one detection rate in the project where 1.000 is bad. It means
an attacker holding two outputs from a key can mint a third sequence the generator never produced, and
the verifier will call it authentic.

The reason is the structural fact this experiment was built on, and it is not fixable by tuning: the
statistic is a sum of per-position, content-blind indicators, so **the construction authenticates a
distribution, not a sequence**. Nothing in it binds position `i` to position `j`, and nothing binds the
sequence to a nonce, a length, or a payload. Any fix is a different construction.

### Prediction 3 was right: rearrangement removes the mark

A full positional shuffle drops detection to **0.000 at every length on every policy**, and the
statistic falls to 2.29–2.78, which is the null level.

### Prediction 4 was right about the statistic and incomplete about detection

Prediction 4 said a block width of 2 should roughly halve the signal. Measured share of the genuine
statistic retained at width 2: 0.53–0.58 for `C_tok`, 0.44–0.50 for `G_tok`, 0.49–0.55 for `G_bp`.
Right.

What the prediction did not carry through is that halving a statistic which grows like the square root
of the length leaves it above threshold once the length is large enough. So detection after a width-2
shuffle *rises* with length rather than staying halved:

| Policy | width for detection 0.000 at 384 b | at 1,536 b | at 3,072 b |
|---|---|---|---|
| `C_tok` | 4 | 8 | 8 |
| `G_tok` | 4 (non-monotone at small n) | 16 | 16 |
| `G_bp` | 4 | 8 | 32 |

By width 8 to 16 the absolute statistic sits at the null level for every policy and length, so the
mark is gone rather than merely weakened. The reading: **a longer watermarked sequence is harder to
strip by local rearrangement**, because the attacker must displace tokens over a wider window to
overcome the extra signal. Small-`n` noise is visible in the width-by-width curves — eight trials per
cell, and the joint intervals are correspondingly wide — so the width thresholds above are read from
where the statistic reaches the null level, not from a single zero.

### Prediction 5 was right: calibration survives key reuse

One fixed key scored against sequences it did not generate exceeded the threshold in 0 or 1 of 8 trials
per cell, across all policies and lengths. At eight trials the resolution is 0.125, so this confirms
the calibration is not obviously broken by key reuse rather than measuring the rate precisely.

### The utility column, and why it undercuts the removal result

Removal has to be priced, or "the mark can be removed" is worthless. Largest relative shift across the
nine admitted proxies:

| Attack | `C_tok` | `G_tok` | `G_bp` |
|---|---|---|---|
| full positional shuffle | 0.167 | 0.123 | 0.143 |
| block shuffle, any width | 0.060 – 0.214 | 0.154 – 0.231 | 0.111 – 0.222 |
| splice forgery | 0.196 – 0.422 | 0.223 – 0.365 | 0.217 – 0.294 |

In every case the largest shift is on `longest_homopolymer_run`, a single extreme-value statistic, and
every other proxy moves far less. GC fraction, base, dinucleotide and trinucleotide entropy, and purine
fraction are essentially unchanged.

**This is a fact about the proxies, not a licence to call removal free.** The removal attacks permute
whole 6-mers, so they preserve the 6-mer multiset *exactly* — a tested invariant — and a suite of
composition and complexity statistics is blind to them by construction. What a rearrangement destroys
is long-range structure: reading frames, splice junctions, anything spanning a junction. The ORF and
independent-model-likelihood proxies declared in `../baseline_definition.md` and not yet implemented
are precisely the instruments that would price it, and this result is the strongest argument yet for
building them.

Note also that **the forgery is more anomalous than the removal** on these proxies, because splicing
mixes tokens across organisms. A defender screening for composition anomalies would be more likely to
catch the spoof than the strip.

## Implementation status

- `src/genomic_watermarks/attacks.py` implements the three attacks; `tests/test_attacks.py` asserts
  that a splice is never a verbatim copy and that both shuffles preserve the 6-mer multiset exactly,
  so a measured removal can never be confused with a composition change.
- `scripts/run_key_reuse_attacks.py` runs the experiment and stores every per-trial row.
- `src/genomic_watermarks/attack_report.py` and `scripts/analyze_key_reuse_attacks.py` validate it,
  including that the threshold came from unattacked nulls and that the report states which direction
  each family's detection rate points.

## Evidence boundary

No number moves into `evidence/measurements.yaml` without explicit evidence-admission review.
