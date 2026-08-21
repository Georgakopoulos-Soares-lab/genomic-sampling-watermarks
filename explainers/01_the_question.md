# 01 — The question

## The problem

A genomic language model can generate a DNA-like sequence. After that sequence is copied, cropped,
reverse-complemented, or lightly edited, its origin may be difficult to establish.

We want to test whether generation can leave a **secret-key provenance signal** in the sequence.
Someone holding the key should be able to detect the signal. Someone without the key should not
see an obvious statistical difference between ordinary and watermarked model output.

The complete path is:

```text
DNA context
    ↓
genomic language model → probabilities for the next 6-mer
    ↓
secret-key sampler → watermarked DNA
    ↓
substitution / insertion / deletion / crop / reverse complement
    ↓
standalone detector + secret key → score and calibrated decision
```

## One paper, two model families

Carbon and GENERator-v2 are not separate paper projects. They answer complementary parts of the
same question:

- Does the idea work across more than one genomic model?
- Does it behave differently under direct 6-mer sampling and base-by-base sampling?
- Is there enough probability uncertainty to carry a detectable signal within roughly 1–5 kbp?

Using both models makes the paper about the watermarking mechanism, not a quirk of one checkpoint.

## A tiny example

Suppose a model says the next DNA block should be one of these:

| Next 6-mer | Probability |
|---|---:|
| `AAAAAA` | 0.40 |
| `TTTTTT` | 0.30 |
| `CCCCCC` | 0.20 |
| `GGGGGG` | 0.10 |

Ordinary generation draws from that table directly.

Watermarked generation also has to produce `AAAAAA` about 40% of the time, `TTTTTT` about 30%, and
so on when averaged over fresh secret randomness. But it coordinates each draw with a hidden keyed
target. That coordination is what the detector later measures.

The hard part is keeping both properties:

1. **Preservation:** the visible output distribution remains the declared model distribution.
2. **Detectability:** the secret-key holder sees more agreement than chance.

If we improve detectability by simply forcing a favorite set of DNA blocks, we have changed the
model distribution. That is an easier watermark, but it is not the main claim of this project.

## What the detector is allowed to know

The detector receives:

- the DNA sequence;
- a secret key supplied at runtime;
- public configuration, such as the watermark method and search settings.

It does **not** receive:

- the original prompt;
- model weights or model logits;
- the generation seed;
- an unedited reference copy.

This is why the detector is described as *standalone* or *model-free*.

## What success would mean

The project must measure whether the signal is detectable at a declared false-positive rate, both
before and after realistic edits. It must also test whether ordinary statistical classifiers can
distinguish watermarked sequences without the key.

Success does not mean that generated DNA is functional, viable, biologically safe, or impossible
to attack. Those are different claims and are outside this paper unless supported separately.

Next: [How genomic models generate DNA](02_how_genomic_models_generate.md).
