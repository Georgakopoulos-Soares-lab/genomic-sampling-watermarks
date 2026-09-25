# Lane 1 direct A100 run plan and execution log

**Date:** 2026-09-21, completed 2026-09-24. **Status:** complete. Generation and position-
independent detection finished for both models, both strict validators pass, and the results are
admitted to `evidence/measurements.yaml`. See *Results and admission* at the end.
This replaces Lane 1's Slurm submission examples for the current allocation. The user's explicit
authorization removes the M5-only evidence requirement (AD-1 in the original lane note); the
repository hardware guidance now admits documented A100 execution. L1-07 remains unsigned and
outside this run.

## Inputs and identity gates

1. Freeze the output-blind public source specification in
   `data/public_prompt_cohort_fpr_v2_sources.yaml`, then build the immutable candidate manifest
   `data/public_prompt_cohort_fpr_v2_1608.yaml` and processed cohort. Verify 1,608 unique,
   384-base prompts and 64 calibration plus 1,544 evaluation assignments. Record the cohort
   content digest and manifest hashes. Never select prompts based on model output.
2. Fill the cohort digest in `synthid_v2_fpr_scaling_protocol_2026_09_21.md`, freeze that file,
   and record its SHA-256 before model inference. Freeze separate new v2 model configs. The new
   domain labels and experiment IDs prevent old v1 shards from being admitted as v2 evidence.
3. Activate `tacc_watermark` with `cuda/12.8`; check both A100s, pinned model revisions in the
   offline Hugging Face cache, Python/package versions, source manifest, and remaining allocation
   time. Capture this environment record and the exact command line.

## Smoke gate

Use `scripts/hpc/run_direct_synthid_fpr.py` with `--profile smoke` on Carbon and GENERator
in separate new output roots. Smoke uses four deterministic prompts across the split, two draws,
two arms, and 64 generated tokens. One GPU handles each draw. Confirm all eight per-model prompt
shards exist, checksum and identity validation pass, both draw summaries finalize, and the model
cache was used offline. Smoke outputs have their own identity and are never mixed with full data.

## Full generation and detection

After both smokes pass, run each model with `--profile full` against the fixed 1,608-prompt cohort.
Generate two 512-token draws, each containing ordinary and SynthID arms. The script validates an
existing shard before skipping it; a failed or interrupted prompt is retried on the next invocation.
Complete draw files are assembled only after every expected shard is present. The full runner then
uses the deterministic 64-prompt split and invokes position-independent detection on the 1,544
evaluation prompts. Detector work also checkpoints one immutable prompt shard at a time. Run strict
model-specific validators, `scripts/check_evidence.py`, and source/artifact hash checks before
adding new `[V]` and `[A]` ledger entries or the Results Delta Packet.

Each new allocation can repeat the **same** full command with the same cohort, protocol, config,
output root, and model cache. It will validate and skip complete shards. Keep a separate log per
invocation rather than overwriting a prior log. A partially complete run is `inconclusive` or
`not_run` in the delta packet, never a reported FPR result.

## Operational checks

| Gate | Check | Continue only if |
|---|---|---|
| Cohort | source/manifests/hash, count, uniqueness, fixed split | all exact |
| Environment | CUDA probe, two A100 devices, offline cache, source hash | all exact |
| Smoke | both draws and both arms per model, shard checksums | both models pass |
| Full generation | 1,608 shards per draw/model and immutable summaries | complete |
| Detection | 1,544 shards/model; 37,056 decisions/model; global search correction | complete |
| Evidence | validators, protocol/config/artifact hashes, ledger checker | all pass |

The detector is CPU intensive, and the 1,608-prompt generation is larger than one development
allocation. This plan intentionally resumes across allocations; no completion claim is made from
partial shards. The source manifest and runtime log record any code change between resumptions.

## Commands and observed progress

### Gate 1 — cohort (PASSED 2026-09-21)

The output-blind source specification was frozen first, then fetched. The parallel fetch was
interrupted by an NCBI rate-limit error at 1,598 of 1,608 windows and was resumed with the
identical command at two workers and a 0.5 s interval; already-fetched windows are content-checked
and reused, so the resumption is not a refetch.

