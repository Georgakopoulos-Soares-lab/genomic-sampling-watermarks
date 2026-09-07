# Dual-model SynthID paper rebuild plan

## Status

This is the proposed authoritative plan for rebuilding the paper around the current SynthID
tournament sampler and position-independent detector for both Carbon-500M and GENERator-v2 1.2B.
It is a plan, not a claim that the new experiment has already run.

The existing version-one runs are development history. Their results may be used to estimate
runtime and statistical variance, but they will not be copied, renamed, or described as newly
frozen evidence. The rebuilt manuscript will cite only new result and measurement identifiers.

## Scope decision

The rebuilt paper has two co-primary model evaluations:

- `HuggingFaceBio/Carbon-500M` with its direct canonical 6-mer policy; and
- `GenerTeam/GENERator-v2-eukaryote-1.2b-base` with its direct canonical 6-mer policy.

It contains one watermark implementation, the SynthID binary tournament, and one final detector,
the position-independent SynthID detector. The only generation control is ordinary categorical
sampling from the same model-specific distribution. The robustness scope is clean DNA and exactly
one ordinary nucleotide substitution, insertion, or deletion. Multiple edits, detector queries,
and detector-guided editing remain outside scope.

Before implementation begins, the repository-level and paper-level instructions must be revised
from Carbon-only to dual-model. This request supplies the scientific scope decision, but the file
changes must still be made explicitly so future work cannot silently follow conflicting rules.

## What “new” means

The new identity belongs to the study and evidence, not automatically to the mathematical
algorithm. The proposed study identifier is:

```text
synthid_dual_model_confirmatory_v2
```

If the sampler and detector behavior remain unchanged, their implementation identifiers remain
`synthid-tournament-v1` and `synthid-position-independent-detector-v1`. Renaming unchanged code as
a new algorithm would be misleading. If any behavior changes, the affected implementation receives
a new identifier before the protocol is frozen.

New work requires:

- a new protocol and configuration hash;
- a clean source commit or content-addressed source snapshot;
- a new, previously uninspected prompt cohort;
- new M5 Pro runs for both models;
- new result directories and artifact manifests;
- a new evidence namespace, proposed as `synthid.v2.*`; and
- a manuscript generated only from the new evidence map.

The old artifacts remain byte-for-byte unchanged as excluded history. “Forget” means they are not
used for confirmatory claims; it does not mean destroying or relabeling the audit trail.

## Scientific questions

The paper will answer four questions separately for each model:

1. Does the implementation sample from the fixed-key tournament law it calculates?
2. Is model quality non-inferior to ordinary generation within a limit fixed before the run?
3. Can the detector find the watermark without knowing the prompt boundary, strand, or 6-mer
   alignment?
4. Are ordinary and independent-key outputs controlled at the declared false-positive level?

Replication across two models supports portability of the implementation. It does not establish
that the models, their output distributions, or their biological usefulness are equivalent.

## Proposed locked design

These are the recommended values to freeze after the M5 smoke benchmark and before inspecting any
confirmatory result.

| Item | Proposed value |
|---|---|
| Models | Carbon-500M and GENERator-v2 1.2B at exact pinned revisions |
| Hardware | Documented M5 Pro with 48 GB unified memory for every paper-bound stage |
| Model policy | Direct normalized distribution over each model's 4,096 canonical DNA 6-mers |
| Sampling | Temperature 1.0; no top-k or top-p truncation |
| Prompts | 1,024 new public prompts, disjoint from every prior cohort |
| Source design | Non-overlapping windows; one prompt per source record where possible; taxonomic and source-record clustering recorded |
| Draws | Two per prompt and arm, with distinct replay seeds |
| Keys | Sixteen reproducible fixture-key identifiers, balanced across prompts; the two draws for one prompt always use different keys |
| Continuation | 512 6-mer tokens, or 3,072 generated bases |
| Arms | Correct-key SynthID and matched ordinary sampling |
| Detector input | 384-base prompt prepended to the continuation; true boundary withheld |
| Detector search | Both orientations, every nucleotide start, and 384/768/1,536/3,072-base regions |
| Detector threshold | Analytic, with every searched region included in one corrected read-level probability |
| Proposed detector target | 0.001 per read |
| Read conditions | Clean; one frozen random nucleotide substitution, insertion, or deletion |
| Primary unit | Prompt, with source-record and organism sensitivity analyses |
| Calibration prompts | None in the confirmatory cohort |

