# Combined research plan

## Research question

Can secret-key sampling preserve the intended next-token distribution of fixed 6-mer genomic language models while leaving a provenance signal that is detectable from DNA alone after substitutions, insertions, deletions, crops, phase changes, and reverse complementation?

This is one cross-model paper. Carbon and GENERator-v2 expose different generation policies around a shared 6-mer alphabet, which makes them complementary evidence rather than separate stories.

## Proposed paper argument

The nominal alphabet size of 4,096 does not establish watermark capacity. Capacity depends on the realized next-token distribution, the mass balance of a keyed partition, the generation policy, and the information lost when DNA edits break token synchronization. The paper therefore moves in this order:

1. audit the exact tokenization and generation implementations;
2. prove and test sampler-level marginal preservation on fixed distributions;
3. measure the real conditional channel on model logits;
4. calibrate a standalone detector over its complete hypothesis search;
5. test robustness and removal under controlled edit channels;
6. add coding or synchronization only when the measured channel justifies it.

## Core construction

Let `P_t` be the next-token distribution over canonical 6-mers. A secret-key function assigns tokens to two groups. Let `q` be the probability mass of group 1 under `P_t`, and let `C` be a fair keyed latent bit. Use maximal coupling:

- if `q >= 1/2`, group 1 is chosen with probability 1 when `C=1` and `2q-1` when `C=0`;
- if `q < 1/2`, group 1 is chosen with probability `2q` when `C=1` and 0 when `C=0`.

After choosing a group, sample from `P_t` conditioned on that group. Averaging over the fair latent bit recovers `P_t` exactly. The expected disagreement between the latent bit and the sampled group is `|q - 1/2|`, so imbalanced mass directly reduces the signal.

The shorter Carbon plan also described always conditioning on `group(token)=C`. That rule is not used here because a fair latent bit would change the marginal distribution whenever `q != 1/2`. The maximal-coupling construction is the shared corrected baseline.

## Sampler families

The initial comparison contains three distribution-preserving families:

1. **Partition coupling**: interpretable channel baseline with explicit mass-balance diagnostics.
2. **Inverse-transform sampling (ITS)**: matched to the robust distortion-free construction and detector family of Kuditipudi et al.
3. **Exponential/Gumbel sampling (EXP)**: an exact categorical sampler with keyed randomness and a matched score.

PRC layers are deferred. A pseudorandom target stream plus an ordinary error-correcting code may be studied as an engineering layer, but it is not called a pseudorandom code.

## Standalone detector

The verifier receives only:

- a DNA string;
- a secret key;
- the public algorithm and detector configuration.

It does not receive the prompt, model, model logits, generation seed, or runtime trace. It normalizes the sequence, enumerates forward and reverse-complement orientations, enumerates all six 6-mer phases, applies configured windows and key offsets, and returns one globally calibrated statistic. The null distribution must repeat the complete search, including any selected synchronization procedure.

## Cross-model design

### Carbon

Carbon uses a hybrid tokenizer: ordinary BPE outside DNA tags and non-overlapping 6-mers inside `<dna>...</dna>`. The main released checkpoints use a standard causal-language-model path. The separate `fns` revision contains a custom base-marginal generator and is treated as an optional branch baseline, not as the default Carbon sampler.

### GENERator-v2

The audited released checkpoint has 4,096 canonical 6-mers plus special tokens. Its custom generation path transforms token logits to four base marginals at each of six positions, independently samples or selects bases, and reconstructs a 6-mer. The paper must compare that released base-marginal path with a direct categorical sample from the processed 4,096-way distribution.

## Evidence layers

### Mathematical

- prove marginal preservation of each claimed exact sampler;
- define detector statistics and hypothesis families;
- state what is conditioned on when calibrating p-values.

### Cryptographic

- use domain-separated keyed derivation for partitions, target bits, offsets, and nonces;
- state assumptions without claiming a security reduction that has not been written;
- evaluate key reuse and many-output attacks separately from one-output distortion.

### Statistical and empirical

- measure entropy, inverse Simpson support, top-1 mass, group mass, information per token/base, and sampler overhead;
- report confidence intervals and the number of independent prompts, sequences, keys, and null trials;
- calibrate family-wise error after the complete detector search.

### Biological proxy

- compare GC content, k-mer spectra, low-complexity/repeat measures, ORFs when contextually appropriate, and independent-model likelihood;
- describe these only as proxies, never as function, viability, or safety.

## Primary evidence package

- Carbon-500M and GENERator-v2 1.2B on MPS.
- Clean outputs and matched unwatermarked outputs at several sequence lengths up to 5 kbp.
- Controlled substitutions, insertions, deletions, mixed edits, crops, reverse complements, and query-based removal.
- Real-logit channel measurements at a pilot-selected number of states; summary statistics for all states and full probability vectors for a stratified audit subset.
- Wrong-key, natural/public-sequence, and unwatermarked-model nulls.
- A reduced Carbon-3B confirmation only if the primary tiers pass and local runtime is acceptable.

## Stopping rules

- Stop construction work if fixed-distribution tests fail exact marginal preservation beyond Monte Carlo uncertainty.
- Stop the current method if E2 shows less than 0.01 mean information bit per base and E4 cannot detect within 5 kbp.
- Treat failure primarily under indels as a synchronization problem, not as evidence for larger models.
- Do not escalate to Carbon-8B or remote hardware to rescue a failed channel.
- Do not claim robustness below a false-positive rate that the calibrated null evidence can support.

