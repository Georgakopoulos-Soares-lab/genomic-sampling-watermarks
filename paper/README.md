# Paper workspace

The LaTeX source is under `manuscript/source/`. The manuscript is intentionally a section-level scaffold until E0-E9 produce admitted evidence.

```text
context/       Terminology, contribution frame, claim limits, and source map
manuscript/    LaTeX source and local build output
figures/       Versioned source figures; generated figures stay under generated/
reviews/       Append-only dated reviews
submission/    Final venue-specific package
scripts/       Build and paper integrity commands
```

Build with `./scripts/build.sh`. The script prefers `tectonic`, then `latexmk`.

