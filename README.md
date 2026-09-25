# Position-independent SynthID for genomic DNA generation

This repository contains one sampling watermark, one matched ordinary control, and one standalone
detector. The paper is being rebuilt as a fresh, dual-model evaluation on Carbon-500M and
GENERator-v2 1.2B. The detector needs the observed DNA, secret key, public generation domain, and
fixed public settings; it does not need the prompt or model.

The authoritative future design, frozen-gate proposal, evidence requirements, and manuscript
outline are in the
[dual-model paper rebuild plan](docs/research/dual_model_synthid_paper_rebuild_plan.md).

The numerical results below document version-one development runs. They are deliberately retained
for auditability but are not confirmatory evidence for the rebuilt paper.

## Legacy Carbon development result

The final held-out detector evaluation used 192 public prompts and two stored draws per prompt,
giving 384 sequences in each result cell. Each read contained the 384-base prompt followed by the
3,072-base generated continuation. The detector searched both strands, every nucleotide start, and
four possible region lengths in one corrected decision.

| Read condition | Correct-key SynthID detections | Ordinary Carbon false positives | Wrong-key false positives |
|---|---:|---:|---:|
| Clean | 384/384 | 1/384 | 0/384 |
| One nucleotide substitution | 384/384 | 1/384 | 0/384 |
| One nucleotide insertion | 384/384 | 1/384 | 0/384 |
| One nucleotide deletion | 384/384 | 1/384 | 0/384 |

The four displayed ordinary false positives are the same underlying prompt and draw repeated
across the four conditions; each edit occurred outside its winning region. At the prompt level,
the clean ordinary result is therefore one positive among 192 independent prompt clusters. Its
exact 95% interval is 0.0132% to 2.8676%. The data are compatible with the declared 1% target, but
they do not prove that the operational false-positive rate is below 1%.

Quality was measured separately on the stored 3,072-base generations. The paired difference in
Carbon negative log-likelihood, SynthID minus ordinary, was 0.00852 nat per token, with a 95%
prompt-level interval from -0.04426 to 0.05973 and p=0.751. No declared sequence summary differed
after correction for testing several summaries. This means no quality reduction was detected; it
does not prove biological equivalence.

## Legacy GENERator development result

The same frozen SynthID process was repeated with
`GenerTeam/GENERator-v2-eukaryote-1.2b-base`, using its direct 4,096-way canonical 6-mer
distribution. It again produced 1,024 sequences from 256 prompts and reserved the same 192 prompts
for final detection.

| Read condition | Correct-key SynthID detections | Ordinary GENERator false positives | Other-key false positives |
|---|---:|---:|---:|
| Clean | 384/384 | 0/384 | 1/384 |
| One nucleotide substitution | 384/384 | 0/384 | 1/384 |
| One nucleotide insertion | 384/384 | 0/384 | 1/384 |
| One nucleotide deletion | 384/384 | 0/384 | 0/384 |

The one other-key positive in the first three rows is the same prompt and draw. The paired
GENERator negative-log-likelihood difference was -0.00564 nat per 6-mer, with a 95% prompt-level
interval from -0.05614 to 0.04378 and p=0.830. No declared quality summary differed after
multiple-test correction. Thus GENERator passes the same predeclared quality and detector gates as
Carbon, although the exact null counts need not match. Full interpretation and limitations are in
[the GENERator execution record](docs/research/generator_synthid_execution_2026_09_03.md).

## Detector command

```bash
export GENOMIC_SYNTHID_KEY='<hex-encoded-secret-key>'
PYTHONPATH=src python3 scripts/detect_synthid_position_independent.py \
  --input observed.fasta --domain '<generation-domain>'
```

The command does not print the key or the input DNA. See
[the detector protocol](docs/research/synthid_position_independent_detector_protocol.md) and
[the completed execution record](docs/research/carbon_synthid_position_independent_execution_2026_09_02.md).

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
python3 scripts/check_evidence.py
uv run ruff check .
```

The old model-backed paths remain documented for audit history. Model weights and source DNA are
not stored in this repository. New paper-bound results must use the fresh dual-model study identity,
new prompt cohort, documented execution environment, and `synthid.v2.*` evidence namespace.

## Scope

The attacker considered here does not know the secret key and cannot inspect or query the detector
score. The edit checks model ordinary single-nucleotide changes, not an optimization attack.
Multiple edits and detector-guided edits are not part of the protocol. Public fixture keys make the
experiment reproducible; they are not evidence that a deployment key cannot be recovered from many
examples.