```bash
python3 scripts/build_large_public_prompt_cohort.py \
  --source-spec data/public_prompt_cohort_fpr_v2_sources.yaml \
  --freeze-manifest data/public_prompt_cohort_fpr_v2_1608.yaml \
  --raw-root data/raw --freeze-workers 2 --request-interval-seconds 0.5

python3 scripts/build_large_public_prompt_cohort.py \
  --manifest $PWD/data/public_prompt_cohort_fpr_v2_1608.yaml \
  --raw-root $PWD/data/raw --processed-root $PWD/data/processed --offline
```

The processed build ran with `--offline`, so no prompt could be reselected once model output
existed. Reported validation: unique case ids, unique prompt sequences, unique public-null
sequences, canonical prompts, non-overlapping source spans, hashes verified, and
`selection_used_model_output: false`.

| Quantity | Value |
|---|---|
| Cohort id | `ncbi_refseq_eukaryote_windows_fpr_v2_1608` |
| Prompts | 1,608 unique, 384 bases each, from 12 accessions and 6 organisms |
| Split | 64 calibration / **1,544 evaluation**, recomputed and confirmed |
| Cohort content SHA-256 | `f6075a85bc056f5159952031618c544fb3a82864ed9029c913e7f5a7d03c5dc5` |
| Source spec SHA-256 | `8ecdbdf10eda6ebbefad90031552914e62671d16039b209b2025d5210fd53b1d` |
| Frozen manifest SHA-256 | `7adad76712848a0d0b19e9660c24197293d751610a98ecb8db1bda35534b5c55` |
| `prompts.jsonl` SHA-256 | `cb19e90662fcb25f774b0840e2e696132e2dc9c54439d97597bd186d4948f775` |
| Public-null cohort SHA-256 | `b949530f16ea5b4b19ef9c43170bafac3ac9a1d43b355efb92ec8a5ffeaba0c5` |

### Gate 2 — protocol and configuration (PASSED 2026-09-21)

`docs/research/synthid_v2_fpr_scaling_protocol_2026_09_21.md` was completed with the digests above
and frozen at SHA-256 `ad950bfdda3d664d7691574d4d88e3403d84cd438a7961f6ebfb25a787523d32`. Its
predeclared one-sided 95% upper bounds at 1,544 evaluation prompts were recomputed independently
and agree exactly: 0 positives gives 0.19384%, 8 gives 0.93294%, and 15 gives 1.49200%. The bound
therefore falls below 1% only if at most eight prompt clusters are positive, as predeclared.

`configs/carbon_synthid_v2_fpr_hpc.toml` and `configs/generator_synthid_v2_fpr_hpc.toml` were
frozen with the new `carbon-synthid-fpr-v2` and `generator-synthid-fpr-v2` domain labels, the new
`*_synthid_v2_fpr_generation` and `*_synthid_v2_fpr_position_independent` experiment identities,
the pinned model revisions, the cohort digest, and the protocol digest. The runner's strict
configuration comparison accepts both files: a smoke invocation passed the cohort, identity, and
configuration checks and wrote its immutable `orchestration/run_identity.json` before reaching the
device gate. Per AD-1, these configs carry `execution_profile = "lonestar6_a100_direct"` and no
laptop-path requirement; the frozen `*_hpc_v1.toml` files are untouched.

Both pinned revisions are present in the offline Hugging Face cache, so `--local-files-only`
cannot silently download: Carbon-500M `9796b752108258c1d365089f842e62e6c0547704` and GENERator-v2
1.2B `c41b0018da9ee13b9e96ee54647de8da381ccd72`.

### Gate 3 — environment (FAILED on node c301-002; the run is blocked here)

`module load cuda/12.8` loads cleanly and `torch 2.11.0+cu128` reports `torch.version.cuda 12.8`,
but CUDA cannot initialise on this node. The cause is a node hardware fault, not an environment or
module problem, and it is not fixable from user space:

- The node has three A100s. The one at `0000:21:00.0` (device minor 0) fails to attach. The kernel
  log repeats `NVRM: osInitNvMapping: *** Cannot attach gpu` and
  `NVRM: GPU 0000:21:00.0: RmInitAdapter failed! (0x22:0x56:744)`, first at 377,622 s of a 520,843 s
  uptime — roughly four days before this session, so the fault predates this work.
- `nvidia-smi` shows only the two healthy A100s, at `0000:81:00.0` and `0000:e2:00.0`, both idle,
  0 MiB used, no ECC or row-remap errors.
- Because the UVM driver's global initialisation probes every RM-registered GPU, the dead adapter
  makes `open("/dev/nvidia-uvm")` return `EIO` for every process on the node. `cuInit` then returns
  999 and `torch.cuda.is_available()` is `False` while `device_count()` still reports 2, which is
  the misleading symptom recorded earlier.
- Ruled out: the `cuda/12.8` module, `CUDA_VISIBLE_DEVICES` by index and by GPU UUID, the device
  node majors (`237` matches `/proc/devices`), device cgroup restriction (`a *:* rwm`), running
  inside the Slurm job step rather than the login session, and `nvidia-modprobe -u`. The fix is
  `rmmod nvidia_uvm; modprobe nvidia_uvm` after the dead adapter is removed, or a node repair;
  both need root.

Lonestar6 refuses `sbatch` from compute nodes. Submission was done over `ssh login1`, which accepts
the user's key; because `~/.bashrc` execs zsh even for non-interactive sessions, the submission
commands were fed through a forced pty (`ssh -tt`) rather than as a plain remote command.

### Partition fallback and the one-GPU-per-draw change (2026-09-21)

The first submission to `gpu-a100` (jobs `3459822`/`3459823`) never started: the partition was
fully subscribed and the jobs sat in `ReqNodeNotAvail`. They were cancelled and the work moved to
`gpu-a100-small`, whose `qa100small` QoS allows a two-day walltime and twelve concurrent jobs, but
gives each job a **single** A100 rather than a whole two-GPU node.

`scripts/hpc/run_direct_synthid_fpr.py` previously required two GPUs unconditionally and launched
draw 0 and draw 1 as concurrent processes. It now takes a repeatable `--draw`, requires only as
many GPUs as the draws that job runs, and writes the cross-draw `generation_summary.json` only
once **both** draws are finalized; a job that finishes its own draw first reports
`status: draws_incomplete` and exits zero rather than failing. Detection is unchanged and still
requires the complete summary, so it is now a separate `--stage detection` step. Nothing about the
watermark, the sampler, the detector, the cohort, the split, or the protocol changed; the frozen
protocol digest `ad950bfd…87523d32` is unaffected. Because the runner's own source hash is part of
`run_identity.json`, the pre-change smoke root was discarded; it held no generated data.

### Why nothing started at first: a maintenance reservation, not a partition choice

The `gpu-a100` jobs and the first `gpu-a100-small` jobs all sat in `ReqNodeNotAvail`. The cause was
the `Beegfs_Maintenance_Sept2026` reservation, which starts 2026-09-22T08:30 and covers
`c301-[001-004]` (every `gpu-a100-dev` node) and `v330-[001-024]` (every `gpu-a100-small` node).
With about 18 hours left before it began, Slurm would not start a 48-hour job on any partition.
Lowering the request to 12 hours made the jobs schedulable immediately; the pending reason changed
to `Priority`/`Resources` and the first job started within seconds. Keep `-t` under the remaining
window before the next reservation (`scontrol show reservation`).

### Two node-level faults found and fixed

1. **`c301-002` has a failed A100** (see Gate 3). `c301-001` exposes three healthy A100s, so the
   fault is specific to that node, not to the partition.
