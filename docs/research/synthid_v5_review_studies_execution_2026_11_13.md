# SynthID v5 review studies: execution record (local cohort)

**Date:** 2026-11-13. Execution finished on 2026-11-13 at 02:00:40 UTC; Section 9 of the protocol names `synthid_v5_review_studies_execution_2026_11_12.md`, and this record uses the completion date instead. **Namespace:** `synthid.v5.*`. **Status:** complete; results are admitted to `evidence/measurements.yaml` (Section 11). **Protocol:** `docs/research/synthid_v5_review_studies_protocol_2026_11_12.md`, unchanged by this record.

This is a second execution of the same watermark (`synthid-tournament-v1`), ordinary control, and verifier (`synthid-position-independent-detector-v1`) on a locally regenerated cohort, by the same authors with the same code and prompts, in a different computing environment. It is not an independent replication. No verifier setting was tuned in any study. Keys are public fixtures. Nothing here establishes biological function or secret-key security.

Every number in this record is read from the result files by `scripts/derive_synthid_v5_evidence.py` (derived file `evidence/derived/synthid_v5/synthid_v5_derived_2026_11_13.json`). Facts are separated from interpretation; interpretation appears only where the protocol states a rule in advance.

## 1. What ran

| Stage | Scope |
|---|---|
| Generation | Carbon-500M and GENERator-v2 1.2B, 512 evaluated prompts, two draws, SynthID and ordinary arms, 512 tokens (3,072 bases) per sequence, three processes per model |
| S0 | existing position-independent runner and validator, reference layout, 3 families x 4 conditions, both models |
| S1 layout | 54 cells x 2 families x 512 prompts x 2 draws, both models |
| S2 detector comparison | first 256 evaluated prompts, 5 cells x 4 detectors x 2 families, both models; single-process timing on 32 prompts |
| S3 null calibration | 64 null keys; ordinary model output and marked output (512 reads per model), natural DNA (1,608 spans) |
| S4 entropy | one teacher-forced pass over 2,048 sequences per model; Spearman analysis |

## 2. Environment

| Item | Value | Source |
|---|---|---|
| Machine | Apple M5 Pro, 18 cores (6 + 12 by performance level), 48 GiB unified memory, arm64 | `sysctl`, read 2026-11-13 |
| Operating system | macOS 27.2 (build 26B123) | `sw_vers`; session files record `macOS-27.2-arm64-arm-64bit` |
| Python | 3.12.16 | session and study summaries (`provenance.python`) |
| PyTorch | 2.13.0, MPS backend, bfloat16 | S4 entropy summaries (`session.torch_version`); `.venv` read after the run: torch 2.13.0 |
| Other packages (read from `.venv` after the run) | numpy 2.5.2, scipy 1.18.0, transformers 5.15.1, tokenizers 0.22.2 | `.venv/bin/python`; versions were not recorded in the result files |
| Dependency lock | `uv.lock` sha256 `cd5c2c0d23290c734a266775facb287c6399b7d882b32e53f9ef177bc31c9986` | repository file |
| Generation device | mps, bfloat16 | session files |
| Detection and S3 device | CPU, 12 worker processes (single worker for S2 timing) | study summaries (`runtime`, `provenance.workers`) |
| Model weights | offline Hugging Face cache, `HF_HUB_OFFLINE=1`; revisions Carbon `9796b752108258c1d365089f842e62e6c0547704`, GENERator `c41b0018da9ee13b9e96ee54647de8da381ccd72` | generation scripts; study summaries |

Peak resident memory per generation process: GENERator-v2 1.2B 6.94 GiB, Carbon-500M 1.07 GiB (largest session value). Three generation processes shared one MPS device per model.

Weights are not stored in the repository and no key bytes, private sequences, or credentials were written to any result file (`key_bytes_recorded` is false in every S3 summary).

## 3. Inputs and identity gates

| Gate | Expected | Observed | Result |
|---|---|---|---|
| Protocol file sha256 | `49509bc664a5dadfcdddce486a45d4be708da6eae1921424482f6b0cd19de317` (current file) | recorded in every summary: `49509bc664a5dadfcdddce486a45d4be708da6eae1921424482f6b0cd19de317` | match |
| `prompts.jsonl` sha256 | `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775` | current `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775`; recorded in summaries and run identities: `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775` | match |
| Cohort content sha256 | `f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5` | `f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5` | match |
| Evaluated prompts | first 512 held-out in split-rank order | `evaluated_case_ids.txt` sha256 `4a6ea27d2a2fa036069f9fdf874427263dce0cf56a53a947574e5e9dfe02e320`; identical lists in both model roots; re-derived from the cohort and split label: equal | match |
| Prompt split | label `carbon_synthid_validation_v1/prompt-split/v1`; 1608 prompts, 1544 held out | per model: GENERator-v2 1.2B {'evaluation': 512, 'not_evaluated': 1096}; Carbon-500M {'evaluation': 512, 'not_evaluated': 1096} | as written in protocol Section 3 |

The protocol file's current sha256 equals the sha256 recorded in every study summary and run identity (`49509bc664a5dadfcdddce486a45d4be708da6eae1921424482f6b0cd19de317`).

## 4. Commands

Generation, per model, from the repository root (as reported by the operator; the per-process invocations are recorded in the session files and logs):

```bash
scripts/local/run_synthid_v5_generation.sh generator
scripts/local/run_synthid_v5_generation.sh carbon
```

Inside the script each of three processes per model ran draw 0 and then draw 1 over its own disjoint third of the 512 prompts (every third line of `evaluated_case_ids.txt`). Recorded command of one session, with its 171 `--case-id` arguments elided and absolute paths shortened:

```bash
.venv/bin/python scripts/run_generator_large_generation.py \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl \
  --draw-index 0 \
  --steps 512 \
  --experiment-label generator-synthid-local-v5 \
  --experiment-id generator_synthid_v5_local_generation \
  --tournament-depth 30 \
  --context-tokens 4 \
  --context-history-size 1024 \
  --device mps \
  --dtype bfloat16 \
  --cache-dir .cache/huggingface \
  --local-files-only \
  --output-root outputs/synthid_v5_local/generator/parts/p0 \
  --case-id ... 
```

Studies, run unattended by `scripts/local/run_synthid_v5_overnight.sh`, which waits for 1,024 generation shards per model and then calls:

```bash
scripts/local/run_synthid_v5_studies.sh detect generator   > outputs/synthid_v5_local/logs/detect_generator.log
scripts/local/run_synthid_v5_studies.sh detect carbon      > outputs/synthid_v5_local/logs/detect_carbon.log
scripts/local/run_synthid_v5_studies.sh final              > outputs/synthid_v5_local/logs/final.log
```

`detect <model>` collects the shards unchanged into `<model>/merged/`, finalizes generation with the existing script (`--finalize-only --expected-case-count 512`), writes `detection/prompt_split.json`, runs S0 (the existing runner and strict validator, `--experiment-id <model>_synthid_v5_local_position_independent`, `--workers 12`), S1 (`scripts/run_synthid_v5_layout.py`), S2 (`scripts/run_synthid_v5_detector_comparison.py --prompts 256`), and the two model-output S3 families (`scripts/run_synthid_v5_null_calibration.py --family ordinary_model_output` and `marked_independent_key`). `final` runs S3 natural DNA, the S4 entropy pass (`scripts/run_synthid_v5_entropy.py --device mps --dtype bfloat16`), the S4 analysis (`scripts/analyze_synthid_v5_entropy.py`), and the single-process S2 timing (`--timing-only --prompts 32`, run last). The full argument lists are in the shell scripts, whose sha256 are in Section 6, and in each study summary's `provenance.command`.

Derivation and admission commands (this record):

