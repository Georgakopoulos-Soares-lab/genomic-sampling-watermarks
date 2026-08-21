# Terminology

- **Genomic language model (gLM):** an autoregressive model used here to generate DNA-token continuations.
- **Canonical 6-mer:** a length-six string over A/T/C/G.
- **Direct-token policy:** categorical sampling from a defined distribution over complete 6-mer tokens.
- **Base-marginal policy:** marginalize a 6-mer distribution at each base position, choose six bases independently, and reconstruct a token.
- **Exact marginal preservation:** after averaging over fresh keyed randomness, the sampled token has exactly the declared next-token distribution.
- **Distortion-free:** use only when matching the precise definition of the cited construction; it is not automatically synonymous with multi-query undetectability.
- **Standalone verifier:** receives DNA, a key, and public configuration, but no model, prompt, logits, generation seed, or trace.
- **Phase:** the number of leading bases skipped before fixed non-overlapping 6-mer parsing; values 0-5.
- **Orientation:** forward strand or reverse complement.
- **Null calibration:** distribution of the final statistic after repeating every detector search and selection step.
- **ECC:** an ordinary error-correcting code.
- **PRC:** a pseudorandom error-correcting code satisfying a cited security definition; never shorthand for CSPRNG plus ECC.
- **Biological proxy:** a computable sequence statistic or model score that does not establish function, viability, or safety.

