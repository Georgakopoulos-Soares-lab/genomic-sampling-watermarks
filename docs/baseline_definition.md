# Baseline definitions

## Model-generation policies

| ID | Model | Policy | Purpose |
|---|---|---|---|
| `C_full` | Carbon | Sample from the full processed vocabulary | Audit control; may emit non-DNA tokens |
| `C_tok` | Carbon | Restrict and renormalize to canonical DNA tokens, then categorical sample | Primary direct-token baseline |
| `C_deployed` | Carbon | Exact selected main-revision policy including all processors | Released-policy control |
| `C_bp` | Carbon `fns` revision | Sample independent base marginals and reconstruct a 6-mer | Optional historical branch baseline |
| `G_tok` | GENERator-v2 | Categorical sample from processed 4,096-way DNA distribution | Research direct-token baseline |
| `G_bp` | GENERator-v2 | Released base-marginal path | Primary released-policy control |

Every empirical table must name the policy ID. “Carbon” or “GENERATOR” alone is insufficient.

## Watermark methods

| ID | Type | Marginal claim | Detection |
|---|---|---|---|
| `none` | Ordinary sampling | Reference distribution | None |
| `partition_mc` | Fair latent bit with maximal coupling to keyed token partition | Exact, conditional on the defined `P_t` | Keyed group agreement / likelihood score |
| `its` | Keyed inverse-transform sampling | Exact under fresh uniform key material | Matched cyclic/permutation score |
| `exp` | Keyed exponential/Gumbel categorical sampling | Exact under fresh exponential variables | Matched key-token score |
| `dipmark` | Distribution-preserving reweighting | As defined by the source paper | Secondary, after independent implementation |
| `kgw` | Green-list logit bias | Not exact-marginal | Distortion-allowing reference only |

## Matched sampling controls

- identical prompt cohort and generation length;
- identical temperature and truncation policy;
- identical model and tokenizer revision;
- paired generation seeds where the method permits a meaningful coupling;
- separate results for direct-token and base-marginal policies;
- no comparison across policies presented as a pure watermark effect.

## Biological proxy controls

Compare against ordinary outputs from the same model policy and prompt. Report GC, canonical k-mer distances, complexity/repeats, ORF summaries when appropriate, and independent-model likelihood. Do not treat closeness on these metrics as biological equivalence.

