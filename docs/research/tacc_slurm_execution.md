# Optional TACC Lonestar6 CUDA and Slurm execution record

This profile accelerated the completed Carbon SynthID validation and the later GENERator
replication without changing either MPS/CPU-capable path. It uses the same scientific runners and
schemas; CUDA and Slurm appear only in device selection, environment records, and orchestration.

## Frozen environment

Lonestar6 currently exposes `cuda/12.8`. The named Conda environment is `tacc_watermark` and lives
in Conda's configured `$SCRATCH` environment directory. Its direct pins are:

```text
Python 3.12.14
PyTorch 2.11.0+cu128
Transformers 5.15.1
CUDA module 12.8
```

Create or reconcile it from a TACC shell with:

```bash
cd /path/to/genomic-sampling-watermarks
bash scripts/hpc/create_tacc_watermark_env.sh
```

The creator uses `environment/tacc_watermark.yml` and
`environment/tacc-cu128-requirements.txt`, installs this checkout in editable mode without changing
dependency resolution, runs `pip check`, and validates module/build agreement. A login node may
report no GPU; the batch preflight requires real devices and executes a CUDA tensor operation.

TACC injects an Intel MPI Python 3.9 directory through `PYTHONPATH`. Every HPC activation unsets
that path and sets `PYTHONNOUSERSITE=1`; otherwise an apparently healthy Python 3.12 environment
contains an ABI-incompatible site package. Batch jobs fail before model loading if the Conda name,
CUDA module, PyTorch CUDA build, Slurm allocation, or requested GPU count is wrong.

## Cache and data boundary

Model and tokenizer revisions remain pinned in `sources.yaml`. GPU jobs pass `--local-files-only`,
so missing cache content is a hard failure rather than an unrecorded compute-node download. The
public cohort and cache paths are exported to the jobs, but raw keys, generated sequences, model
weights, and credentials are never copied into tracked files. Use `$SCRATCH` for the ignored cache
and output roots.

## Submission

TACC accepts `sbatch` only on a login node. Do not run the submitter from `idev`, a compute node, or
inside another Slurm job. From `login*.ls6.tacc.utexas.edu`, run the smoke first:

```bash
python3 scripts/hpc/submit_carbon_synthid_validation.py \
  --profile smoke \
  --account YOUR_TACC_ALLOCATION
```

After the smoke's post job passes, submit the frozen 256-prompt workload:

```bash
python3 scripts/hpc/submit_carbon_synthid_validation.py \
  --profile full \
  --account YOUR_TACC_ALLOCATION
```

The supplementary GENERator workflow uses the parallel submitter with the same profile names:

```bash
python3 scripts/hpc/submit_generator_synthid_validation.py \
  --profile smoke \
  --account YOUR_TACC_ALLOCATION

python3 scripts/hpc/submit_generator_synthid_validation.py \
  --profile full \
  --account YOUR_TACC_ALLOCATION
```

Use `--output-root` to select a different new or resumable root. `--dry-run` prints the resolved
preparation and GPU submission commands without writing or submitting. Queue and time defaults are:

| Profile | GPU stage | Carbon post stage | GENERator post stage |
|---|---|---|---|
| smoke | `gpu-a100-dev`, 2 hours | `development`, 30 minutes | `development`, 30 minutes |
| full | `gpu-a100`, 24 hours | `normal`, 6 hours | `normal`, 12 hours |

Lonestar6 schedules complete GPU nodes in these partitions and does not expose generic GPU GRES in
its Slurm configuration, so the scripts intentionally do not request `--gres`. The GPU stage uses
two of the node's A100s: draw 0 and draw 1 run concurrently, followed by concurrent fixed-state and
teacher-forced analyses. The CPU post job has an `afterok` dependency and runs detection, figures,
report rendering, and the strict validator.

The submitter records job IDs, dependency, account, partitions, exact paths, config checksum, git
commit, and dirty-worktree digest under `output_root/orchestration/`. Environment checks are stored
under `output_root/environment/`. Neither record contains key bytes or generated DNA.

Submission also writes an immutable `orchestration/source_manifest.json` covering every Python
module under `src/`, every scientific/HPC runner in this workflow, the environment locks, model
source pins, cohort manifests, and resolved HPC config. Both jobs verify those hashes before doing
work. If scientific source changes while a job is queued, the job fails instead of producing an
artifact with ambiguous code provenance; submit changed code to a new output root.

## Monitoring and resumption

```bash
squeue -u "$USER" -o '%.18i %.12P %.24j %.2t %.10M %.4D %R'
tail -f "$SCRATCH/carbon_synthid_validation_hpc_v1/orchestration/logs/gsw-synthid-gpu-"*.out
```

Use the selected GENERator output root in the second command when monitoring that replication.

The detailed stage logs are `generation_draw_00.log`, `generation_draw_01.log`,
`distribution.log`, `sequence_comparison.log`, and `detection.log`. They contain case identifiers,
timings, and failures, not sequence payloads.

To resume after a failed job, submit the same profile with the same `--output-root`. Scientific
runners validate and skip immutable completed shards. Finalized artifacts are accepted only when
byte-identical; different content is never overwritten. Figure pairs and their manifest are also
resume-safe. If the GPU job fails, the post job remains pending on `afterok` and may be cancelled or
left for the corrected GPU resubmission.

## Recorded validation status