The earlier data may be called development data. They fix the unweighted detector score and inform
the power calculation; they do not enter a new estimate or confidence interval. Because the final
threshold is analytic, no new prompt is needed to fit it. All new prompts remain available for
confirmatory evaluation.

### Why use a 0.001 detector target

A detector configured at 1% should occasionally produce false positives near 1%, so an empirical
confidence bound will not reliably prove that its rate is below the same 1% value. Configuring the
new detector at 0.1% creates a meaningful safety margin. With 1,024 independent primary null reads,
an exact simultaneous upper bound can remain below 1% with a small number of observed positives.
The final protocol must recompute the exact attainable null probability for each read because the
binomial score is discrete.

### What “quality must not drop” can mean

No finite experiment can prove an exactly zero change. The defensible replacement is a
pre-specified non-inferiority claim: the data must rule out a loss larger than an agreed practical
limit.

The recommended primary margin is an increase of `0.05 nat/6-mer` in teacher-forced negative
log-likelihood. This corresponds to at most a 5.13% increase in token perplexity. For each model,
the one-sided confidence bound, corrected across the two co-primary model tests, must remain below
that margin. The margin must be scientifically approved before the protocol is hashed. It must not
be widened after seeing new results. If 5.13% is considered too permissive, a smaller margin and the
larger sample size required by a new power calculation must be frozen instead.

The 1,024-prompt recommendation is a provisional power and false-positive target informed by the
legacy variance estimates. A blinded power script must recompute the required count using only the
predeclared margin and legacy variance, account for clustering, and freeze the final count before
confirmatory generation.

## Proposed statistical analysis

- Model quality is paired within prompt and draw. The primary estimate is the SynthID-minus-ordinary
  negative-log-likelihood difference, with prompts resampled as clusters and both draws kept
  together.
- The two model-quality tests are co-primary. Each uses a one-sided 97.5% bound so their combined
  error rate is at most 5%.
- Clean correct-key detection is summarized at both sequence level and prompt level. The primary
  prompt event is that both draws are detected. The two model bounds are corrected together.
- The six model-by-single-edit sensitivity cells form a separate family. Their lower bounds are
  adjusted together rather than treating each displayed row as an unrelated experiment.
- Ordinary output, SynthID output checked with an independent key, and public DNA remain three
  distinct null families. One draw per prompt is fixed in advance for the primary independent-read
  bound; the second draw is a paired replication and is analyzed with prompt clustering.
- False-positive bounds are simultaneous across both models and all primary null families. The
  exact prompt-level goodness-of-fit calculation also uses each read's attainable discrete null
  probability instead of assuming that every read has exactly the nominal probability.
- Secondary sequence summaries use a frozen multiple-testing correction and are reported whether
  or not they are significant. They are not used as substitutes for the primary non-inferiority
  result.
- The cross-model comparison is descriptive. The study is powered to establish each model's gate,
  not to declare one genomic model better than the other.

All interval type, tail choice, confidence allocation, bootstrap seed, resampling hierarchy, and
missing-data rule must be written into the protocol and executable analysis before the cohort is
opened.

## Frozen scientific gates

The protocol will contain a machine-readable gate file. A failed gate is reported; it is never
made to pass by tuning the same confirmatory data.

