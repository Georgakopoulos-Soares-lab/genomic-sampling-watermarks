# Runtime envelope protocol

Frozen before assembling any runtime claim.

## Question

Does the required experimental path run on the declared hardware, and what does each stage cost in
wall-clock time?

This underwrites the contribution claim that the evidence pipeline is laptop-reproducible. It is not
a benchmarking study and makes no claim about other hardware.

## What may be claimed

Wall-clock time and throughput, taken from completed, already-admitted experiment artifacts. No new
runs are performed: the runtimes were recorded by the experiments themselves, so assembling them
introduces no new measurement.

Every runtime is a single observation on one machine under an uncontrolled desktop load. It is a
feasibility figure, not a benchmark, and must be reported with that word.

## What may not be claimed, and why

**Peak memory is not admitted.** The three memory fields recorded by the runners cannot support a
residency claim:

- `process_peak_rss_gib` is a true process peak from `getrusage`, but on Apple unified memory it does
  not capture Metal-side allocations, so it understates GPU-side use.
- `mps_current_allocated_gib` is the allocation at the moment it was sampled, after the loop and
  before cleanup. It is not a peak.
- `mps_driver_allocated_gib` is a driver counter. In the `C_tok` generation run it reports 52.31 GiB
  on a machine with 48 GiB of unified memory. A figure above physical memory cannot be resident-set
  usage, so the counter must include reused or cumulative blocks.

Reporting any of these as "peak memory" would be a false claim about fitting in 48 GiB. The honest
statement is that the required path completes on the declared machine, which the completed runs
demonstrate, and that a defensible peak-memory figure needs instrumentation this project does not yet
have.

**Open item.** Add a sampled high-water measurement — for example polling
`torch.mps.current_allocated_memory()` during the loop and recording the maximum, alongside resident
set size — before any memory number is admitted.

## Sources

Runtimes are read from artifacts already cited by admitted measurements:

- E2 sequential capacity: `outputs/*_e2_sequential_v2.json`
- E4 matched generation: `outputs/*_e4_generation_v1.json`
- E4 clean detection: `outputs/*_e4_detection_v4.json`

The summarizer verifies each artifact digest against the ledger before reading it, so a runtime claim
cannot drift away from the experiment that produced it.

## Result and admission (2026-08-21)

| Policy | Capacity, 3,072 states | Matched generation, 8 x 3,072 bases per arm | Clean detection, 1,472 trials |
|---|---:|---:|---:|
| `C_tok` | 126 s | 393 s | 53 s |
| `G_tok` | 268 s | 1,298 s | 56 s |
| `G_bp` | 280 s | 1,360 s | 56 s |

Watermarked generation throughput is 124 bases per second for `C_tok` and 36 to 38 for the
GENERATOR policies. Clean detection runs at about 27 trials per second with no model and no GPU.

The whole required path — sequential capacity, matched generation, and clean detection, for all
three policies — is **3,890 seconds, about 65 minutes**, on the declared machine.

Admitted: three `[V]` per-policy entries carrying every stage time and throughput, and one `[A]`
derived total. Each entry records that these are single observations under uncontrolled load.

Peak memory is not admitted, for the reasons above. The exclusion is recorded in every entry's scope
so a later draft cannot quietly reintroduce it.

## Boundary

One machine, one operating-system version, one PyTorch version, uncontrolled background load, and a
single observation per stage. No comparison to other hardware, no claim of optimality, and no claim
that a different machine would be adequate.