The four-prompt smoke passed inside existing Lonestar6 job `3399876` on 2026-08-29. This Codex
session then opened `ssh login1` and submitted the full dependency chain from the authenticated
login shell: GPU job `3400018` in `gpu-a100` and post-processing job `3400019` in `normal` with
dependency `afterok:3400018`, against output root
`/scratch/10899/kimopro/carbon_synthid_validation_hpc_v2`.

**That chain was then cancelled by the account owner before either job started.** `sacct` records
both as `CANCELLED by 903286` with zero elapsed time and no start time; `3400019` shows reason
`Dependency`, which is the normal pending state for an `afterok` job, not a failure. The submission
itself was correct: `orchestration/submission_3400018.json` was written, so the banner-parser defect
that killed `3400015` did not recur.

### Completed Carbon SynthID run

The final generation job was submitted on 2026-08-29 at 12:11:42Z against
`/scratch/10899/kimopro/carbon_synthid_validation_hpc_v3`:

| Job | Name | Partition | Dependency | Outcome |
|---|---|---|---|---|
| `3400067` | `gsw-synthid-gpu` | `gpu-a100-dev` | — | generation completed; job reached its two-hour limit during later stages |
| `3400068` | `gsw-synthid-post` | `normal` | `afterok:3400067` | did not run because the parent ended with `TIMEOUT` |

Job `3400067` wrote a complete generation summary before Slurm stopped it: 256 prompts, two draws,
1,024 sequences, 524,288 generated tokens, and 3,145,728 generated bases. Its two sequence JSONL
files were copied byte-for-byte into the final analysis root
`/scratch/10899/kimopro/carbon_synthid_validation_hpc_v4`; their SHA-256 digests are
`3b363ff9e5640d0d24e2f0f65db0f576ac2bc5f60da13adbc51cf68e48530f9d` and
`40cea992524e194cb54fa9e08ae53e9e60b46f3428860bea9c162c4f7612fab2`.

Interactive MFA prevented another non-interactive login-node submission during the continuation.
The model-backed fixed-state and teacher-forced analyses therefore used the declared CPU fallback
on a Lonestar6 `vm-small` host with bfloat16 and local-only model files. Detection resumed from all
512 immutable score shards and did not load the model. The exact mixed-device environment is frozen
in `configs/carbon_synthid_validation_cpu_analysis_resume_v1.toml`; commands, hashes, and the
provenance boundary are recorded in
[`carbon_synthid_e16_execution_2026_08_29.md`](carbon_synthid_e16_execution_2026_08_29.md).

The final `v4` root contains all 256 fixed-state results, all 1,024 sequence-metric records, the
analytic-threshold detection analysis, ten PNG/PDF figure pairs, the rendered report, and a passing
strict digest manifest. `v3` remains the generation origin; `v4` is the evidence-selected analysis
root. The two roots are connected only by the explicitly verified byte-identical generation files.

### Superseded roots

The earlier incomplete roots remain excluded from the completed result:

| Root | Jobs | Outcome |
|---|---|---|
| `..._hpc_v1` | `3400015` | dependent job rejected by the original banner parser; GPU job cancelled while pending |
| `..._hpc_v2` | `3400018`/`3400019`, `3400041`/`3400042`, `3400043`/`3400044` | queued three times and cancelled; the last attempt produced only 32/256 pre-optimisation shards |

No `v1` or `v2` shard was merged into `v3` or `v4`. The accelerated sampler is bit-identical on the
declared tests, but the specific partial `v2` draws were not compared byte-for-byte, so exclusion is
the only defensible treatment. The submitter now extracts the final numeric job ID from both plain
and TACC banner-prefixed `sbatch` output.

Smoke numbers and their interpretation boundary are recorded in
[`carbon_synthid_hpc_smoke_2026_08_29.md`](carbon_synthid_hpc_smoke_2026_08_29.md).

### Completed GENERator SynthID replication

The full GENERator replication used output root
`/scratch/10899/kimopro/generator_synthid_validation_hpc_v1` and the same two-GPU generation layout.
Its scientific source tree was frozen before execution with SHA-256
`96f8418f13cfec283cdfa2d4ea7c228a6c96ce99569b029dbda91c9efeb1a989`.

| Job | Stage | Outcome |
|---|---|---|
| `3408824` | generation and parallel model analyses | all 1,024 sequences and quality results finalized; timed out after 247/256 sampler states |
| `3409024` | sampler-analysis recovery | finalized the remaining nine sampler states; later redundant quality finalization was refused by immutable-output protection |
| `3409054` | aligned detection, report, and validation | scientific outputs completed; stopped on the original rare-event bootstrap guardrail |
| `3409070` | final position-independent detector | all 4,608 decisions and the strict detector validator completed successfully |

After the rare-event validator was corrected to use the exact prompt-level Poisson-binomial check,
the full artifact validator also passed. The correction changed no generation, calibration, score,
threshold, or detector decision. The complete scientific interpretation, exact artifact hashes,
and validation amendment are in
[`generator_synthid_execution_2026_09_03.md`](generator_synthid_execution_2026_09_03.md) and
[`generator_synthid_validator_amendment_2026_09_03.md`](generator_synthid_validator_amendment_2026_09_03.md).

The GENERator run is supplementary evidence under the current Carbon-only manuscript scope. It
does not make CUDA or Slurm part of the required local reproduction path.