| Gate | Required evidence | Pass condition | Consequence of failure |
|---|---|---|---|
| S0: frozen identity | Protocol, configuration, source, cohort, model, tokenizer, analysis, and gate hashes | Every recorded digest matches before generation | Stop; create a new protocol identity |
| S1: model adapters | Model/tokenizer revision and canonical vocabulary audit | Exactly 4,096 canonical 6-mers and the declared direct policy for each model | Stop before generation |
| S2: sampler mathematics | Differential tests against the pinned upstream implementation and enumerated small tournaments | Exact agreement within the frozen numerical tolerance | Stop; implementation invalid |
| S3: empirical sampler check | 256 new fixed states/model, 5,000 draws/arm/state, at least 9,999 Monte Carlo replicates, and eight deliberately incorrect controls | No corrected rejection in either real arm; every incorrect control rejected; family-level fit not rejected | Do not make sampler-correctness claim |
| S4: corpus completeness | Generation manifest and shard validator | Every prompt/draw/arm exists once, has 512 tokens, uses its declared seed/key identifier, and hashes correctly | Stop before analysis |
| S5: model quality | Prompt-paired negative-log-likelihood difference and simultaneous one-sided interval | Upper bound is below the frozen non-inferiority margin for both models | State that quality preservation was not established |
| S6: secondary quality flags | Predeclared composition and repetition summaries | Report all adjusted results; any adverse flag triggers investigation but is not hidden | Qualify the quality conclusion |
| S7: clean detection | Correct-key prompt-level result for each model | Simultaneous 95% lower bound is at least 99% | Do not claim reliable clean detection |
| S8: single-edit detection | Separate substitution, insertion, and deletion results | Simultaneous 95% lower bound is at least 98% in every declared cell | Omit the failed robustness claim |
| S9: false positives | Ordinary, independent-key, and public-DNA nulls kept separate | Simultaneous 95% upper bound below 1% for clean primary nulls, plus no corrected exact null-fit rejection | Do not claim operational false-positive control |
| S10: complete search correction | Trial-level recomputation | Every orientation, start, and length is counted in the global probability for every read | Invalidate detector results |
| S11: strict result validation | Independent cross-model validator | Every count, statistic, interval, decision, source hash, and artifact hash recomputes | No evidence admission |

The paper must report observed estimates and intervals even when a gate fails. A gate controls the
wording of the conclusion; it is not a filter for suppressing unfavorable data.

## Frozen software and evidence gates

Software checks support implementation consistency and traceability. They are not measurements of
genomic quality, biological function, detection power, or cryptographic security.

| Gate | Required action | Pass condition |
|---|---|---|
| Q0: locked environment | Install from the frozen lock file without updating it | Exact dependency resolution succeeds |
| Q1: unit and property tests | Run the complete offline suite, including pinned upstream parity | Zero failures, zero errors, and zero unexplained skips; test count and upstream revision recorded |
| Q2: detector equivalence | Compare optimized and literal exhaustive search on frozen fixtures | Identical winning region, statistic, corrected probability, and decision |
| Q3: validator tamper tests | Corrupt one count, hash, probability, key mapping, and path in test fixtures | Every corruption is rejected |
| Q4: lint and formatting | Run Ruff lint and Ruff format checks | Both exit successfully under recorded Ruff version/configuration |
| Q5: shell and schema checks | Check shell syntax and all machine-readable schemas | No syntax or schema errors |
| Q6: strict M5 doctor | Verify machine, memory, Python, MPS/CPU support, cache, and pinned revisions | Every required field matches the M5 profile |
| Q7: evidence audit | Parse the ledger, recompute every cited value, and recursively verify manifests | No missing, duplicate, stale, or mismatched reference |
| Q8: release-bundle audit | Reject absolute paths, raw keys, credentials, model weights, and disallowed sequence data | Portable content-addressed bundle passes |
| Q9: manuscript build | Generate tables from evidence and build LaTeX | PDF builds with no unresolved references; generated-table hashes match the manifest |

The final release must capture machine-readable receipts for these gates. For example:

```bash
uv sync --frozen --all-extras

GSW_SYNTHID_UPSTREAM=/path/to/pinned/synthid-text \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
uv run --frozen python -m unittest discover -s tests -v

uv run --frozen ruff check .
uv run --frozen ruff format --check .
python3 scripts/doctor.py --strict --profile m5-pro-48gb
python3 scripts/check_evidence.py --strict
python3 scripts/validate_dual_model_release.py --bundle outputs/synthid_dual_model_confirmatory_v2
cd paper && ./scripts/build.sh
```