```bash
PYTHONPATH=src .venv/bin/python scripts/derive_synthid_v5_evidence.py
.venv/bin/python scripts/emit_synthid_v5_ledger.py --verify
.venv/bin/python scripts/emit_synthid_v5_ledger.py --append
python3 scripts/check_evidence.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

## 5. Timeline (UTC)

| Stage | Start | End | Elapsed |
|---|---|---|---|
| GENERator-v2 1.2B generation | 2026-11-12 15:11:00 | 2026-11-12 18:13:48 | 3h 02m 49s |
| Carbon-500M generation | 2026-11-12 18:13:49 | 2026-11-13 00:51:07 | 6h 37m 19s |
| generator: collect shards | 2026-11-12 18:15:37 | 2026-11-12 18:15:41 | 0h 00m 04s |
| generator: finalize generation | 2026-11-12 18:15:41 | 2026-11-12 18:15:41 | 0h 00m 00s |
| generator: S0 verifier on the reference layout | 2026-11-12 18:15:41 | 2026-11-12 18:18:08 | 0h 02m 27s |
| generator: S1 layout study | 2026-11-12 18:18:08 | 2026-11-12 18:39:45 | 0h 21m 37s |
| generator: S2 detector comparison | 2026-11-12 18:39:45 | 2026-11-12 18:58:22 | 0h 18m 37s |
| generator: S3 null calibration, ordinary_model_output | 2026-11-12 18:58:22 | 2026-11-12 19:03:03 | 0h 04m 41s |
| generator: S3 null calibration, marked_independent_key | 2026-11-12 19:03:03 | 2026-11-12 19:07:36 | 0h 04m 33s |
| carbon: collect shards | 2026-11-13 00:51:40 | 2026-11-13 00:51:42 | 0h 00m 02s |
| carbon: finalize generation | 2026-11-13 00:51:42 | 2026-11-13 00:51:43 | 0h 00m 01s |
| carbon: S0 verifier on the reference layout | 2026-11-13 00:51:43 | 2026-11-13 00:53:33 | 0h 01m 50s |
| carbon: S1 layout study | 2026-11-13 00:53:33 | 2026-11-13 01:06:37 | 0h 13m 04s |
| carbon: S2 detector comparison | 2026-11-13 01:06:37 | 2026-11-13 01:18:45 | 0h 12m 08s |
| carbon: S3 null calibration, ordinary_model_output | 2026-11-13 01:18:45 | 2026-11-13 01:21:40 | 0h 02m 55s |
| carbon: S3 null calibration, marked_independent_key | 2026-11-13 01:21:40 | 2026-11-13 01:24:38 | 0h 02m 58s |
| S3 null calibration, natural DNA | 2026-11-13 01:24:38 | 2026-11-13 01:32:36 | 0h 07m 58s |
| generator: S4 entropy pass | 2026-11-13 01:32:36 | 2026-11-13 01:35:44 | 0h 03m 08s |
| carbon: S4 entropy pass | 2026-11-13 01:35:44 | 2026-11-13 01:37:32 | 0h 01m 48s |
| S4 analysis | 2026-11-13 01:37:32 | 2026-11-13 01:37:50 | 0h 00m 18s |
| generator: S2 single-process timing | 2026-11-13 01:37:50 | 2026-11-13 01:48:47 | 0h 10m 57s |
| carbon: S2 single-process timing | 2026-11-13 01:48:47 | 2026-11-13 02:00:40 | 0h 11m 53s |

Overall: first generation process started 2026-11-12 15:11:00, final stage ended 2026-11-13 02:00:40: 10h 49m 40s. Generation start times are the process start stamps in the log file names (second resolution). Stage end times are the start of the next logged stage; the last stage ends at the `final stage done` stamp. While Carbon generated (18:13:49 to 00:51:07), the GENERator studies ran on the same CPU, which affects wall time only; the S2 timing runs were last and single-process.

In the session files the field `started_utc` is the session end, not its start: start stamp from the log file name, plus `wall_seconds`, equals `started_utc` to within 1.04 s for every draw-0 session (the draw-1 sessions begin where draw 0 of the same process ended). Recorded as observed; no file was changed.

## 6. Code digests and git state

Git state when this record was written: HEAD `787ab9c` ("Add comprehensive unit tests for SynthID v5 null calibration", committed 2026-11-12T17:30:31+02:00); tracked files unmodified; the scripts `scripts/local/run_synthid_v5_overnight.sh` and `scripts/local/run_synthid_v5_studies.sh` untracked.

State at run time, from `git reflog` and file times: the branch pointed at `6354716` when generation started (2026-11-12 15:11:00 UTC, with the v5 code and the protocol present but uncommitted); commit `787ab9c` was made at 2026-11-12 15:30:31 UTC, 19 minutes into generation, and contains the protocol, the S1 to S4 code, `src/genomic_watermarks/review_layouts.py`, `src/genomic_watermarks/detector_baselines.py`, the generation script, and tests. The study stage (from 2026-11-12 18:15:37 UTC) therefore ran with HEAD `787ab9c` plus the two untracked shell scripts. Between `6354716` and `787ab9c` no existing file under `src/`, `scripts/`, `tests/`, or `configs/` changed: `git diff --name-status 6354716 787ab9c -- src scripts tests configs` lists 13 files, all added (`A`). The generation code (`run_*_large_generation.py`, the `src/genomic_watermarks` modules it imports) is therefore byte-identical at both commits.

The study summaries hold `code_sha256`; every recorded digest equals the sha256 of the current file of the same path (column `matches summaries`). Generation and summarize scripts are not hashed in the session files; their current digests and the commit that last changed them are given.

| File | sha256 (current) | matches summaries | git | last commit |
|---|---|---|---|---|
| `scripts/analyze_synthid_v5_entropy.py` | `9bd4868bcc52b3d041a0daf1100e5c9313bf378fa3f518aaf8c417551c205ae8` | yes | clean | 787ab9c |
| `scripts/local/run_synthid_v5_generation.sh` | `25a5d0c71896aeb3333c0a8d12ff32f96cff057eb6173fae4f49bd88d6f02e8b` | not recorded | clean | 787ab9c |
| `scripts/local/run_synthid_v5_overnight.sh` | `d132f8d49a8efabbc9adc476457fa58678ab452a62543d992801278e1fbb787b` | not recorded | untracked | n/a |
| `scripts/local/run_synthid_v5_studies.sh` | `6e5de967480252791cefff7e2f1791c634d734c365daf5d9df3734313e8e4426` | not recorded | untracked | n/a |
| `scripts/run_carbon_large_generation.py` | `b595d6a820302271f99998b8acb133e893b5280fd45029fb8e40e90bc44c20da` | not recorded | clean | 8a3878d |
| `scripts/run_carbon_synthid_position_independent.py` | `9556b9c3bd14a1fa9892427965a5fa2e9cfad9a4ab23e4262785234175560e02` | yes | clean | 8a3878d |
| `scripts/run_generator_large_generation.py` | `5247d8012189d2028cc192de4365cefb700666749d9e4364ebbdb9bc7bb83744` | not recorded | clean | 8a3878d |
| `scripts/run_generator_synthid_position_independent.py` | `88d3e41a88fce41a1d4196954bf33da0e5f711384d262155f47d50163d47e1bc` | yes | clean | 8a3878d |
| `scripts/run_synthid_v5_detector_comparison.py` | `a28f5112c72c97a98882671fdce7aacf77c5a38a69c20e75eb93b6ea6717fdf4` | yes | clean | 787ab9c |
| `scripts/run_synthid_v5_entropy.py` | `6b155ffd13649b32898303e91f19c84578254deb70ff4685cd3da6b5af26e44c` | yes | clean | 787ab9c |
| `scripts/run_synthid_v5_layout.py` | `502cb5100b6fddb9ae3a30c37985cfcc17f670ee868087c0b299208d3b515123` | yes | clean | 787ab9c |
| `scripts/run_synthid_v5_null_calibration.py` | `af3f081e373da5ed56951dd8aa863d921373ce828713ed5448d6c4744395487f` | yes | clean | 787ab9c |
| `scripts/summarize_carbon_large_generation.py` | `6ad5db1e0c1f06a9391db466a6194e6bba196ac368e002f09a3904a6b0cc8472` | not recorded | clean | 8a3878d |
| `scripts/summarize_generator_large_generation.py` | `391311d09e9184fa8b2d37688f46f00eeca3edcc696ef106ab5dd9e49b6a28f1` | not recorded | clean | 8a3878d |
| `scripts/validate_carbon_synthid_position_independent.py` | `54a719a8f29db42dd4d5b1f7a5619c0a345174fd1d2ecec44034c4760f9032e4` | yes | clean | 8a3878d |
| `scripts/validate_generator_synthid_position_independent.py` | `c5fb393f542b0e81c34faf437f85f5a6ec33b8d12173f179b07fe5ec9bb265a7` | yes | clean | 8a3878d |
| `src/genomic_watermarks/detector_baselines.py` | `5bc1cf5f158aec21c6fd8194c29504d0b5cf796082d65997bdf9ae2e673945f6` | yes | clean | 787ab9c |
| `src/genomic_watermarks/dna.py` | `2deec679760f8bdfcb3cd7f9bb8a6456e9bdcf9745a38719ca5102d18d3ff4c7` | yes | clean | ad3801f |
| `src/genomic_watermarks/large_validation.py` | `9b0d7ee95575de350f6db573ca1a245eaaa59ad6e261903dff2e2960171264c2` | yes | clean | 4602fc1 |
| `src/genomic_watermarks/models/huggingface.py` | `ec372c3c7fb72121efe0b7626fd290ba66b920a4296ad6782af026e64d3f0eb7` | yes | clean | 2dea3a9 |
| `src/genomic_watermarks/models/policy_math.py` | `fc1aa001a1664b9e6c7466e74ea73f2bb471af156107f91303f2065b6df6d5e6` | yes | clean | 4602fc1 |
| `src/genomic_watermarks/models/runtime.py` | `ab6d6d3e3eed1cd27b7259ad7b01022314e98b3562f3e8fc7fefe9d59464ef3f` | yes | clean | 4602fc1 |
| `src/genomic_watermarks/models/vocabulary.py` | `45a992cc39d52584bd1817e9c840618603ed1418d8123a4f20607fe620d5139b` | yes | clean | ad3801f |
| `src/genomic_watermarks/pilot.py` | `28930af5169e6318e0a3b312d104315329ca5e3e115af7e514bf93321af4859b` | yes | clean | 4602fc1 |
| `src/genomic_watermarks/review_layouts.py` | `f74e36264f795a7558df6e777a886e068a43617b70872b078d29d14df7a3b86f` | yes | clean | 787ab9c |
| `src/genomic_watermarks/synthid.py` | `a50fa22c451548e901c75d59b0e6583d9e9015fd6e414cf379d57c7258933082` | yes | clean | 4602fc1 |
| `src/genomic_watermarks/synthid_boundary.py` | `d9193912afa4257a05f0595138be8e3fffd0b223649a281eff81ff0202626270` | yes | clean | 8a3878d |
| `src/genomic_watermarks/synthid_position_independent.py` | `db7a0116281d8c07b46b7c6c6196907526578480a22eb2ab6c55a9260f78c901` | yes | clean | 4602fc1 |
| `src/genomic_watermarks/watermark.py` | `96f881bb9486753af6a38e1a1875f97cee116caa51892b7825ae5bfdef552853` | yes | clean | 4602fc1 |

## 7. Validity checks and admission gates

| Model | Check | Observed | Result |
|---|---|---|---|
| GENERator-v2 1.2B | S0 strict validator (log line) | `{"decisions": 12288, "experiment_id": "generator_synthid_v5_local_position_independent", "prompts": 512, "rate_cells": 12, "status": "ok"}` | pass |
| GENERator-v2 1.2B | WARNING, FAILED, or Traceback lines in the detect log | 0 | pass |
| GENERator-v2 1.2B | S1 check 1: Series A at l = 3,072 reproduces the S0 unedited decisions | 2048 compared, 0 mismatches, max |log P difference| 0.0 | pass |
| GENERator-v2 1.2B | S1 check 2: Series C read and reverse complement agree | 24576 pairs, 0 mismatches, 0 unpaired | pass |
| GENERator-v2 1.2B | S1 summary `valid`, `validity_failures` | True, [] | pass |
| Carbon-500M | S0 strict validator (log line) | `{"decisions": 12288, "experiment_id": "carbon_synthid_v5_local_position_independent", "prompts": 512, "rate_cells": 12, "status": "ok"}` | pass |
| Carbon-500M | WARNING, FAILED, or Traceback lines in the detect log | 0 | pass |
| Carbon-500M | S1 check 1: Series A at l = 3,072 reproduces the S0 unedited decisions | 2048 compared, 0 mismatches, max |log P difference| 0.0 | pass |
| Carbon-500M | S1 check 2: Series C read and reverse complement agree | 24576 pairs, 0 mismatches, 0 unpaired | pass |
| Carbon-500M | S1 summary `valid`, `validity_failures` | True, [] | pass |
| both | WARNING lines in `final.log` | 0 | pass |
| both | trials digests stored in summaries equal the files | 9 artifacts checked | pass |

Protocol Section 9 gates admission on S0 completing, Section 5 checks 1 and 2 passing, digests being recorded, and `scripts/check_evidence.py` and the unit tests passing. The first three hold for both models. The last two are reported in Section 11.

## 8. Deviations and disclosures

Items 1, 2, 5, 7, 8, 10, and 11 were checked against files and logs. Items 3, 6, and 9, and the reasons for the code fixes in item 4, are statements by the operator that the repository files cannot confirm.

1. **Prompt split file.** `detection/prompt_split.json` in each merged root marks the 512 evaluated prompts `evaluation` and all other prompts, including the 64 reserved, `not_evaluated` (protocol Section 3). Counts above.
2. **Session file names.** The session records of the three parts were copied into `merged/generation/sessions/` with the part name inserted (`draw_00_session_p0_...`), because Carbon numbers its sessions per directory. Shards were copied byte for byte and compared with `cmp` when already present.
3. **Smoke test, not a result.** Before the real run a 6-prompt smoke test of the pipeline ran in a scratch directory on real GENERator shards. Only validity flags were inspected; no setting was changed; its outputs are not results and are not in `outputs/synthid_v5_local`. An earlier reviewer agent also pushed one real shard through the S1 and S2 code, read-only.
4. **Code fixes before any study ran on real sequences.** After the protocol was written, the study code was reviewed and fixed (gzip reader, required S0 check, integer-based check 1, read-level interval labelling, write-once outputs). Files `run_synthid_v5_layout.py`, `run_synthid_v5_null_calibration.py`, and `run_synthid_v5_detector_comparison.py` were last modified at 15:23, 15:22, and 15:20 UTC on 2026-11-12 (file times), after generation started and before the first study ran (the first detect stage began 18:15:37 UTC); the digests in Section 6 are those of the files the studies recorded.
5. **Shared CPU.** GENERator studies ran while Carbon generated; this affects wall time only. S2 timing was run last, single-process, in the `final` stage.
6. **Launch commands.** The invocation of the generation scripts and of the overnight script is not recorded in the logs; the commands in Section 4 are as reported.
7. **S1 control check (protocol Section 5, rule 3).** Observed values are in Section 9 (S1): the read-level ordinary rate never exceeds 1% in any of the 54 cells of either model; the prompt-level any-draw count exceeds 1% in GENERator-v2 1.2B cell `A_l0384` (6 of 512). A prompt is positive if either of two reads is, so the any-draw rate is a union over two reads. The study summaries' own `control_rate_above_target` flag is read-level and is false in every cell. Both views are reported; neither is dropped.
8. **Session timestamp field.** `started_utc` holds the session end (Section 5).
9. **S4 numerical cross-check.** The cross-check of the entropy alignment against the sampling path is being done separately and is not part of this record; the S4 summaries record `crosscheck_nll: false`. See the marked line in Section 9 (S4).
10. **Benchmark directory.** `outputs/local_mps_benchmark_2026_11_12/` holds the timing benchmark the protocol cites under the label `local-mps-benchmark-2026-11-12`. No detector was run on its output and none of it is used here.
11. **Package versions.** The result files record Python 3.12.16 and, in the S4 summaries, PyTorch 2.13.0; the other package versions in Section 2 were read from the `.venv` after the run.
12. **Not a replication.** Same authors, same code, same prompts, new keys and seeds, different machine.

## 9. Results

### S0: reference layout

Reference layout: the 384-base prompt followed by the 3,072-base continuation. Prompt-level positives count a prompt when either draw is detected ('any'); prompts detected on both draws are also given. One-sided upper bounds are exact, `Beta^-1(0.95; k + 1, 512 - k)`, recomputed by the derivation script. Strength is the median of -log10 of the smallest window P-value (uncorrected for the search), computed from the S0 trials file. The four-length window set is searched with 16,128 to 16,144 hypotheses per read (16,136 for unedited and substituted reads).

**GENERator-v2 1.2B** (`synthid.v5.generator.detector.*`)

| Condition | Family | Reads | Prompts, any draw | Two-sided 95% | One-sided 95% upper | Prompts, both draws | Median strength | Winning window length: reads |
|---|---|---|---|---|---|---|---|---|
| clean | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 797.4 | 3072: 1024 |
| clean | ordinary_corresponding_key | 0/1024 | 0/512 | [0.00, 0.72]% | 0.583% | 0/512 | 3.2 | 384: 709, 768: 224, 1536: 80, 3072: 11 |
| clean | watermarked_wrong_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.1 | 384: 713, 768: 229, 1536: 71, 3072: 11 |
| substitution_1nt | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 780.7 | 3072: 1024 |
| substitution_1nt | ordinary_corresponding_key | 0/1024 | 0/512 | [0.00, 0.72]% | 0.583% | 0/512 | 3.2 | 384: 707, 768: 220, 1536: 85, 3072: 12 |
| substitution_1nt | watermarked_wrong_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 716, 768: 219, 1536: 79, 3072: 10 |
| insertion_1nt | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 450.9 | 1536: 444, 3072: 580 |
| insertion_1nt | ordinary_corresponding_key | 0/1024 | 0/512 | [0.00, 0.72]% | 0.583% | 0/512 | 3.2 | 384: 698, 768: 225, 1536: 93, 3072: 8 |
| insertion_1nt | watermarked_wrong_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 705, 768: 225, 1536: 81, 3072: 13 |
| deletion_1nt | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 437.5 | 1536: 465, 3072: 559 |
| deletion_1nt | ordinary_corresponding_key | 1/1024 | 1/512 | [0.00, 1.08]% | 0.923% | 0/512 | 3.2 | 384: 712, 768: 216, 1536: 83, 3072: 13 |
| deletion_1nt | watermarked_wrong_key | 1/1024 | 1/512 | [0.00, 1.08]% | 0.923% | 0/512 | 3.1 | 384: 717, 768: 216, 1536: 77, 3072: 14 |

**Carbon-500M** (`synthid.v5.carbon.detector.*`)

| Condition | Family | Reads | Prompts, any draw | Two-sided 95% | One-sided 95% upper | Prompts, both draws | Median strength | Winning window length: reads |
|---|---|---|---|---|---|---|---|---|
| clean | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 791.5 | 1536: 1, 3072: 1023 |
| clean | ordinary_corresponding_key | 3/1024 | 3/512 | [0.12, 1.70]% | 1.507% | 0/512 | 3.2 | 384: 701, 768: 232, 1536: 75, 3072: 16 |
| clean | watermarked_wrong_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 697, 768: 245, 1536: 75, 3072: 7 |
| substitution_1nt | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 775.8 | 1536: 1, 3072: 1023 |
| substitution_1nt | ordinary_corresponding_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 696, 768: 241, 1536: 75, 3072: 12 |
| substitution_1nt | watermarked_wrong_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 698, 768: 241, 1536: 76, 3072: 9 |
| insertion_1nt | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 444.3 | 1536: 448, 3072: 576 |
| insertion_1nt | ordinary_corresponding_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 709, 768: 222, 1536: 79, 3072: 14 |
| insertion_1nt | watermarked_wrong_key | 1/1024 | 1/512 | [0.00, 1.08]% | 0.923% | 0/512 | 3.2 | 384: 700, 768: 252, 1536: 60, 3072: 12 |
| deletion_1nt | watermarked_correct_key | 1024/1024 | 512/512 | [99.28, 100.00]% | 100.000% | 512/512 | 437.4 | 768: 1, 1536: 466, 3072: 557 |
| deletion_1nt | ordinary_corresponding_key | 2/1024 | 2/512 | [0.05, 1.40]% | 1.224% | 0/512 | 3.2 | 384: 702, 768: 240, 1536: 69, 3072: 13 |
| deletion_1nt | watermarked_wrong_key | 1/1024 | 1/512 | [0.00, 1.08]% | 0.923% | 0/512 | 3.2 | 384: 694, 768: 242, 1536: 77, 3072: 11 |

At 512 prompts the exact one-sided upper bound is 0.583% for 0 positive prompts, 0.923% for 1 positive prompts, 1.224% for 2 positive prompts, 1.507% for 3 positive prompts. It is below 1% only with at most one positive prompt. Control rows with two or more positive prompts have an upper bound above 1%; they are reported as observed, with no claim that the 1% operational rate was established for those families (as in the detection cohort).

- GENERator-v2 1.2B: correct-key reads detected clean 1024/1024, substitution_1nt 1024/1024, insertion_1nt 1024/1024, deletion_1nt 1024/1024; 3 of 8 control rows have a prompt-level upper bound above 1% (clean watermarked_wrong_key: 2 prompts; substitution_1nt watermarked_wrong_key: 2 prompts; insertion_1nt watermarked_wrong_key: 2 prompts); largest control read-level count 2/1,024.

- Carbon-500M: correct-key reads detected clean 1024/1024, substitution_1nt 1024/1024, insertion_1nt 1024/1024, deletion_1nt 1024/1024; 6 of 8 control rows have a prompt-level upper bound above 1% (clean ordinary_corresponding_key: 3 prompts; clean watermarked_wrong_key: 2 prompts; substitution_1nt ordinary_corresponding_key: 2 prompts; substitution_1nt watermarked_wrong_key: 2 prompts; insertion_1nt ordinary_corresponding_key: 2 prompts; deletion_1nt ordinary_corresponding_key: 2 prompts); largest control read-level count 3/1,024.

### S1: layout study

54 cells per model. Marked: reads detected of 1,024, prompts detected on both draws of 512, median strength (-log10 of the smallest window P-value). Ordinary control: reads positive of 1,024 (read-level), prompts positive on either draw of 512 (any-draw), and the exact one-sided 95% upper bound on the any-draw prompt rate. Series and cells as in protocol Section 5: A suffix length, B embedded length, C phase and strand (`o` offset, `fw` or `rc`), D flank length, E placement, F cropping. Exact two-sided intervals per cell are in the compact summaries.

**GENERator-v2 1.2B** (`synthid.v5.generator.s1.series_a.marked_detection` to `series_f`, and `ordinary_control`)

| Cell | Marked reads | Marked prompts, both draws | Median strength | Ordinary reads | Ordinary prompts, any draw | One-sided 95% upper |
|---|---|---|---|---|---|---|
| `A_l0384` | 1023/1024 | 511/512 | 94.00 | 6/1024 | 6/512 | 2.30% |
| `A_l0576` | 1023/1024 | 511/512 | 106.50 | 5/1024 | 5/512 | 2.04% |
| `A_l0768` | 1023/1024 | 511/512 | 194.84 | 3/1024 | 3/512 | 1.51% |
| `A_l1152` | 1024/1024 | 512/512 | 216.14 | 3/1024 | 3/512 | 1.51% |
| `A_l1536` | 1024/1024 | 512/512 | 394.54 | 1/1024 | 1/512 | 0.92% |
| `A_l2304` | 1024/1024 | 512/512 | 409.89 | 1/1024 | 1/512 | 0.92% |
| `A_l3072` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `B_l0384` | 1023/1024 | 511/512 | 94.00 | 0/1024 | 0/512 | 0.58% |
| `B_l0576` | 1023/1024 | 511/512 | 110.43 | 3/1024 | 3/512 | 1.51% |
| `B_l0768` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `B_l1152` | 1024/1024 | 512/512 | 223.69 | 2/1024 | 2/512 | 1.22% |
| `B_l1536` | 1024/1024 | 512/512 | 394.54 | 1/1024 | 1/512 | 0.92% |
| `B_l2304` | 1024/1024 | 512/512 | 448.71 | 1/1024 | 1/512 | 0.92% |
| `B_l3072` | 1024/1024 | 512/512 | 797.42 | 1/1024 | 1/512 | 0.92% |
| `C_l0768_o0_fw` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `C_l0768_o0_rc` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `C_l0768_o1_fw` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o1_rc` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o2_fw` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o2_rc` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o3_fw` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o3_rc` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o4_fw` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `C_l0768_o4_rc` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `C_l0768_o5_fw` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o5_rc` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o0_fw` | 1024/1024 | 512/512 | 797.42 | 1/1024 | 1/512 | 0.92% |
| `C_l3072_o0_rc` | 1024/1024 | 512/512 | 797.42 | 1/1024 | 1/512 | 0.92% |
| `C_l3072_o1_fw` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o1_rc` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o2_fw` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o2_rc` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o3_fw` | 1024/1024 | 512/512 | 797.42 | 1/1024 | 1/512 | 0.92% |
| `C_l3072_o3_rc` | 1024/1024 | 512/512 | 797.42 | 1/1024 | 1/512 | 0.92% |
| `C_l3072_o4_fw` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o4_rc` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o5_fw` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `C_l3072_o5_rc` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `D_l0768_f0000` | 1023/1024 | 511/512 | 194.84 | 3/1024 | 3/512 | 1.51% |
| `D_l0768_f0384` | 1023/1024 | 511/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `D_l0768_f1536` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `D_l0768_f4608` | 1023/1024 | 511/512 | 194.84 | 0/1024 | 0/512 | 0.58% |
| `D_l3072_f0000` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `D_l3072_f0384` | 1024/1024 | 512/512 | 797.42 | 0/1024 | 0/512 | 0.58% |
| `D_l3072_f1536` | 1024/1024 | 512/512 | 797.42 | 2/1024 | 2/512 | 1.22% |
| `D_l3072_f4608` | 1024/1024 | 512/512 | 797.42 | 1/1024 | 1/512 | 0.92% |
| `E_s0000` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `E_s1344` | 1023/1024 | 511/512 | 194.84 | 0/1024 | 0/512 | 0.58% |
| `E_s2688` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `E_s4032` | 1023/1024 | 511/512 | 194.84 | 1/1024 | 1/512 | 0.92% |
| `E_s5376` | 1023/1024 | 511/512 | 194.84 | 0/1024 | 0/512 | 0.58% |
| `F_c0768` | 1023/1024 | 511/512 | 105.67 | 5/1024 | 5/512 | 2.04% |
| `F_c1536` | 1024/1024 | 512/512 | 211.08 | 2/1024 | 2/512 | 1.22% |
| `F_c2304` | 1024/1024 | 512/512 | 409.66 | 0/1024 | 0/512 | 0.58% |

**Carbon-500M** (`synthid.v5.carbon.s1.series_a.marked_detection` to `series_f`, and `ordinary_control`)

| Cell | Marked reads | Marked prompts, both draws | Median strength | Ordinary reads | Ordinary prompts, any draw | One-sided 95% upper |
|---|---|---|---|---|---|---|
| `A_l0384` | 1024/1024 | 512/512 | 94.91 | 3/1024 | 3/512 | 1.51% |
| `A_l0576` | 1024/1024 | 512/512 | 106.83 | 3/1024 | 3/512 | 1.51% |
| `A_l0768` | 1024/1024 | 512/512 | 194.61 | 5/1024 | 5/512 | 2.04% |
| `A_l1152` | 1024/1024 | 512/512 | 216.47 | 5/1024 | 5/512 | 2.04% |
| `A_l1536` | 1024/1024 | 512/512 | 394.08 | 4/1024 | 4/512 | 1.78% |
| `A_l2304` | 1024/1024 | 512/512 | 408.73 | 3/1024 | 3/512 | 1.51% |
| `A_l3072` | 1024/1024 | 512/512 | 791.52 | 3/1024 | 3/512 | 1.51% |
| `B_l0384` | 1023/1024 | 511/512 | 94.91 | 3/1024 | 3/512 | 1.51% |
| `B_l0576` | 1024/1024 | 512/512 | 110.76 | 2/1024 | 2/512 | 1.22% |
| `B_l0768` | 1024/1024 | 512/512 | 194.38 | 0/1024 | 0/512 | 0.58% |
| `B_l1152` | 1024/1024 | 512/512 | 223.35 | 1/1024 | 1/512 | 0.92% |
| `B_l1536` | 1024/1024 | 512/512 | 394.08 | 0/1024 | 0/512 | 0.58% |
| `B_l2304` | 1024/1024 | 512/512 | 446.73 | 1/1024 | 1/512 | 0.92% |
| `B_l3072` | 1024/1024 | 512/512 | 791.52 | 1/1024 | 1/512 | 0.92% |
| `C_l0768_o0_fw` | 1024/1024 | 512/512 | 194.38 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o0_rc` | 1024/1024 | 512/512 | 194.38 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o1_fw` | 1024/1024 | 512/512 | 194.38 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o1_rc` | 1024/1024 | 512/512 | 194.38 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o2_fw` | 1024/1024 | 512/512 | 194.61 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o2_rc` | 1024/1024 | 512/512 | 194.61 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o3_fw` | 1024/1024 | 512/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o3_rc` | 1024/1024 | 512/512 | 194.84 | 2/1024 | 2/512 | 1.22% |
| `C_l0768_o4_fw` | 1024/1024 | 512/512 | 194.61 | 5/1024 | 5/512 | 2.04% |
| `C_l0768_o4_rc` | 1024/1024 | 512/512 | 194.61 | 5/1024 | 5/512 | 2.04% |
| `C_l0768_o5_fw` | 1024/1024 | 512/512 | 194.61 | 4/1024 | 4/512 | 1.78% |
| `C_l0768_o5_rc` | 1024/1024 | 512/512 | 194.61 | 4/1024 | 4/512 | 1.78% |
| `C_l3072_o0_fw` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o0_rc` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o1_fw` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o1_rc` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o2_fw` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o2_rc` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o3_fw` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o3_rc` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o4_fw` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o4_rc` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o5_fw` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `C_l3072_o5_rc` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `D_l0768_f0000` | 1024/1024 | 512/512 | 194.38 | 4/1024 | 4/512 | 1.78% |
| `D_l0768_f0384` | 1024/1024 | 512/512 | 194.38 | 4/1024 | 4/512 | 1.78% |
| `D_l0768_f1536` | 1024/1024 | 512/512 | 194.84 | 3/1024 | 3/512 | 1.51% |
| `D_l0768_f4608` | 1024/1024 | 512/512 | 194.61 | 1/1024 | 1/512 | 0.92% |
| `D_l3072_f0000` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `D_l3072_f0384` | 1024/1024 | 512/512 | 791.52 | 2/1024 | 2/512 | 1.22% |
| `D_l3072_f1536` | 1024/1024 | 512/512 | 791.52 | 0/1024 | 0/512 | 0.58% |
| `D_l3072_f4608` | 1024/1024 | 512/512 | 791.52 | 1/1024 | 1/512 | 0.92% |
| `E_s0000` | 1024/1024 | 512/512 | 194.61 | 1/1024 | 1/512 | 0.92% |
| `E_s1344` | 1024/1024 | 512/512 | 194.61 | 3/1024 | 3/512 | 1.51% |
| `E_s2688` | 1024/1024 | 512/512 | 194.61 | 2/1024 | 2/512 | 1.22% |
| `E_s4032` | 1024/1024 | 512/512 | 194.61 | 4/1024 | 4/512 | 1.78% |
| `E_s5376` | 1024/1024 | 512/512 | 194.61 | 0/1024 | 0/512 | 0.58% |
| `F_c0768` | 1024/1024 | 512/512 | 105.19 | 3/1024 | 3/512 | 1.51% |
| `F_c1536` | 1024/1024 | 512/512 | 212.50 | 3/1024 | 3/512 | 1.51% |
| `F_c2304` | 1024/1024 | 512/512 | 407.81 | 3/1024 | 3/512 | 1.51% |

