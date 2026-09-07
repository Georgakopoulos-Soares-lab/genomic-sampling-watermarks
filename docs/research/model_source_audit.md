# Model source audit

## Carbon

The retained model is `HuggingFaceBio/Carbon-500M` revision
`9796b752108258c1d365089f842e62e6c0547704`. Its tokenizer dependency on Qwen3-4B-Base is pinned to
revision `906bfd4b4dc7f14ee4320094d8b41684abff8539`.

Inside DNA tags, the experiment uses the 4,096 canonical non-overlapping 6-mer tokens. The Carbon
logits are gathered for exactly those tokens and normalized. Both SynthID and ordinary generation
use temperature 1.0, no top-k truncation, and no top-p truncation.

The retained code does not use Carbon's alternate base-marginal branch. Model revision, tokenizer
revision, vocabulary mapping, data cohort, numerical type, device, command, and artifact hashes are
recorded with the completed experiment.

## Supplementary GENERator replication

The replication model is `GenerTeam/GENERator-v2-eukaryote-1.2b-base` revision
`c41b0018da9ee13b9e96ee54647de8da381ccd72`. The upstream GENERator code source inspected for the
adapter was revision `5132e2c35da5d5e9a7dcec7484901be4de864bf6`.

Its tokenizer consists of 32 special tokens followed by all 4,096 canonical non-overlapping DNA
6-mers at IDs 32 through 4,127. The frozen `G_tok` adapter gathers exactly these token logits and
normalizes them once. It uses `<s>` as the prompt prefix, temperature 1.0, no top-k truncation, and
no top-p truncation. The released base-marginal helper is outside the retained experiment.

A real CPU comparison between cached and uncached next-token evaluation gave a maximum probability
difference of approximately 4.15e-7 and total-variation distance of approximately 2.77e-5, within
the declared numerical tolerance. The full artifacts record the model revision, policy, device,
numerical type, cohort, command, and content hashes.
