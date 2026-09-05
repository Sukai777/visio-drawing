# Blocks, flows and scientific modules

Preserve the directed relationship graph, decisions, labels, feedback loops, hierarchy and semantic roles. Repositioning is allowed; reversing an arrow, dropping a return loop, changing a Yes/No label or moving an object into another logical container is not.

Use process, decision, terminator, data, ellipse and container native shapes. Assign ports explicitly, e.g. `check.B -> finish.T` with label `Yes`, and `check.R -> retry.L` with label `No`. Port choice can change to improve routing only when evidence is revised to distinguish original ports from semantic endpoints; do not silently weaken the direction/label comparison. Use separate typed nodes for a branch merge if the reference shows one; electrical junction dots are usually inappropriate for conceptual arrows.

Prefer a clear dominant reading direction, consistent process dimensions, larger decision diamonds for readable text, and generous return-loop margins. Use a light fill for containers and place them before children. `parent` expresses membership; child bounds are checked. Keep source captions as source labels and separate added explanations with `role:annotation`.

The provided router supports orthogonal hv/vh paths and explicit waypoints, not general graph auto-layout. The AI chooses placement and routes; scripts catch selected geometry errors and preserve glued endpoints. Return loops often need explicit outside waypoints. Review every directed branch in the source/output contact sheet.