**S1 control rule and marked rates (facts)**

- GENERator-v2 1.2B: ordinary read-level maximum 6/1,024 = 0.586% in `A_l0384`; no cell has a read-level rate above 1%. Prompt-level any-draw rate above 1%: `A_l0384` 6/512 = 1.172% (one-sided 95% upper 2.30%); the next largest any-draw rate is 5/512. Marked reads: lowest cell rate 1023/1,024 = 99.902%; 28 of 54 cells have one missed marked read (one read, one prompt on both draws). The exact one-sided 95% upper bound on the any-draw ordinary prompt rate exceeds 1% in 20 of 54 cells (it does whenever two or more of 512 prompts are positive).

- Carbon-500M: ordinary read-level maximum 5/1,024 = 0.488% in `A_l0768`, `A_l1152`, `C_l0768_o4_fw`, `C_l0768_o4_rc`; no cell has a read-level rate above 1%. No cell has a prompt-level any-draw rate above 1% (maximum 5/512 = 0.977%). Marked reads: lowest cell rate 1023/1,024 = 99.902%; 1 of 54 cells have one missed marked read (one read, one prompt on both draws). The exact one-sided 95% upper bound on the any-draw ordinary prompt rate exceeds 1% in 44 of 54 cells (it does whenever two or more of 512 prompts are positive).