2. **The preflight itself broke the job on `gpu-a100-small`.** The original preflight called
   `ctypes.CDLL("libcuda.so.1")` and `cuInit` *before* `import torch`. On the shared `v330` nodes
   that made the subsequent torch import fail with
   `ImportError: cannot load module more than once per process` from numpy's extension, killing
   jobs `3460007`–`3460010` in under a minute. The preflight is now
   `scripts/hpc/check_v2_fpr_node.py`, which imports torch first and only inspects
   `/dev/nvidia-uvm` when torch reports no usable device — the same order the runner itself uses.
   It also runs a real device allocation, not just enumeration. Confirmed working: job `3460006`
   printed `preflight OK` on `c301-001` and began Carbon smoke generation on two GPUs.
   `PYTHONPATH` and the XALT `LD_PRELOAD`, both inherited through `--export=ALL`, were tested and
   are *not* the cause; the driver still unsets `PYTHONPATH` as hygiene.

### `gpu-a100-small` cannot run this environment

Every job placed on a `v330` node died within about fifteen seconds on a plain `import torch`:

```
ImportError: cannot load module more than once per process
  .../numpy/_core/multiarray.py, line 11: from . import _multiarray_umath, overrides
```

Four distinct nodes (`v330-008`, `v330-009`, `v330-011`, `v330-012`) failed identically, while the
same interpreter and the same conda environment import cleanly on `c301-001`, `c304-005`,
`c308-002`, and `c316-002`. Tested and excluded as causes: the inherited `PYTHONPATH`, the XALT
`LD_PRELOAD`, heredoc-versus-file invocation, and loading `libcuda` before torch. The fault is
specific to those shared VM nodes, so the partition is unusable here and is worth a TACC ticket.
`gpu-a100-dev` and `gpu-a100` are unaffected.

### Measured throughput (2026-09-21, full 512-token profile)

From the running jobs, per prompt and per draw, covering both the ordinary and the SynthID arm:

| Model | Ordinary | SynthID | Per prompt | 1,608 prompts, two draws on two GPUs |
|---|---|---|---|---|
| Carbon-500M | 10.9 s | 12.6 s | 23.7 s | ~10.5 h |
| GENERator-v2 1.2B | 9.8 s | 11.4 s | 21.3 s | ~9.5 h |

GENERator is not materially slower than Carbon despite being 1.2 B against 500 M; an earlier
estimate that assumed a 2.3x penalty was wrong. Both jobs hold a 14-hour walltime, so each is
expected to finish its generation inside one allocation and before the maintenance reservation.

### Submitted batch jobs (2026-09-21)

| Model | Slurm job | Partition | Node | Stage | Result |
|---|---|---|---|---|---|
| Carbon-500M | `3460006` | `gpu-a100-dev`, 2 h | c301-001 | smoke | **passed**, 4/4 shards per draw, summary written |
| Carbon-500M | `3460042` | `gpu-a100`, 14 h | c308-002 | full generation | running |
| GENERator-v2 1.2B | `3460043` | `gpu-a100`, 14 h | c316-002 | smoke + full | smoke **passed**; full generation running |

Both models have now cleared the protocol's smoke gate on real hardware, which exercises the whole
chain: cohort load, configuration comparison, immutable run identity, two-GPU generation of both
arms, keyed recomputation, and per-draw finalisation.

Superseded: `3459822`/`3459823` and `3459922`-`3459925`, cancelled while pending because a
48-hour walltime cannot start before the maintenance reservation; `3460007`-`3460010` and
`3460022`-`3460025`, failed on `gpu-a100-small` for the reason above.

Each job runs digest checks, a GPU preflight, the smoke gate, then full generation for its own
draw. Slurm logs land in `outputs/synthid_v2_fpr_logs/`. Resubmitting an identical line resumes:
completed per-prompt shards are validated and skipped. Once all four draws are finalized, run
detection once per model:

```bash
sbatch --export=ALL,GSW_MODEL=carbon,GSW_STAGE=detection    scripts/hpc/synthid_v2_fpr_small.sbatch
sbatch --export=ALL,GSW_MODEL=generator,GSW_STAGE=detection scripts/hpc/synthid_v2_fpr_small.sbatch
```

Detection is CPU bound; `gpu-a100-small` nodes have 32 cores, so `--workers` may need lowering from
its default of 16 only if memory pressure appears.

### How to start the run on a healthy node

