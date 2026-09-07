# Repository guidance

Follow `AGENTS.md` and read the documents in its stated order. The repository contains only the
SynthID tournament watermark, its matched ordinary sampling control, and the position-independent
SynthID detector. Carbon-500M and GENERator-v2 1.2B are the two paper models. Version-one runs and
the Carbon-only manuscript are legacy development material; new claims require `synthid.v2.*`
evidence.

Do not reintroduce other watermark constructions or their experiments. Do not add multiple-edit,
detector-query, or detector-guided attack experiments: they are outside the declared threat model.
Keep statistical detection claims separate from biological function and from secret-key security.
Every manuscript number must resolve to `evidence/measurements.yaml`.