- Cells with one missed marked read: GENERator `A_l0384`, `A_l0576`, `A_l0768`, `B_l0384`, `B_l0576`, `B_l0768`, `C_l0768_o0_fw`, `C_l0768_o0_rc`, `C_l0768_o1_fw`, `C_l0768_o1_rc`, `C_l0768_o2_fw`, `C_l0768_o2_rc`, `C_l0768_o3_fw`, `C_l0768_o3_rc`, `C_l0768_o4_fw`, `C_l0768_o4_rc`, `C_l0768_o5_fw`, `C_l0768_o5_rc`, `D_l0768_f0000`, `D_l0768_f0384`, `D_l0768_f1536`, `D_l0768_f4608`, `E_s0000`, `E_s1344`, `E_s2688`, `E_s4032`, `E_s5376`, `F_c0768`; Carbon `B_l0384`.

**S1 interpretation by the pre-declared rules**

- Rule 1 (Series A at l = 3,072 reproduces the S0 unedited decisions exactly): passes for both models (Section 7).
- Rule 2 (a Series C read and its reverse complement agree): passes for both models (Section 7).
- Rule 3 (ordinary rate at or below 1% in every cell): holds at read level in every cell of both models. At prompt level the cells above 1% as an any-draw union are: GENERator-v2 1.2B `A_l0384`; the marked rate of such a cell carries that caveat. Reported as observed.
- Rule 4 (no pass threshold for marked rates): the rates above are the result.
- Rule 5 (no cell added, dropped, or redefined): 54 cells per model were run and are all reported.