`scripts/hpc/synthid_v2_fpr_direct.sh` is the resumable driver and
`scripts/hpc/synthid_v2_fpr.sbatch` the batch wrapper. The driver re-verifies the protocol and
cohort digests, then runs a preflight that opens `/dev/nvidia-uvm` and requires two usable A100s,
so a node with this fault stops immediately instead of failing part way through.

```bash
# From a login node (preferred; the partition excludes the faulty node):
sbatch --export=ALL,GSW_MODEL=carbon    scripts/hpc/synthid_v2_fpr.sbatch
sbatch --export=ALL,GSW_MODEL=generator scripts/hpc/synthid_v2_fpr.sbatch

# Or inside a fresh healthy allocation:
idev -p gpu-a100-dev -N 1 -n 1 -t 2:00:00 -A MCB25091 --exclude=c301-002
bash scripts/hpc/synthid_v2_fpr_direct.sh carbon all
bash scripts/hpc/synthid_v2_fpr_direct.sh generator all

# Progress at any time, without running anything:
python3 scripts/hpc/run_direct_synthid_fpr.py --model carbon --profile full \
  --cohort-jsonl data/processed/ncbi_refseq_eukaryote_windows_fpr_v2_1608/prompts.jsonl \
  --output-root /scratch/10899/kimopro/synthid_v2_fpr/carbon --status
```

Repeat the identical command in each new allocation to resume. Until both models' full generation
and detection are finalised and the strict validators pass, L1-01 is `not_run` in the Results Delta
Packet; no false-positive rate is reported from partial shards.


## Results and admission (2026-09-24)

Generation finished on 2026-09-22 inside a single allocation for each model: Carbon job `3460042`
in 10:44:41 on c308-002, GENERator job `3460043` in 09:55:37 on c316-002, both `COMPLETED`.
Detection ran on 2026-09-24 as CPU-only jobs `3467948` and `3467949` on `development` nodes with
64 workers, in 6:07 and 5:41.

### Acceptance gate

| Gate | Result |
|---|---|
| Generation shards | 1,608/1,608 per draw, both draws finalised, both models |
| Generation summary | `case_count` 1608, `sequence_count` 6432, 512 tokens, `complete: true` |
| Detector shards | 1,544/1,544, both models |
| Strict validators | `status: ok`; 37,056 decisions, 1,544 prompts, 12 rate cells per model |
| **Protocol digest** | recorded digest equals the protocol document for **both** models |
| Prompt split | 64/1,544, byte-identical across models (`e3a2ff9e…`) |
| `check_evidence.py` | passes: 72 measurements, 21 artifact digests, 13 documents |

The protocol-digest row is the version-one failure that L1-02 documents. It does not recur here.

### Primary result

Detection power is 3,088/3,088 reads in every condition for both models, so the correct-key lower
exact bound is 99.76%; the protocol's failure thresholds are 0.95 clean and 0.90 under one edit.

In the primary control family, ordinary output under the corresponding key, the exact one-sided
95% upper bounds on the prompt-level false-positive rate are:

| Condition | Carbon-500M | GENERator-v2 1.2B |
|---|---|---|
| clean | 3 positives, **0.5014%** | 5 positives, **0.6797%** |
| substitution | 3, 0.5014% | 5, 0.6797% |
| insertion | 3, 0.5014% | 6, 0.7655% |
| deletion | 4, 0.5919% | 7, 0.8499% |

Every primary cell is at or below the predeclared eight-positive threshold, so every primary bound
is below the 1% target. The largest is 0.8499%. This answers PAT-W4, where the version-one bound
was 2.87% from one positive prompt in 192.

In the separately reported wrong-key family, `carbon deletion_1nt` has 9 positive prompts and a
bound of 1.0150%, above 1%. It is recorded as observed, with no claim that the 1% operational rate
holds for the wrong-key family.

### Artifacts and derivation

Per-model `summary.json`, `report.md`, and a reproducibly compressed `trials.jsonl.gz` are retained
under `outputs/{carbon,generator}_synthid_v2_fpr_position_independent/`. The gzip uses `-n` so the
bytes are reproducible, and each archive was verified to expand to the original digest. The
one-sided bounds are derived by `scripts/derive_synthid_v2_fpr_evidence.py` into
`evidence/derived/synthid_v2_fpr_rates_2026_09_24.json`; the detector summary itself stores only
the two-sided interval. That script self-checks against the three bounds the protocol predeclared
(0.19384%, 0.93294%, 1.49200%) before emitting anything.

