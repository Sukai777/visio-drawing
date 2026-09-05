# Version 2 input contracts

Two separate JSON documents are required. The evidence records what the source says; the model records how to draw it. The compiler enforces their agreement but cannot independently read an image. Never generate the evidence nets by traversing the final drawing's wires.

## Evidence

`source`: reference image path relative to the evidence JSON. `reviewed_from_source: true` means the author inspected that image. `panels`: `{id,bbox:[x,y,width,height]}` in full reference pixels. `inventory`: `{id,type,panel,bbox,text?,runs?,role?,parent?}`. Bounds locate each reference object, not a demanded output size. Optional `body_bbox` can document measured symbol body separately from source lead endpoints. `labels`: all standalone source text as plain strings after concatenating text runs. Put component-internal labels in inventory `text`, not again in labels.

For circuits: `nets` maps names to arrays of `ID.PIN`; assign each electrical device terminal once (ground/pad optional). Ground symbols are internally common within `ground_domain` (default `0`). Panels do not imply a common or distinct electrical domain: assign it explicitly when domains differ. `must_connect` and `must_separate` are arrays of endpoint pairs. `open_pins` maps every intentional single-terminal net to a concrete image reason. Legitimate open stubs are allowed. Do not call an accidentally omitted wire intentional.

`junctions:[{id,panel,bbox}]` records every visible modeled connection dot from the source. The visible model node IDs/panels must match exactly, so a dot cannot silently disappear. Hidden route nodes need no source inventory entry. Optional inventory `color` and `fill` enforce semantic color roles when the source uses color to distinguish meanings.

For flow/block diagrams: `edges` is an array of `{from,to,label?,arrow?}`. Named ports and direction count; branch labels count; duplicate edges count. `arrow` is `end` (default), `both`, or `none`. Record container `parent` and semantic `role` (e.g. decision, subsystem) in both documents. `uncertainties` lists unresolved source ambiguities; these prevent completion, not draft rendering. `revision_reason` explains evidence corrections in new lock versions.

## Model

Required roots: `version:2`, `canvas:[width,height]`, `panels`, `components`, `wires`, `labels`. Optional `nodes`, `styles`, `annotations`, `font`, `inches_per_unit` (default .015), `transform_test_ids`.

Panels: `{id,at:[pageX,pageY],size:[pageWidth,pageHeight],scale:1}`. Positions within a component/label/annotation are local to its panel. Scale applies to positions and dimensions, not font point sizes. Panel `size` describes the output crop in page units. Model and evidence panel IDs must match.

Components share `{id,type,panel,at:[x,y],anchor?,rotate?,flip_x?,flip_y?,text?,runs?,font_size?,color?,fill?,weight?,role?,parent?}`. Positive rotation is counterclockwise. `at` locates the chosen named pin; absent `anchor`, it locates the center. IDs contain letters, digits, hyphens or underscores; no dots. Labels do not move/rotate with electrical symbols: add separate labels.

Electrical types: resistor/capacitor/inductor A(top),B(bottom); nmos G(left),D(top-right),S(bottom-right); pmos G(left),S(top-right),D(bottom-right); nmos4/pmos4 G,D,S,B; npn/pnp B,C,E; ground P; pad A(left),B(right),T(top),U(bottom), all equipotential; line_section A(left),B(right); current_source/voltage_source A(top),B(bottom). Current-source arrow points A to B; rotation/mirroring transforms it together with pins.

Circuit size: `profile` selects a styles entry (defaults to type); profile `{span:48,aspect?:0.333,source_reason?:...}` controls native unrotated symbol size. For a line_section span is width; otherwise span is height. For R/L/C and source circles, prefer `{body_width:32}` or `{body_height:40}` (one dimension only). `assets/body-metrics.json` contains measured native body fractions excluding fixed leads; the compiler converts the requested visible body dimension into full symbol size automatically. Native aspect is preserved unless a reference-calibrated profile explicitly overrides it. Per-object `size:1` is uniform; deviations >25% require `size_reason`. Existing native masters include short fixed leads; additional distance is drawn with wires, never by stretching the symbol body. Use `body_bbox` and the catalog preview for source calibration. Native R/L/C style may differ from a reference; exact coil count is not guaranteed.

`align:{x:"other.PIN",y:"other.PIN"}` optionally aligns the anchor to real pins of an earlier component. Put dependencies first; an anchor is required for align. Let the renderer calculate transistor offsets. Do not approximate to 30 pixels or hand-calculate long decimal offsets.

Generic types: process (rectangle), decision (diamond), terminator (oval), data (parallelogram), ellipse, container (background rectangle). Specify `w,h`; ports are L,R,T,B. Text is editable. Container membership is recorded and geometrically checked; this does not create a native Visio Container List or promise drag-together behavior.

Nodes: `{id,panel,at,diameter:4,hidden:false,color}`. A junction has pin P. For an electrical crossing use different nodes/route waypoints if unconnected; share an explicit junction for a connection. Shared coordinates alone never join nets.

Wires: `{id,from,to,kind:"wire",net?,route:"hv",via?,panel?,color?,weight?}`. `kind:"edge"` is a generic directed relationship with `arrow` and optional `label`; electrical wires forbid arrows. `via:[[x,y],...]` must be nested coordinate pairs local to `panel`. With no via, the actual pin positions define a route; `hv` or `vh` determines elbow order. `strict` rejects any diagonal segment. Bends are glued to hidden native nodes; device end connections survive moves, but elbow routes may need rerendering after manual edits.

Labels: `{panel,at,w,h,font_size:14,style:3,color,text}`. Style 0 regular/1 bold/2 italic/3 both. For subscripts use `runs:[{text:"V"},{text:"DD",sub:true}]`; `text` becomes `VDD`, without a literal underscore. Multiple independently sub/sup ranges and mixed styles are supported. Additional explanatory labels must set `role:"annotation"`; source labels otherwise match the evidence inventory exactly.

Annotations only: `{kind:"frame",panel,at,w,h,color,fill?,rounding?,purpose}` or `{kind:"arrow"|"line",panel,points:[[x,y],...],color,purpose}`. No electrical symbols here. Frames are sent behind wires/symbols. For complex scientific figures decompose into supported native modules plus labeled relations; arbitrary icons/plots require a separately tested typed implementation or disclose the unsupported content.

For native frame annotations, optional `rounding` sets the corner radius in page units. It is cosmetic and does not create an electrical device.