### S2: detector comparison

First 256 evaluated prompts, both draws. All detectors use the same window statistic and the same 0.01 sequence-level target, each corrected for its own search. Marked: reads detected of 512, prompts detected on both draws of 256, median corrected strength (-log10 of the sequence-level P-value before capping at 1; negative means a corrected P above 1). Ordinary: reads positive of 512, prompts positive on either draw of 256, one-sided 95% upper bound on that prompt rate, median corrected strength. Windows: number searched per read (correction factor). Time: median wall milliseconds of one single-threaded detection call, single-process run on 32 prompts (64 reads per cell and family), marked reads; the 12-worker medians are larger and are in the derived file.

**GENERator-v2 1.2B** (`synthid.v5.generator.s2.*`)

| Cell | Detector | Windows | Marked reads | Marked prompts, both | Marked median strength | Ordinary reads | Ordinary prompts, any | One-sided 95% upper | Ordinary median strength | Median ms per read |
|---|---|---|---|---|---|---|---|---|---|---|
| `B_l0768` | aligned_oracle | 1 | 512/512 | 256/256 | 195.3 | 1/512 | 1/256 | 1.84% | 0.30 | 0.49 |
| `B_l0768` | fine_grid | 351,482 | 512/512 | 256/256 | 189.7 | 0/512 | 0/256 | 1.16% | -1.89 | 742.76 |
| `B_l0768` | phase_only | 12 | 511/512 | 255/256 | 22.9 | 5/512 | 5/256 | 4.06% | 0.15 | 55.26 |
| `B_l0768` | verifier | 37,640 | 512/512 | 256/256 | 190.7 | 1/512 | 1/256 | 1.84% | -1.09 | 90.80 |
| `B_l1152` | aligned_oracle | 1 | 512/512 | 256/256 | 295.8 | 2/512 | 2/256 | 2.44% | 0.31 | 1.95 |
| `B_l1152` | fine_grid | 351,482 | 512/512 | 256/256 | 290.3 | 1/512 | 1/256 | 1.84% | -1.78 | 746.24 |
| `B_l1152` | phase_only | 12 | 512/512 | 256/256 | 52.9 | 7/512 | 7/256 | 5.07% | 0.22 | 51.06 |
| `B_l1152` | verifier | 37,640 | 512/512 | 256/256 | 219.4 | 2/512 | 2/256 | 2.44% | -1.00 | 97.00 |
| `B_l3072` | aligned_oracle | 1 | 512/512 | 256/256 | 798.3 | 4/512 | 4/256 | 3.54% | 0.29 | 5.04 |
| `B_l3072` | fine_grid | 351,482 | 512/512 | 256/256 | 792.8 | 0/512 | 0/256 | 1.16% | -1.84 | 740.26 |
| `B_l3072` | phase_only | 12 | 512/512 | 256/256 | 385.0 | 4/512 | 4/256 | 3.54% | 0.15 | 50.15 |
| `B_l3072` | verifier | 37,640 | 512/512 | 256/256 | 793.7 | 0/512 | 0/256 | 1.16% | -1.07 | 92.36 |
| `reference` | aligned_oracle | 1 | 512/512 | 256/256 | 798.3 | 4/512 | 4/256 | 3.54% | 0.29 | 4.97 |
| `reference` | fine_grid | 101,442 | 512/512 | 256/256 | 793.3 | 0/512 | 0/256 | 1.16% | -1.63 | 224.55 |
| `reference` | phase_only | 12 | 512/512 | 256/256 | 701.3 | 6/512 | 5/256 | 4.06% | 0.18 | 28.98 |
| `reference` | verifier | 16,136 | 512/512 | 256/256 | 794.1 | 0/512 | 0/256 | 1.16% | -1.00 | 44.41 |
| `reference_insertion` | aligned_oracle | 1 | 483/512 | 227/256 | 202.5 | 2/512 | 2/256 | 2.44% | 0.30 | 1.78 |
| `reference_insertion` | fine_grid | 101,508 | 512/512 | 256/256 | 596.3 | 0/512 | 0/256 | 1.16% | -1.64 | 222.50 |
| `reference_insertion` | phase_only | 12 | 512/512 | 256/256 | 403.7 | 2/512 | 2/256 | 2.44% | 0.13 | 27.53 |
| `reference_insertion` | verifier | 16,144 | 512/512 | 256/256 | 460.9 | 0/512 | 0/256 | 1.16% | -1.00 | 41.48 |

**Carbon-500M** (`synthid.v5.carbon.s2.*`)

| Cell | Detector | Windows | Marked reads | Marked prompts, both | Marked median strength | Ordinary reads | Ordinary prompts, any | One-sided 95% upper | Ordinary median strength | Median ms per read |
|---|---|---|---|---|---|---|---|---|---|---|
| `B_l0768` | aligned_oracle | 1 | 512/512 | 256/256 | 194.2 | 5/512 | 5/256 | 4.06% | 0.30 | 0.48 |
| `B_l0768` | fine_grid | 351,482 | 512/512 | 256/256 | 188.6 | 0/512 | 0/256 | 1.16% | -1.82 | 739.06 |
| `B_l0768` | phase_only | 12 | 511/512 | 255/256 | 22.2 | 2/512 | 2/256 | 2.44% | 0.21 | 54.79 |
| `B_l0768` | verifier | 37,640 | 512/512 | 256/256 | 189.6 | 0/512 | 0/256 | 1.16% | -1.07 | 91.38 |
| `B_l1152` | aligned_oracle | 1 | 512/512 | 256/256 | 294.7 | 4/512 | 4/256 | 3.54% | 0.27 | 1.92 |
| `B_l1152` | fine_grid | 351,482 | 512/512 | 256/256 | 289.2 | 0/512 | 0/256 | 1.16% | -1.78 | 741.90 |
| `B_l1152` | phase_only | 12 | 511/512 | 255/256 | 51.8 | 5/512 | 5/256 | 4.06% | 0.22 | 50.62 |
| `B_l1152` | verifier | 37,640 | 512/512 | 256/256 | 219.4 | 1/512 | 1/256 | 1.84% | -1.00 | 96.73 |
| `B_l3072` | aligned_oracle | 1 | 512/512 | 256/256 | 791.5 | 2/512 | 2/256 | 2.44% | 0.30 | 4.99 |
| `B_l3072` | fine_grid | 351,482 | 512/512 | 256/256 | 786.0 | 1/512 | 1/256 | 1.84% | -1.81 | 739.76 |
| `B_l3072` | phase_only | 12 | 512/512 | 256/256 | 381.5 | 2/512 | 2/256 | 2.44% | 0.14 | 49.69 |
| `B_l3072` | verifier | 37,640 | 512/512 | 256/256 | 786.9 | 1/512 | 1/256 | 1.84% | -1.01 | 93.35 |
| `reference` | aligned_oracle | 1 | 512/512 | 256/256 | 791.5 | 2/512 | 2/256 | 2.44% | 0.30 | 4.92 |
| `reference` | fine_grid | 101,442 | 512/512 | 256/256 | 786.6 | 0/512 | 0/256 | 1.16% | -1.62 | 224.07 |
| `reference` | phase_only | 12 | 512/512 | 256/256 | 696.4 | 6/512 | 6/256 | 4.57% | 0.15 | 28.77 |
| `reference` | verifier | 16,136 | 512/512 | 256/256 | 787.3 | 2/512 | 2/256 | 2.44% | -1.00 | 45.12 |
| `reference_insertion` | aligned_oracle | 1 | 486/512 | 230/256 | 197.2 | 3/512 | 3/256 | 3.00% | 0.29 | 1.76 |
| `reference_insertion` | fine_grid | 101,508 | 512/512 | 256/256 | 591.8 | 0/512 | 0/256 | 1.16% | -1.61 | 221.79 |
| `reference_insertion` | phase_only | 12 | 512/512 | 256/256 | 397.8 | 3/512 | 3/256 | 3.00% | 0.14 | 27.29 |
| `reference_insertion` | verifier | 16,144 | 512/512 | 256/256 | 451.2 | 1/512 | 1/256 | 1.84% | -1.00 | 41.62 |

