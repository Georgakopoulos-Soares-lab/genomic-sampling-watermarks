# SynthID for generated DNA, in plain language

Carbon and GENERator write DNA six bases at a time. At every step each model assigns probabilities
to all 4,096 possible 6-base tokens. Ordinary generation randomly draws one token from those
probabilities. Two ordinary draws can therefore differ even though neither uses a watermark key.

SynthID changes how that random draw is made. A secret key, the preceding four generated tokens,
and each candidate token produce 30 hidden yes/no values. A sequence of small tournaments gives
more chance to candidates with favorable hidden values. The detector later recomputes the hidden
values for the observed DNA. With the correct key, watermarked DNA contains substantially more
favorable values than ordinary DNA.

The detector does not need to know where generated DNA starts. It examines the supplied strand and
its reverse complement, tries every nucleotide start, and tests four fixed region lengths. For each
region it asks how surprising its score would be if no matching watermark were present. It then
applies a conservative correction for every region it examined and returns one answer for the
complete read.

Both full model runs used the same 256 public prompts. Sixty-four prompts were reserved for choosing
between two score summaries; the remaining 192 were used for final evaluation. Every prompt had two
draws, giving 384 sequences in each result cell. The final test separately checked correct-key
SynthID, ordinary model output, and SynthID output with the other draw's key. It tested clean reads
and exactly one nucleotide substitution, insertion, or deletion.

| Model | Correct-key result in every condition | Ordinary false positives | Other-key false positives |
|---|---:|---:|---:|
| Carbon | 384/384 | 1/384 | 0/384 |
| GENERator | 384/384 | 0/384 | 1/384 in clean/substitution/insertion; 0/384 after deletion |

The repeated positives within a model are the same prompt and draw under several read conditions.
They are not separate independent failures. With only 192 independent prompt clusters, the results
are compatible with the intended 1% false-positive rate but cannot prove that the real-world rate
is below exactly 1%.

The quality comparison found no measurable likelihood loss or corrected sequence-summary
difference for either model. This means the tested model-based quality measures did not get worse.
It does not show biological function, viability, or safety.

The keys in the experiments are public fixtures, so the runs can be reproduced but are not
key-security tests. A real deployment key must remain secret. The intended observer does not know
that key and cannot inspect or query detector scores. Multiple-edit and detector-guided experiments
are outside this project.

For manuscript-ready measurements and exact provenance, see
`docs/research/manuscript_evidence_packet.md`.