### One code change between generation and detection

The detector scripts validated generation rows against the *detector* experiment id, while v2
generation rows carry the *generation* id, so detection could not start. The check was an
unexercised addition: version-one generation rows carry no `experiment_id` at all. Both detectors
now take `--generation-experiment-id`, defaulting to `--experiment-id` so version-one invocations
are unchanged. Because the runner hashes its own sources into the run identity, detection records a
separate `run_identity_detection.json` rather than overwriting generation's. The generation script
and the watermark and detector libraries are byte-identical across both stages.


## L1-06 — measured conservatism of the full-search correction (2026-09-24)

PAT observed that windows shifted by exactly six bases share phase and nearly all tokens, so the
per-window binomial statistics are strongly positively correlated and a correction over every
searched hypothesis must be conservative. This measures that headroom on unmarked reads, which are
draws from the null. **It does not change the decision rule.** The reported rule remains the
full-search Bonferroni correction, and these numbers must not be used as a threshold.

### Realized family-wise rate against the 0.01 target

| Model | Corrected decision fired | Rate | Conservatism vs target |
|---|---|---|---|
| Carbon-500M | 13 / 12,352 | 0.1052% | 9.5x |
| GENERator-v2 1.2B | 23 / 12,352 | 0.1862% | 5.4x |

Pooled over the clean and three single-edit conditions, ordinary corresponding-key family.

### Effective independent windows

Under the null, if a read's search behaved like `M_eff` independent uniform tests then
`P(p_min > x) = (1 - x)^M_eff`, whose maximum-likelihood estimate is
`M_eff = -n / sum(log(1 - p_min))`.

| Model | Condition | Hypotheses searched | `M_eff` | Inflation |
|---|---|---|---|---|
| Carbon | clean | 16,136 | 832 | 19.4x |
| Carbon | substitution | 16,136 | 832 | 19.4x |
| Carbon | insertion | 16,144 | 837 | 19.3x |
| Carbon | deletion | 16,128 | 828 | 19.5x |
| GENERator | clean | 16,136 | 852 | 18.9x |
| GENERator | substitution | 16,136 | 848 | 19.0x |
| GENERator | insertion | 16,144 | 837 | 19.3x |
| GENERator | deletion | 16,128 | 844 | 19.1x |

The inflation sits near 19x across both models and every condition.

### Stated limitation

`M_eff` matches the mean of `log(1 - p_min)`; it is not a distributional fit. The `Beta(1, M_eff)`
model reproduces the observed quantiles only to within a factor of 0.54 to 1.23, because local
p-values are discrete binomial tails and neighbouring windows share phase and nearly all tokens.
The artifact stores those observed-over-predicted ratios so the limitation travels with the number.
Read the result as an order-of-magnitude statement that the correction is roughly nineteen times
more severe than the effective test count, not as a calibrated count of tests.

## Source manifest (L1-01 acceptance gate)

Frozen at `evidence/derived/synthid_v2_fpr_source_manifest_2026_09_24.json`: 83 files, source tree
`3a9b71f84a8f842e7fb56c92f3a89447bb7bc7b92f730595aa63b96cf20ad655`.

Extending `scripts/hpc/freeze_source_manifest.py` to cover this run exposed that Carbon's
position-independent runner and validator were missing from its file list while GENERator's were
present, so Carbon's detector sources had never been covered by a frozen manifest. Both are now
included, together with the v2 configs, the v2 protocol, the v2 cohort files, and the new v2
scripts.

Its `--verify` mode cannot pass immediately after a freeze in a dirty worktree: the manifest
records a digest of `git status --porcelain`, and writing the manifest changes that status. Every
tracked file digest is identical between a fresh build and the stored manifest, so source integrity
is intact; only the worktree-cleanliness field differs. Run `--verify` from a clean tree.