**S2 facts for the protocol's descriptive rule**

- GENERator-v2 1.2B: pairs of detectors whose exact two-sided 95% prompt-level intervals do not overlap: `reference_insertion` marked_prompts_both_draws aligned_oracle vs phase_only; `reference_insertion` marked_prompts_both_draws aligned_oracle vs verifier; `reference_insertion` marked_prompts_both_draws aligned_oracle vs fine_grid. Ordinary read-level rate above 1% (cell, detector, positives/reads): `reference` phase_only 6/512; `B_l1152` phase_only 7/512. Ordinary prompt-level any-draw rate above 1% (cell, detector, positives/prompts): `reference` aligned_oracle 4/256; `reference` phase_only 5/256; `B_l0768` phase_only 5/256; `B_l1152` phase_only 7/256; `B_l3072` aligned_oracle 4/256; `B_l3072` phase_only 4/256.

- Carbon-500M: pairs of detectors whose exact two-sided 95% prompt-level intervals do not overlap: `reference_insertion` marked_prompts_both_draws aligned_oracle vs phase_only; `reference_insertion` marked_prompts_both_draws aligned_oracle vs verifier; `reference_insertion` marked_prompts_both_draws aligned_oracle vs fine_grid. Ordinary read-level rate above 1% (cell, detector, positives/reads): `reference` phase_only 6/512. Ordinary prompt-level any-draw rate above 1% (cell, detector, positives/prompts): `reference` phase_only 6/256; `reference_insertion` aligned_oracle 3/256; `reference_insertion` phase_only 3/256; `B_l0768` aligned_oracle 5/256; `B_l1152` aligned_oracle 4/256; `B_l1152` phase_only 5/256.

Interpretation (protocol): descriptive. No detector is declared better from a difference whose exact 95% intervals overlap, and the verifier's settings do not change whatever the outcome. The aligned oracle searches one window, so its nominal level is 0.01 per read by construction. The fine-grid search stands in for a search over all contiguous spans, which was not run.

### S3: null calibration

64 null keys (key `i` is the SHA-256 of `synthid-review-v5/null-key/<i>`, never used in generation), domain `synthid-review-v5/null`, verifier unchanged. Ordinary and marked output: draw 0, reference layout, 512 reads per model, 16,136 windows each; natural DNA: 1,608 3,072-base spans, 13,064 windows each. Pooled intervals treat the read-by-key decisions as independent although they share reads and keys, so the pooled lower bound is anti-conservative as evidence against validity; the read-level and per-key figures stand beside it.

| Family | Positives / decisions | Rate | Two-sided 95% (pooled) | One-sided 95% upper (pooled) | Per-key rate: min / median / max | Keys with zero positives (of 64) | Reads positive under at least one key |
|---|---|---|---|---|---|---|---|
| GENERator-v2 1.2B, ordinary_model_output | 36/32,768 | 0.1099% | [0.077, 0.152]% | 0.145% | 0.000% / 0.000% / 0.781% | 39 | 36/512 (7.03%) |
| Carbon-500M, ordinary_model_output | 37/32,768 | 0.1129% | [0.080, 0.156]% | 0.149% | 0.000% / 0.000% / 0.781% | 38 | 36/512 (7.03%) |
| GENERator-v2 1.2B, marked_independent_key | 42/32,768 | 0.1282% | [0.092, 0.173]% | 0.166% | 0.000% / 0.098% / 0.781% | 32 | 40/512 (7.81%) |
| Carbon-500M, marked_independent_key | 46/32,768 | 0.1404% | [0.103, 0.187]% | 0.179% | 0.000% / 0.195% / 0.586% | 30 | 45/512 (8.79%) |
| natural DNA | 132/102,912 | 0.1283% | [0.107, 0.152]% | 0.148% | 0.000% / 0.124% / 0.435% | 11 | 127/1608 (7.90%) |

Identifiers: `synthid.v5.carbon.s3.ordinary_model_output.*`, `synthid.v5.generator.s3.ordinary_model_output.*`, `synthid.v5.carbon.s3.marked_independent_key.*`, `synthid.v5.generator.s3.marked_independent_key.*`, `synthid.v5.shared.s3.natural_dna.*` (each with `pooled_rate`, `per_key_rate`, `reads_positive_under_any_key`, `calibration`).

Calibration: fraction of decisions with sequence-level P-value at or below each nominal level (count in parentheses). Observed and nominal are both shown; no level exceeds nominal in any family.

| Family | 0.01 | 0.05 | 0.10 | 0.25 | 0.50 | Any level exceeds nominal |
|---|---|---|---|---|---|---|
| GENERator-v2 1.2B, ordinary_model_output | 0.110% (36) | 0.525% (172) | 1.071% (351) | 2.585% (847) | 4.736% (1,552) | none |
| Carbon-500M, ordinary_model_output | 0.113% (37) | 0.580% (190) | 0.983% (322) | 2.591% (849) | 4.782% (1,567) | none |
| GENERator-v2 1.2B, marked_independent_key | 0.128% (42) | 0.638% (209) | 1.147% (376) | 2.719% (891) | 4.776% (1,565) | none |
| Carbon-500M, marked_independent_key | 0.140% (46) | 0.558% (183) | 1.068% (350) | 2.521% (826) | 4.587% (1,503) | none |
| natural DNA | 0.128% (132) | 0.593% (610) | 1.122% (1,155) | 2.682% (2,760) | 4.728% (4,866) | none |

Lower 95% one-sided bounds per level: GENERator-v2 1.2B, ordinary_model_output: 0.01: 0.082%, 0.05: 0.461%, 0.1: 0.979%, 0.25: 2.442%, 0.5: 4.545%; Carbon-500M, ordinary_model_output: 0.01: 0.084%, 0.05: 0.513%, 0.1: 0.895%, 0.25: 2.448%, 0.5: 4.590%; GENERator-v2 1.2B, marked_independent_key: 0.01: 0.097%, 0.05: 0.567%, 0.1: 1.052%, 0.25: 2.573%, 0.5: 4.584%; Carbon-500M, marked_independent_key: 0.01: 0.108%, 0.05: 0.493%, 0.1: 0.976%, 0.25: 2.380%, 0.5: 4.398%; natural DNA: 0.01: 0.110%, 0.05: 0.554%, 0.1: 1.069%, 0.25: 2.600%, 0.5: 4.620%.

Interpretation (protocol rule): the P-value is supported as valid where every observed fraction is at or below its nominal level; any fraction whose one-sided 95% lower bound exceeds its nominal level is evidence against validity for that family. In every family above, every observed fraction is at or below its nominal level and no lower bound exceeds nominal: the rule supports the P-value as valid for these families and this sample. This is a statement about the reported families, keys, and sample sizes; with 64 keys a read can be positive under any of them, which the read-level column quantifies.

### S4: entropy and strength

One teacher-forced pass of the generating model (PyTorch 2.13.0, MPS, bfloat16) over each continuation of the 512 evaluated prompts; entropy is the Shannon entropy in nats of the canonical 4,096-token distribution at each of the 512 generated positions, averaged per sequence. For scale, ln 4096 = 8.3178 nats.

| Model | Arm | Sequences | Mean | Std | Min | 5% | 25% | Median | 75% | 95% | Max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GENERator-v2 1.2B | SynthID | 1024 | 7.5628 | 0.3646 | 1.074 | 7.101 | 7.482 | 7.643 | 7.752 | 7.835 | 7.899 |
| GENERator-v2 1.2B | ordinary | 1024 | 7.5633 | 0.3748 | 0.572 | 6.976 | 7.509 | 7.650 | 7.748 | 7.838 | 7.896 |
| Carbon-500M | SynthID | 1024 | 7.5952 | 0.3051 | 4.473 | 7.037 | 7.490 | 7.657 | 7.774 | 7.954 | 8.154 |
| Carbon-500M | ordinary | 1024 | 7.5979 | 0.3349 | 2.169 | 7.075 | 7.488 | 7.658 | 7.788 | 7.941 | 8.131 |

| Model | Spearman correlation of SynthID mean entropy with | Estimate | Bootstrap 95% interval | Unit | Valid replicates of 10,000 |
|---|---|---|---|---|---|
| GENERator-v2 1.2B | S0 unedited correct-key strength | 0.5808 | [0.5320, 0.6269] | 512 prompts, 1024 sequences | 10000 |
| GENERator-v2 1.2B | fraction of mark bits equal to 1 (full continuation window) | 0.5800 | [0.5313, 0.6261] | 512 prompts, 1024 sequences | 10000 |
| Carbon-500M | S0 unedited correct-key strength | 0.6630 | [0.6203, 0.7031] | 512 prompts, 1024 sequences | 10000 |
| Carbon-500M | fraction of mark bits equal to 1 (full continuation window) | 0.6530 | [0.6098, 0.6938] | 512 prompts, 1024 sequences | 10000 |

Identifiers: `synthid.v5.carbon.s4.mean_entropy`, `synthid.v5.generator.s4.mean_entropy`, `synthid.v5.carbon.s4.spearman_entropy_vs_strength`, `synthid.v5.generator.s4.spearman_entropy_vs_strength`, `synthid.v5.carbon.s4.spearman_entropy_vs_mark_bits`, `synthid.v5.generator.s4.spearman_entropy_vs_mark_bits`.

Interpretation (protocol): the prior expectation, stated before measurement, was a positive correlation in both models. All four estimates are positive and each bootstrap interval excludes zero. A correlation is not a causal attribution.

