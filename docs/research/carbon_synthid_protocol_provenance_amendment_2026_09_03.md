# Carbon position-independent protocol provenance amendment

## Finding

During the 2026-09-03 manuscript-evidence consolidation, the immutable Carbon detector summary was
rechecked with the current strict validator. All 4,608 trial identities, detector decisions,
probabilities, counts, read lengths, search sizes, coordinate transforms, and source-artifact
digests validated. The final provenance check then found one mismatch:

| Item | SHA-256 |
|---|---|
| Protocol hash recorded inside the immutable result | `f0feca50e0af76119d2f9d40f3e6b203c6af2a04191383aa4cdec6737241684c` |
| Current `carbon_synthid_position_independent_validation_protocol.md` | `d7aac7f40a0fd70a2e074eed197aa1ff776dda669542eb57513f7771227a9c70` |

The exact bytes of the originally hashed protocol document are not present in the retained
workspace or source manifest. The current document states the same operational model, revision,
prompt split, draw count, key mapping, families, read conditions, region lengths, orientations,
search counts, and 0.01 decision rule that are independently recorded and checked in the immutable
summary and trial files. Nevertheless, semantic agreement is not byte-level provenance.

## Consequence

This is a documentation-provenance defect, not evidence that a sequence, detector statistic,
threshold, or result count changed. The immutable summary and trial hashes still match the evidence
ledger, and the scientific validator reaches only this final protocol-file check before failing.
The original result must not be edited to replace its recorded protocol hash with the current one.

The current Carbon detector numbers remain transparently labeled draft evidence, with this
amendment attached. A new paper-bound replay is the clean resolution:
freeze the current protocol under a new result identity, rerun the model-free detector on the same
immutable generations, and admit the new artifact rather than overwriting the old result. Until
that replay is complete, manuscript review must retain both the Linux-CPU limitation and this
protocol-provenance caveat.

The GENERator protocol and result hashes match and are unaffected by this finding.