Interfaces containing `--strict` and the cross-model validator are planned deliverables; the current
scripts do not yet implement all of them.

## Execution sequence

### Phase 0: change the active scope

1. Update `AGENTS.md`, `PROJECT.md`, `paper/AGENTS.md`, `paper/README.md`, and `evidence/README.md`
   so Carbon and GENERator are both paper models.
2. Mark every current version-one measurement and manuscript map as legacy/development-only.
3. Keep old result files immutable, but remove their identifiers from the active manuscript map.
4. Reserve the `synthid.v2.*` namespace for new evidence.

Exit condition: no active instruction or paper file describes GENERator as supplementary.

### Phase 1: make one shared implementation path

1. Replace model-specific orchestration duplication with one parameterized local supervisor.
2. Add Carbon and GENERator as model profiles under one shared study configuration.
3. Make every required path work on MPS with CPU fallback; no CUDA or remote service belongs in the
   required workflow.
4. Create one cross-model validator and bundle-relative artifact paths.
5. Strengthen the environment doctor and evidence checker as described by gates Q6–Q8.
6. Add direct tests for the doctor, evidence checker, release validator, paper table generator, and
   deliberate artifact corruption.

Exit condition: the offline test and lint gates pass with the frozen upstream comparison enabled.

### Phase 2: freeze the protocol before new results

1. Pin the exact model and tokenizer revisions.
2. Approve the non-inferiority margin and run the blinded clustered power calculation.
3. Freeze sample count, draw count, fixture-key schedule, seeds, edit procedure, detector target,
   searched lengths, confidence procedures, multiplicity handling, and gate rules.
4. Build a new public cohort that is disjoint from every previous prompt and record source licenses,
   coordinates, taxonomic strata, and hashes.
5. Freeze the protocol, configurations, cohort, analysis code, and source manifest together.

Exit condition: one top-level pre-run manifest binds every frozen input, and no confirmatory model
output has been inspected.

### Phase 3: M5 smoke and benchmark

1. Run the strict doctor on the documented M5 Pro.
2. Run four prompts/model end to end without changing scientific parameters other than the declared
   smoke size and shorter continuation.
3. Measure memory, model-load time, generation speed, likelihood speed, and detector speed.
4. Select only engineering batch sizes and worker counts that do not change sampling mathematics.
5. Estimate full runtime and disk use before authorizing the full cohort.

Exit condition: both models fit within 48 GB, reproduce deterministic fixtures, and pass the smoke
validator. A scientific-parameter change returns to Phase 2 with a new protocol hash.

### Phase 4: generate and analyze the full cohort

Run resumable immutable shards in this order:

1. ordinary and SynthID generation for both models;
2. corpus completeness validation;
3. fixed-state sampler checks;
4. teacher-forced model-quality analysis;
5. clean position-independent detection;
6. exactly one substitution, insertion, and deletion;
7. ordinary, independent-key, and public-DNA null analyses; and
8. strict cross-model result validation.

The full cohort is completed before primary results are opened. Engineering failures may be resumed
from byte-identical shards. Any change to scientific parameters requires a new study identity.

### Phase 5: admit evidence

1. Produce compact summaries, trial tables, reports, and recursive SHA-256 manifests.
2. Create stable `synthid.v2.carbon.*`, `synthid.v2.generator.*`, and shared QA identifiers.
3. Record value, unit, uncertainty, sample hierarchy, model/tokenizer revisions, configuration,
   environment, exact command, source commit, and artifact hash for every paper-bound number.
4. Generate a dual-model evidence map with exact identifiers only.
5. Run the strict evidence and release-bundle audits.

Exit condition: every manuscript number can be regenerated from one cited artifact and all gates
have signed, hash-linked receipts.

### Phase 6: rebuild the manuscript

The new manuscript should use this structure:

1. **Abstract** — method, both models, primary quality bounds, detection results, and principal
   limitation. Do not list lint or unit-test details here.
2. **Introduction** — genomic provenance problem, unknown-boundary problem, and the two-model
   contribution.
3. **Related work** — SynthID, Carbon, GENERator, and RefSeq primary sources.
4. **Methods** — model-specific token policies, shared tournament sampler, standalone detector,
   complete-search correction, cohort, keys, draws, and edit model.
5. **Pre-specified acceptance criteria** — the scientific gates and how failure changes claims.
6. **Results** — sampler correctness, non-inferiority, clean detection, single-edit detection,
   false positives, and cross-model replication.
7. **Software and evidence validation** — a concise account of tests, strict validators, linting,
   environment checks, artifact hashing, and evidence checks.
8. **Discussion and limitations** — fixed-key reweighting, statistical uncertainty, public fixture
   keys, one-edit scope, and absence of biological-function evidence.
9. **Data, code, and artifact availability** — portable identifiers, release commit/tag, model and
   cohort revisions, top-level manifest hash, and archive DOI.
10. **Supplement** — complete gate matrix, unit-test categories, commands, environment, artifact
    inventory, and measurement map.

Recommended main tables:

- model revisions, token policies, dtypes, and shared generation settings;
- sampler and quality results for both models;
- position-independent detection by model, read condition, and control family; and
- confidence bounds for the primary true-positive and false-positive endpoints.

Recommended supplementary tables:

- every scientific gate with its frozen rule and outcome;
- every software/evidence gate with command, version, receipt hash, and outcome; and
- every public artifact with its release-relative path and SHA-256 digest.

Unit tests, Ruff, linting, and artifact checks should appear as reproducibility evidence, not as
proof that the watermark is accurate or that generated DNA is biologically sound.

### Phase 7: final paper review

1. Generate tables from the evidence ledger; do not transcribe numbers by hand.
2. Check every printed number and claim against the dual-model evidence map.
3. Build the PDF from the frozen release source.
4. Confirm that the manuscript contains no local paths, host names, raw job IDs, secret material,
   or legacy measurement identifiers.
5. Add a dated review record listing all passed and failed gates.
6. Archive the portable release and record its DOI and top-level digest.

Exit condition: the PDF, evidence ledger, generated tables, code snapshot, and artifact bundle all
resolve to one content-addressed release identity.

## Required release artifacts

The compact release bundle should have this shape:

```text
outputs/synthid_dual_model_confirmatory_v2/
  study_manifest.json
  protocol/
    protocol.md
    gates.yaml
    source_manifest.json
    cohort_manifest.yaml
  environment/
    lock_digest.json
    m5_doctor.json
    benchmark.json
  qa/
    unit_tests.json
    upstream_parity.json
    ruff_lint.json
    ruff_format.json
    schema_checks.json
    release_validation.json
    manuscript_build.json
  carbon/
    generation_summary.json
    sampler_summary.json
    quality_summary.json
    detection_summary.json
    trials.parquet
    report.md
  generator/
    generation_summary.json
    sampler_summary.json
    quality_summary.json
    detection_summary.json
    trials.parquet
    report.md
  evidence/
    measurements.yaml
    manuscript_map.json
  paper/
    generated_tables/
    main.pdf
  artifact_digests.json
```

Raw generated sequences, model weights, cache files, credentials, and raw keys remain outside the
portable repository bundle. The manifest records their approved derived-summary lineage without
publishing disallowed material. Every stored path is release-relative; absolute machine paths are
rejected.

## Completion definition

The rebuild is complete only when:

- both models have new M5-generated evidence under the same frozen study identity;
- both primary quality bounds pass the pre-specified margin;
- the correct-key and null detector gates are evaluated and reported without retuning;
- every required scientific, software, evidence, and manuscript gate has a machine-readable
  receipt;
- every paper number resolves to a new `synthid.v2.*` measurement;
- the manuscript PDF builds from the content-addressed release; and
- old version-one results are absent from the active paper and evidence map.