**S4 sampling-path cross-check (2026-11-13, after the S4 results existed; a check of the
measurement, not a new result).** For the first three evaluated prompts (draw 0, marked
continuation) of each model, the stored continuation was stepped token by token through the
adapter's `next_distribution`, the call generation makes (MPS, bfloat16), and the entropy at each
of the 512 positions was compared with the teacher-forced value from the S4 script's own function.

- Carbon (full context at every step): the two series agree to 7e-14 nats at every position, and
  the per-sequence means equal the stored values.
- GENERator (incremental cache on 511 of 512 steps): mean absolute difference 0.033 to 0.035 nats
  per position, largest 0.59; correlation 0.98 to 0.997 at no shift against 0.62 to 0.84 at a
  shift of one position either way; per-sequence means differ by 0.001 to 0.003 nats. With the
  cache reset at every step the bfloat16 series agree to 3e-13, and in float32 with the cache to
  9e-5, so the difference is bfloat16 rounding in the cached path, not misalignment.
- Every stored token has nonzero probability under the sampling-path distribution.

The teacher-forced entropy is therefore the entropy of the distribution each token was sampled
from, up to that rounding. The check also showed that for GENERator in bfloat16 the
log-probability of the stored token differs between the cached and the full pass by about 0.5
nats per token on these three sequences. S4 uses entropy only and reports no likelihood. The
check's scripts and outputs were kept outside the repository and are not evidence.

## 10. Output digests

sha256 of every study `summary.json`, every trials artifact, and the other result files. The trials artifacts are not copied into the repository. Digests stored in the summaries for their own trials files equal the files (Section 7).

| Path | sha256 |
|---|---|
| `outputs/synthid_v5_local/carbon/merged/detection/prompt_split.json` | `43cf800b204a55daf2ee3422bbeb2633cc8111ad785a130d21adcfbe9001991c` |
| `outputs/synthid_v5_local/carbon/merged/generation/draw_00_generation.json` | `84d5e583081a969bdb11ebc110ec9f8d0c286751a889f6910adb2d0fbbb68315` |
| `outputs/synthid_v5_local/carbon/merged/generation/draw_00_sequences.jsonl` | `4c2f832beb7432fb83fe6607eb9b9f2c4663e742b216a3568e065b8e0b7c7983` |
| `outputs/synthid_v5_local/carbon/merged/generation/draw_01_generation.json` | `dd1919fb23827bde01cfad5cb8e662b0e2d5dc18d61c281e2afb1a0fb52840e3` |
| `outputs/synthid_v5_local/carbon/merged/generation/draw_01_sequences.jsonl` | `babd06b52aac8ead8a9db65b941585059c396f3a66918bd2180042c33aacb682` |
| `outputs/synthid_v5_local/carbon/merged/generation/generation_summary.json` | `db5d38d559c7060dd4bd93a699af9771a400266262e6aa9c00fd3e1709bacda9` |
| `outputs/synthid_v5_local/carbon/merged/position_independent/report.md` | `5d3b3a044cc35cd074784e7669cbcc63f52437e60e618d21c44ec4113006ca4f` |
| `outputs/synthid_v5_local/carbon/merged/position_independent/summary.json` | `5b0660895536b5f0183bc08c3f3ef05e51916d29e3b21c07fd6a76c69d0fd5c3` |
| `outputs/synthid_v5_local/carbon/merged/position_independent/trials.jsonl` | `2f8d42e6e918771bc763954a36985fda950459e9995475a60f094debaed6fc8c` |
| `outputs/synthid_v5_local/carbon/studies/s1_layout/natural_pool_manifest.tsv` | `7397b07f2f5f25e5b530095537cc87bc4cd101c072c842e192cf3430a2a9fbbd` |
| `outputs/synthid_v5_local/carbon/studies/s1_layout/run_identity.json` | `6937afdb16f9b8f1abd9dd28a35b0f54bc1fb5848f93e5a1474b7715a62913de` |
| `outputs/synthid_v5_local/carbon/studies/s1_layout/summary.json` | `7fa3a065b91d836e827a8130c21b6052a8a33195440057d7877e274023ea4206` |
| `outputs/synthid_v5_local/carbon/studies/s1_layout/trials.jsonl.gz` | `7396c26dd6cb76095865f85e171c9e29d4081991bdf983333bf0c54b845e5b27` |
| `outputs/synthid_v5_local/carbon/studies/s2_detectors/run_identity.json` | `4d62be3a6e1b6f39ac1f77f2a2342f7c9c48181e3dca795fd50ee43ad8e95bfd` |
| `outputs/synthid_v5_local/carbon/studies/s2_detectors/summary.json` | `c1d729d8e4813b27e498c8b9f6be49dcf82b9f32165144b75a0da7150491a13c` |
| `outputs/synthid_v5_local/carbon/studies/s2_detectors/trials.jsonl.gz` | `01d137d1b8cee015f407acf833a9ce668955957d2587b0dc27afc4814497f28b` |
| `outputs/synthid_v5_local/carbon/studies/s2_timing/run_identity.json` | `24c87cd3ab57ba5d46da1908926141af6880fff375d3fc91ceac08b74c3d6f1d` |
| `outputs/synthid_v5_local/carbon/studies/s2_timing/summary.json` | `59e2a6ee69daceab9d5815b41bc78b3c2ab4db09739a30d06a676f996957aa1c` |
| `outputs/synthid_v5_local/carbon/studies/s2_timing/trials.jsonl.gz` | `086f4f92c16421c667f10963a7afca3444edbd3640aeb33ed976b84f6dbced58` |
| `outputs/synthid_v5_local/carbon/studies/s3_null_marked_independent_key/summary.json` | `a1bb92bbcc1d19ce0b619fb5e43f6cf000ea8a501d0826211177823d4a4897e9` |
| `outputs/synthid_v5_local/carbon/studies/s3_null_marked_independent_key/trials.jsonl.gz` | `ee7f59181f9a46dc7850ef26e2d2d9fb073ea1fd0f0d1cfb3985b178450a7a4c` |
| `outputs/synthid_v5_local/carbon/studies/s3_null_ordinary_model_output/summary.json` | `24a1d41e870ec8502f43162c3a56ce4e100651026ca2ea386beac9f6478da16b` |
| `outputs/synthid_v5_local/carbon/studies/s3_null_ordinary_model_output/trials.jsonl.gz` | `027fd82f69996c974482286ad5da06e50a6c69734be7b203b8b1787d78b170ae` |
| `outputs/synthid_v5_local/carbon/studies/s4_entropy/sequences.jsonl` | `85513fce4e6bba9b636b369df54b525d279d438d59f469cf5e51377dd962a44c` |
| `outputs/synthid_v5_local/carbon/studies/s4_entropy/summary.json` | `1878147feda2a522fb86e8685bd527ecfe9ab0a534bafb8f33d16255a692f67a` |
| `outputs/synthid_v5_local/evaluated_case_ids.txt` | `4a6ea27d2a2fa036069f9fdf874427263dce0cf56a53a947574e5e9dfe02e320` |
| `outputs/synthid_v5_local/generator/merged/detection/prompt_split.json` | `43cf800b204a55daf2ee3422bbeb2633cc8111ad785a130d21adcfbe9001991c` |
| `outputs/synthid_v5_local/generator/merged/generation/draw_00_generation.json` | `57624da7222ed86bbb999fe892a240028358ff5756f8698a2eb1752d7e84a5e4` |
| `outputs/synthid_v5_local/generator/merged/generation/draw_00_sequences.jsonl` | `e919cec722ae4e06be44c2a3f52da89139b8678e40c5581ad3903263546137f0` |
| `outputs/synthid_v5_local/generator/merged/generation/draw_01_generation.json` | `7d911fba979d2ec3017c0af883385d31fe245a330fde36baacab5ebf8a82e678` |
| `outputs/synthid_v5_local/generator/merged/generation/draw_01_sequences.jsonl` | `bb8811e49f0fb8e46e0fd947a96deed1996fd50c11cfee42f5a6f2d5fc74f076` |
| `outputs/synthid_v5_local/generator/merged/generation/generation_summary.json` | `a5a8ee50cb1aed7c106a95557f726afe166fb3ba70ce04706da086e2482f4e96` |
| `outputs/synthid_v5_local/generator/merged/position_independent/report.md` | `51f0f86036316a814ba3fc94dda44b69dd2b64d5e34265e86b5c6982486cac04` |
| `outputs/synthid_v5_local/generator/merged/position_independent/summary.json` | `a075c9160ac3c717a52b8104db78a1ae5a86693347a2899cc73674cd8543aafa` |
| `outputs/synthid_v5_local/generator/merged/position_independent/trials.jsonl` | `962bacd9fec2a6a9e1857b5e6b4c527575ca976cd6eb63f98a536d1f6920a6e5` |
| `outputs/synthid_v5_local/generator/studies/s1_layout/natural_pool_manifest.tsv` | `7397b07f2f5f25e5b530095537cc87bc4cd101c072c842e192cf3430a2a9fbbd` |
| `outputs/synthid_v5_local/generator/studies/s1_layout/run_identity.json` | `ceaab7b4b34370015479ddefc468725acd24ee0b7ff200c8956701c1ffc4a11a` |
| `outputs/synthid_v5_local/generator/studies/s1_layout/summary.json` | `d6164a7c5718930d4e2a650f8f401f9854a1fa348741dbfabe0045e6d8bbfccf` |
| `outputs/synthid_v5_local/generator/studies/s1_layout/trials.jsonl.gz` | `c43b39f323677d0d5e4b54bc21cc211dfe65030743a23f128da415cb6f3cf648` |
| `outputs/synthid_v5_local/generator/studies/s2_detectors/run_identity.json` | `e9da5cd722a2f5f212088a9003604032df4c99ee3f65a7fb52150b4ba457ca60` |
| `outputs/synthid_v5_local/generator/studies/s2_detectors/summary.json` | `fd757030219e809c8b487a65bef60187e74b9aff7c15ca9bf5b7eac6cc0ce4a7` |
| `outputs/synthid_v5_local/generator/studies/s2_detectors/trials.jsonl.gz` | `c0a327f1d9cf66f0ad4e8fe00c65f31702a1a35c862543e6b3d5019e3c996c36` |
| `outputs/synthid_v5_local/generator/studies/s2_timing/run_identity.json` | `023c4f9a7108dba6e95aebafc0873b01d30f6630582596863a0d2e9c314a6900` |
| `outputs/synthid_v5_local/generator/studies/s2_timing/summary.json` | `5117952a97c52dd60cd84db122b440b835e1e546619590df9233a6d937bdd858` |
| `outputs/synthid_v5_local/generator/studies/s2_timing/trials.jsonl.gz` | `9a540866a11befdd8c65c2a2914d0c52f17d2f59eb28d63ce12dac812e981f14` |
| `outputs/synthid_v5_local/generator/studies/s3_null_marked_independent_key/summary.json` | `7629915d37d023f661363dda016b485c852cfaa49d94c99107d9137479cfc5db` |
| `outputs/synthid_v5_local/generator/studies/s3_null_marked_independent_key/trials.jsonl.gz` | `b20ead259eedc3b3dbb0546dfe3c83baa9332578a47c4d24679416e299a9a96c` |
| `outputs/synthid_v5_local/generator/studies/s3_null_ordinary_model_output/summary.json` | `36e6ca88d0668e1ae144d54e079eb21059d9c2ba821a0767d57a1e4dece8534a` |
| `outputs/synthid_v5_local/generator/studies/s3_null_ordinary_model_output/trials.jsonl.gz` | `865dbfae9462d89e7ea01e3b527a2fe4c5737b0b25c11f4dea89d4e0e48e2147` |
| `outputs/synthid_v5_local/generator/studies/s4_entropy/sequences.jsonl` | `a8fd8f343fe5a9a1be33ca983dfcb65ea69496c4707ca5d312c6bb2040457c82` |
| `outputs/synthid_v5_local/generator/studies/s4_entropy/summary.json` | `66ecc9a18d9da1fa59ec7e1094300f0318beda9aed793c1f93125af092ceef38` |
| `outputs/synthid_v5_local/logs/detect_carbon.log` | `ce24aa1c2d5ed7f6ee990078ffbff75f2a3c6d45304407ef50bd68cc16c8c5f7` |
| `outputs/synthid_v5_local/logs/detect_generator.log` | `482e8e649e5877f0d6391b6710a2392d80a4fa510d1c4b775154ae4f62483ea4` |
| `outputs/synthid_v5_local/logs/final.log` | `13ffc20589131bd619a1d7f2ec7e804ada935aa2446de9baa872ec6cd035675b` |
| `outputs/synthid_v5_local/shared/s3_null_natural_dna/summary.json` | `a74833ff692bf8946749638b9f2c9b0c5f1b362e580f036a445f07820ef042fa` |
| `outputs/synthid_v5_local/shared/s3_null_natural_dna/trials.jsonl.gz` | `ff01c3ed99a785d19dd52ed5726f0f99c74d62837b847a4e472ce30891a29954` |
| `outputs/synthid_v5_local/shared/s4_entropy_analysis/marked_sequences_joined.jsonl` | `583dd0c456dc2b2f549716fdbabbffe37f9d787b14ed3f14bf200e757dee6df6` |
| `outputs/synthid_v5_local/shared/s4_entropy_analysis/summary.json` | `72ad519535b5e2e1877bac44992665e0dc755d6eae50b8fb4862acc970c1ceeb` |

