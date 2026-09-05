# Source-grounded electrical reconstruction

Read each local branch in the source image before constructing routes. Count devices and follow conductor paths, not just visual alignment. Supply bars and sideways ground symbols are not capacitors. Connection dots, wire endpoints and deliberate gaps matter. Treat signal arrows as annotations unless the source defines a directed component.

For each transistor inspect G/D/S or B/C/E from the actual symbol convention. Mirror or rotate symbols and pins together. Current-source circles and voltage-source circles are native typed components with A/B pins; dependent-source labels describe the control relation, while all electrical terminals remain auditable.

For dense schematics use local regions with explicit boundary endpoints. Keep meaning across regions even when improving layout. Repeated parts share a calibrated size profile; transistor/electrical lead distances do not determine body height. Visually compare body sizes at matched display scale. For rectangular TL sections preserve source identity and orientation without guessing impedance or electrical length.

Regression cases that motivated this skill:

- In the small-signal source figure, the input connects only to Cgs upper terminal. The upper terminal of the current source, Cds and Rds is a distinct node. Record a must-separate pair between Cgs.A and the current source A. Do not join nearby horizontal lines across the visible gap.
- The upper right symbol in that figure is a sideways ground, not an added series capacitor. Inventory/type checks should reject that extra component.
- In the RF LNA figure, R16 lower terminal joins the TL14/TL15 node; L5 lower terminal joins the TL17/C12 node. Neither is an intentional open end.
- In the complete RF LNA example, source inspection shows a series C7-R14-TL13 branch between the M3 gate and drain. M3 is vertically mirrored: its upper source connects through TL12 to ground. TL13 is vertical, with its top at the drain-side junction and its bottom connected to R14. Do not infer a parallel path from the functional highlight.
- C2, C5 and C13 in that example terminate at sideways ground symbols, not open stubs. R7 connects above TL4; the current-reuse R9 branch joins below TL6. These are observations of this specific reference, not universal topology rules.
- An actual open inductor stub in a source image may be intentional. Document its crop and visible endpoint rather than forcing an invented ground.

These are examples of failure patterns, not defaults to impose on unrelated circuits. Freeze expected nets from the current source and visually verify the boundaries. If a symbol variant is unsupported, add named pins and transform tests to a task-local skill copy before using it; do not change the installed older skill.
