# Tested behavior and limits

Validated locally on Windows with Microsoft Visio and PowerShell 7. The task project retains test artifacts and reports; examples bundled here carry source images, hand-transcribed evidence and reusable models.

- `small-signal`: reconstructs panel (c) of the provided reference. Input/Cgs gate node remains distinct from the grounded drain rail. The current source is a native group with named electrical pins. Visible junctions and individually formatted subscripts are retained. Three expected electrical nets are checked.
- `lr-branches`: a selected-branch connectivity fixture extracted from the RF LNA image. Both lower LR terminals join the intended TL/C nodes. Nine nets include explicit region boundary stubs. This fixture intentionally does not reconstruct every object or caption in its broad reference crop; do not deliver it as the complete original image.
- `flow`: conceptual diagram with process boxes, decision, start/end, container, Yes/No branches and retry loop. Five directed relationships and semantic fill colors are checked.
- Additional primitive tests covered data parallelogram off-center ports, ellipse and grouped voltage-source polarity marks. Actual grouped-source and data/decision symbol geometry was inspected. Transform checks settle Visio's lazily recalculated endpoint cells without re-gluing, then check both endpoint coordinates and saved GlueTo targets.

Run meaningful mutation tests after producing the three named examples:

```powershell
& '<python.exe>' '<skill>/scripts/test-regressions.py' --outputs '<work>/outputs' --report '<work>/regression-results.json'
```

Tests reject introduced gate/drain shorts, extra/missing/wrong-type devices, unsupported circuit stretching, unexplained size overrides, open LR branches, reversed/mislabeled arrows, changed parent or semantic color, missing junctions, replaced source evidence, dropped/redirected saved glue, a deleted source, changed saved size, unregistered artwork and stale visual review. Positive checks cover measured body dimensions and distinct ground domains.

These are script/geometry regressions and a visual audit of the examples. They are not an empirical benchmark showing a particular smaller model's accuracy improvement. No guarantee of perfect image understanding. Generic shape support is deliberately bounded; complex custom icons, scientific plots and arbitrary native Visio stencils need additional typed implementations. Layout optimization is chosen by the drawing agent; the router itself only constructs simple orthogonal paths and flags selected collisions.