Compact copies in `evidence/derived/synthid_v5/` (digests in its `SHA256SUMS`):

| File | sha256 |
|---|---|
| `carbon_generation_summary.json` | `db5d38d559c7060dd4bd93a699af9771a400266262e6aa9c00fd3e1709bacda9` |
| `carbon_s0_position_independent_summary.json` | `5b0660895536b5f0183bc08c3f3ef05e51916d29e3b21c07fd6a76c69d0fd5c3` |
| `carbon_s1_layout_summary.json` | `7fa3a065b91d836e827a8130c21b6052a8a33195440057d7877e274023ea4206` |
| `carbon_s2_detectors_summary.json` | `c1d729d8e4813b27e498c8b9f6be49dcf82b9f32165144b75a0da7150491a13c` |
| `carbon_s2_timing_summary.json` | `59e2a6ee69daceab9d5815b41bc78b3c2ab4db09739a30d06a676f996957aa1c` |
| `carbon_s3_null_marked_independent_key_summary.json` | `a1bb92bbcc1d19ce0b619fb5e43f6cf000ea8a501d0826211177823d4a4897e9` |
| `carbon_s3_null_ordinary_model_output_summary.json` | `24a1d41e870ec8502f43162c3a56ce4e100651026ca2ea386beac9f6478da16b` |
| `carbon_s4_entropy_summary.json` | `1878147feda2a522fb86e8685bd527ecfe9ab0a534bafb8f33d16255a692f67a` |
| `evaluated_case_ids.txt` | `4a6ea27d2a2fa036069f9fdf874427263dce0cf56a53a947574e5e9dfe02e320` |
| `generator_generation_summary.json` | `a5a8ee50cb1aed7c106a95557f726afe166fb3ba70ce04706da086e2482f4e96` |
| `generator_s0_position_independent_summary.json` | `a075c9160ac3c717a52b8104db78a1ae5a86693347a2899cc73674cd8543aafa` |
| `generator_s1_layout_summary.json` | `d6164a7c5718930d4e2a650f8f401f9854a1fa348741dbfabe0045e6d8bbfccf` |
| `generator_s2_detectors_summary.json` | `fd757030219e809c8b487a65bef60187e74b9aff7c15ca9bf5b7eac6cc0ce4a7` |
| `generator_s2_timing_summary.json` | `5117952a97c52dd60cd84db122b440b835e1e546619590df9233a6d937bdd858` |
| `generator_s3_null_marked_independent_key_summary.json` | `7629915d37d023f661363dda016b485c852cfaa49d94c99107d9137479cfc5db` |
| `generator_s3_null_ordinary_model_output_summary.json` | `36e6ca88d0668e1ae144d54e079eb21059d9c2ba821a0767d57a1e4dece8534a` |
| `generator_s4_entropy_summary.json` | `66ecc9a18d9da1fa59ec7e1094300f0318beda9aed793c1f93125af092ceef38` |
| `shared_s3_null_natural_dna_summary.json` | `a74833ff692bf8946749638b9f2c9b0c5f1b362e580f036a445f07820ef042fa` |
| `shared_s4_entropy_analysis_summary.json` | `72ad519535b5e2e1877bac44992665e0dc755d6eae50b8fb4862acc970c1ceeb` |

## 11. Admission

- Ledger: 97 entries added under `synthid.v5.*` (appended to `evidence/measurements.yaml`; no existing entry was changed). `.venv/bin/python scripts/emit_synthid_v5_ledger.py --verify`: verified 2302 referenced numbers across 97 entries; failures 0.
- `python3 scripts/check_evidence.py`: 5 errors, all `missing evidence artifact` for the five Carbon development-cohort result files that were never committed (the known failure); no error concerns `synthid.v5.*`. The checker verified 44 artifact digests and 17 document paths (22 and 15 before the v5 entries were appended), including every compact result file and the derived file cited by the v5 entries, and found every identifier in `paper/context/evidence_map.md` in the ledger.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`: 253 tests, OK (skipped=4).
- `.venv/bin/ruff check .`: 0 findings in the v5 derivation and ledger scripts; 7 findings in other, pre-existing files (scripts/build_large_public_prompt_cohort.py, scripts/hpc/run_direct_synthid_fpr.py, scripts/run_synthid_edit_rate_pilot.py, src/genomic_watermarks/synthid_boundary.py, tests/test_multi_base_edit.py).
- `evidence/measurements.yaml` as a whole is not accepted by a strict YAML parser: before this append, a plain multi-line scalar in the `synthid.v3.source_manifest` entry (`supersedes_manifest`, line 2223) contains a colon followed by a space. This is not part of the v5 block, which was parsed with PyYAML on its own and round-trips every value. The existing entry was not edited.
- Interpretation rules passed or reported: S0 completed and the strict validator passed for both models; S1 checks 1 and 2 pass for both models; digests are recorded (Sections 3, 6, 10); the protocol sha256 recorded in every summary equals the current protocol file. The S4 sampling-path cross-check is pending and is not a ledger entry. Admission does not widen the threat model.

The ledger entries are `synthid.v5.cohort.identity`, `synthid.v5.<model>.generation.throughput`, `synthid.v5.<model>.detector.<condition>.{correct_key,ordinary,wrong_key}_rate`, `synthid.v5.<model>.detector.correct_key_strength_by_condition`, `synthid.v5.<model>.s1.*`, `synthid.v5.<model>.s2.*`, `synthid.v5.<model>.s3.*` and `synthid.v5.shared.s3.natural_dna.*`, and `synthid.v5.<model>.s4.*`; `paper/context/evidence_map.md` lists each identifier. Each entry cites a compact result file under `evidence/derived/synthid_v5/` and a JSON path; `scripts/emit_synthid_v5_ledger.py --verify` re-resolves every referenced number against its cited file.

The 64 reserved prompts were not used. The logs record each stage once and contain no failure line; every one of the 512 evaluated prompts is in every study (S2 uses the first 256 by protocol, S2 timing the first 32); no case was excluded and none was rerun selectively. The cohort has 512 evaluated prompts per model, so no control rate is reported below the resolution of 512 prompts (a zero count has a one-sided 95% upper bound of 0.583%); pooled S3 rates rest on 32,768 or 102,912 correlated decisions and carry that caveat.

## 12. Claims not made

These results are statistical watermark-detection and model-based proxy measurements on one locally regenerated cohort with public fixture keys. They do not establish biological function, viability, safety, sequence authenticity, or secret-key security, and they are not an independent replication. SynthID preservation is an expectation over fresh keyed functions; a fixed key and context use a deliberately reweighted distribution. The assumed attacker does not know the key and cannot query the detector. The studies add no multiple-edit or detector-guided condition; layouts are chosen by public hash streams. S2's comparison detectors are baselines for one analysis and do not replace the verifier.
