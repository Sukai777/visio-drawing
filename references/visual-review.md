# Regional review and completion

Open each `*.review/<panel>-compare.png` and compare it to the source. Inspect `<panel>-overlay.png` when locating a symbol or size discrepancy; overlay alignment is normalized by panel rectangles and can differ under permitted layout optimization. It is not a similarity score or automated semantic check.

For every panel check: (1) component inventory and type, (2) connection paths and deliberate gaps, (3) symbol direction and body sizes, (4) exact labels/subscripts and branch captions, (5) readability, collisions and panel/container membership. Electrical devices must be connected native primitives; explanatory arrows and frames are not devices. Compare long wires separately from component bodies.

The renderer flags selected object/page bounds, text-height overflow, measured text overlaps, parent bounds, and wires crossing unrelated symbol bounds. Visio TEXTWIDTH/TEXTHEIGHT measure native font metrics for labels; symbol bounds include their fixed leads. These checks are not a comprehensive collision detector. Fix real issues. If a bounds warning is a harmless lead/label arrangement, record a concrete reason and its finding ID in review notes. Do not mark all warnings resolved without inspecting them.

Copy the generated review template to `visual-review.json`, fill the exact current VSDX SHA-256, and mark each check only after inspecting that panel. `findings` holds unresolved issues and must be empty at completion. `resolved_layout_findings` lists IDs actually inspected/fixed; include a `notes` explanation. Re-rendering changes the hash and invalidates the prior review. The finalizer reruns native package checks and refuses incomplete visual review or unresolved source uncertainties.

Native checks establish consistency with a frozen transcription. A human/model visual review is still a judgment, not independent mathematical proof of source interpretation. State results with those boundaries. Do not rewrite source nets to match a mistaken rendering, and do not use a large glued-endpoint count as a quality score.
