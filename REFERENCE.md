# Reference

## 1. Reverse-engineering a mating part

A 3MF is a zip. `unzip -l file.3mf` shows the layout; meshes live in
`3D/Objects/*.model` as plain XML vertex and triangle lists, and
`Metadata/model_settings.config` gives each object a human-readable name.

Work in this order.

### Find the axis and the feature planes

```sh
measure.py info   file.3mf                  # bbox tells you which axis is long
measure.py levels file.3mf --axis z --min-count 4
```

`levels` lists the coordinates where vertices cluster. Steps, chamfers,
shoulders and the ends of cylinders all land on a shared plane, so this single
command usually hands you the whole feature breakdown of a turned-looking part
in one shot. Raise `--min-count` to filter out tessellation noise on curves.

### Decide whether a feature is male or female

```sh
measure.py scan file.3mf --at -7 --along x --range -10 10
```

This walks a line across the section and prints every solid/void transition.
Two edges means a simple solid. Four or six means an annulus, or a boss sitting
inside a groove. **Do this before designing anything that has to mate.** A head
that looks like it has a hex socket may instead have a hex boss inside a ring
wall, which needs a socket driver rather than an Allen tip — the two designs
have nothing in common.

### Read the sizes

```sh
measure.py profile file.3mf --from 0 --to 20 --step 0.25
measure.py profile file.3mf --from 0 --to 4 --inner 5.6   # only the bore
measure.py section file.3mf --at -7 --max-r 6             # the raw outline
```

`profile` prints across-flats and outer diameter per slice. `--inner R`
restricts the measurement to the outline inside radius R, which is how you read
a bore while ignoring the outer wall.

Across-flats comes from the minimum distance to the section's *edges*. Do not
use vertex radii: slicing a hexagonal prism produces only its six corner points,
so the minimum vertex radius is the circumradius and you would read a hexagon
15.5 % too wide, then design a part that will not enter.

### Watch for lead-in tapers

Moulded and printed recesses often taper over the first millimetre. If the
entry is *narrower* than the bottom, a straight male feature at full size can
never pass the mouth. Profile the first 1.5 mm at 0.25 mm steps before choosing
a size.

### A mesh that was saved tilted

A ramp or a lid exported at an angle has no vertex planes to read. Its flat
faces still point in a handful of directions, and `measure.py orient` lists
them area-weighted: the end faces, mounting faces and rails cluster on the true
horizontal, and a pair 90 degrees apart is a box. Pick the direction, then
`--level DEG --write level.stl` rotates it onto +X; measure the levelled copy
with `profile`/`section` as usual. Example: a ramp saved lying on
its side read as "64.7 mm rise over 216 mm" this way.

### Verify a copied profile

When you rebuild someone else's shank or boss in OpenSCAD, run `profile` on the
original and on your STL over the same range and compare. Anything worse than
0.01 mm means you misread a level.

## 2. Modelling for printability

- **Orientation.** Model with Z up and the part resting on z=0, mating feature
  down. The STL then drops onto the plate with no rotation, and the mating
  feature gets the flat, dimensionally accurate first layers.
- **Blind holes.** Cap them with a cone or pyramid instead of a flat ceiling, so
  nothing has to bridge:
  ```scad
  translate([0,0,DEPTH]) cylinder(h=DEPTH*1.2, r1=hexR(AF), r2=0.01, $fn=6);
  ```
- **Hexagons.** `cylinder($fn=6, r=R)` gives circumradius R.
  `hexR = function(af) af/2/cos(30);` converts across-flats to that radius.
- **Shape transitions.** A circular cone rising straight off a hexagonal prism
  leaves a horizontal ledge over each flat. `hull()` between the two profiles
  lofts it instead; keep the resulting slope within ~45 degrees of vertical:
  ```scad
  hull() {
      translate([0,0,H-0.3]) cylinder(h=0.3, r=hexR(AF), $fn=6);
      translate([0,0,H+BLEND-0.1]) cylinder(h=0.1, d=D_SHOULDER);
  }
  ```
- **Rounding, chamfers, holes for named screws, threads, gears.** Use
  [BOSL2](BOSL2.md) rather than `hull()`/`minkowski()` constructions:
  `cuboid(size, rounding=, edges="Z", anchor=BOTTOM)`,
  `attach(TOP) screw_hole("M3,10", head="socket", anchor=TOP)` inside a
  `diff()`. The `hexR` helper and the cone-capped blind hole above stay useful
  where the profile was measured off a mesh and must be reproduced exactly.
- **Lead-in chamfers.** A 0.2–0.5 mm 45 degree chamfer on every mating edge
  costs nothing and makes assembly forgiving. On the first layer it also
  compensates for elephant foot.
- **Parameters first.** Put every fit dimension at the top of the file with a
  comment giving the measured value it derives from and the clearance applied.
  Add a variant selector (`TIP = "a"`, `LENGTH = "std"`) rather than duplicating
  files; regenerate variants with `-D 'TIP="a"'`.
- **Always** use `--backend=Manifold`, and read the summary: `Status: NoError`
  and the `Genus` you expect (one per through-hole). Export binary with
  `--export-format binstl`; the ASCII default is roughly six times larger.
- **Empty result, no file.** When the top-level object is empty OpenSCAD prints
  "Current top level object is empty" and does not touch the output path. In
  any loop that exports and then measures, delete the target first.
- **Bridges vs. upside down.** A portal printed standing up needs its ceiling
  bridged (36 mm bridges print fine on a Bambu with 45 degree corbels in the
  corners). The same portal printed roof-down has no bridge at all, so when a
  part has one big flat face, consider putting that face on the bed and
  reorienting with a wrapper module.
- **Cutting a housing for a moving part.** Do not guess the clearance around a
  hinged part; subtract its swept envelope. Build the 2D profile, rotate it in
  1 degree steps over the travel plus a margin, `offset(r = clearance)` and
  union: `for (a = [-1 : 1 : max + 2]) rotate(a) offset(r = 0.4) profile();`.
  A part hinged at mid-height moves its lower corner *forward* in the first
  degrees of opening, so a face that is flush when closed needs air (0.3 mm)
  or it binds.
- **Counterbores near an edge.** A Ø7 head recess needs its centre at least
  3.5 mm plus a wall from every edge. If the screw position is fixed by the
  mating part, extend the piece past the edge (an overhang of 3 mm is fine)
  rather than accepting a broken recess.

### Clearances that work

| Fit | Clearance on the fit dimension |
| --- | --- |
| Printed part into a moulded one | 0.30 mm |
| Printed into printed | 0.30–0.40 mm |
| Guide or pilot feature, no torque | 0.5–1.0 mm |
| Snap or detent feature | copy the original geometry exactly, do not add clearance |

Where a feature carries torque, err loose: a hexagon with 0.3 mm of play has
under 2 degrees of backlash, while 0.1 mm too tight will not go on at all.

## 3. Anatomy of a Bambu project 3MF

```
[Content_Types].xml            Defaults for rels, model, png, gcode
_rels/.rels                    -> 3D/3dmodel.model + the three thumbnails
3D/3dmodel.model               metadata, <resources> of components, <build> of items
3D/_rels/3dmodel.model.rels    -> every 3D/Objects/*.model
3D/Objects/object_N.model      one mesh each, and a mandatory <build/>
Metadata/model_settings.config object and part names, the plate, the assembly
Metadata/project_settings.config   the print profile, as JSON
Metadata/cut_information.xml   one entry per object
Auxiliaries/Model Pictures/    gallery images
Auxiliaries/.thumbnails/       thumbnail_3mf / _middle / _small .png
```

Rules that bite:

- **`<build/>` is mandatory in every `<model>`,** sub-models included, even
  empty. Leaving it out is a spec violation: Bambu Studio reports an error and
  falls back to loading geometry only.
- Bambu writes the production extension, so `p:UUID` belongs on objects,
  components, build and items, and components carry `p:path`.
- `Metadata/project_settings.config` is JSON, not XML. Without it the file opens
  as a model rather than a project. Inherit it from any project the user
  exported themselves so the printer matches.
- Bambu's own `[Content_Types].xml` never declares `.config` or `.xml`, and it
  loads fine. Match it rather than trying to be more correct than the tool.
- `Metadata/_rels/model_settings.config.rels` in files from MakerWorld points at
  a `plate_1.gcode` that is not in the package. Harmless; do not copy it.
- The plate previews (`Metadata/plate_*.png`, `top_*.png`, `pick_*.png`,
  `slice_info.config`) are slicing output. A project that was never sliced does
  not have them, so drop them rather than shipping stale ones.
- Object ids and the ids in `model_settings.config` must agree, and the plates
  must instance every object exactly once. `check3mf.py` verifies this.

### Several plates in one project

`model_settings.config` holds one `<plate>` per plate, with `plater_id` 1..n
and a `plater_name` that Bambu Studio shows in the plate list. The build items
in `3dmodel.model` carry *world* coordinates: Bambu arranges plates on a grid
of ceil(sqrt(n)) columns, each stepped by 1.2 x bed size, rows going towards
-Y, and stores the objects at those offsets. So plate 2 on a 256 bed sits at
X + 307.2, plate 5 at Y - 307.2. `make3mf.py` does this when you tag parts
with `@"Plate name"`; parts sharing a name share a plate, in order of first
use, and `check3mf.py` undoes the offset before checking bed bounds and
overlaps per plate. Naming plates by print order ("1 Housing", "2 Deck",
"3 Small parts") is what users end up doing by hand anyway; group the small
parts of a mechanism on one plate and give each big part its own.

Per-object slicer settings go in the same `<object>` block of
`model_settings.config` (`enable_support`, `support_type` = `tree(auto)`,
`brim_type`, ...). `make3mf.py --support "Name"` sets tree supports on that
object, for the one part that has to print upside down with a big overhang
while everything else prints clean.

### The description field

MakerWorld stores the description as HTML-escaped text inside XML, i.e. escaped
twice, so the raw file contains `&amp;lt;p&amp;gt;`. `make3mf.py --description`
takes a file of plain HTML and applies both passes. Useful tags: `<p>`, `<b>`,
`<i>`, `<ul>/<li>`, `<code>`, and entities such as `&Oslash;` for a diameter
sign. Keep the text ASCII and use entities, which travel better through the
double escaping.

Write the description as real documentation: what it fits and how you know,
the measured dimensions with their clearances, print settings, and which
parameter to change if the fit is wrong. It becomes the MakerWorld listing.

## 4. Mechanisms and assemblies

General rules for anything with moving parts, screws or several pieces that
have to go together. They apply to any object; domain notes (what a wooden
train track needs, say) live in `domains/`.

### Sweep the cycle: parts must not collide anywhere in their travel

Renders hide small collisions, and a 1 mm overlap at one angle jams a
mechanism. Copy `scripts/sweep_template.scad` next to the model, fill
`posed(name)` with the same transforms as the assembly view, and run

```sh
python3 $S/sweep.py chk.scad --parts housing lever wheel crank link floor --var angle 0 360 --step 10
```

It intersects every pair of parts at every step of the driving variable and
prints the volume and bounding box of whatever touches. Rules of use:

- Include a floor slab as a "part" so anything dipping below the ground
  shows up.
- Sweep the whole cycle, not the two end positions: the worst point is
  usually somewhere in the middle.
- Run it again after every geometry change; a fix in one place moves the
  collision elsewhere. It exits 1 on any hit, so it can gate a commit.
- For meshing gears, also sweep the *phase* of one wheel over one tooth
  pitch. The intersection at the assembly pose can be 20 mm3 while another
  phase is 0; only the minimum over the pitch says whether the mesh is right.
- Cranks and handles count as parts: the handle's knob and arm must clear the
  lid, the screws heads, and any link that rises under them.

### Compute the real extremes

A linkage's maximum travel is not at the crank's dead point. Evaluate the
output angle over the whole cycle (`max([for (p = [0 : 359]) angle(p)])`) and
cut housings for that value plus a margin, not for a number a formula gives at
one position. Cut the housing with the part's *swept envelope* (section 2),
not with its closed-position outline.

### Assembly path: can every part reach its seat?

For every part with a hole: what does the hole have to pass over on the way
to its seat? A cap with a Ø8.5 bore cannot be lowered over a Ø10 head on the
same one-piece shaft. Fixes: split the cap (a slot open to one side plus a
keeper that closes the bearing, held by a screw that already exists), or make
the journal the larger diameter with a D-flat only where the handle goes. For
every part that drops into a fork or slot: does anything already assembled sit
in its path? Write the assembly order down step by step and check each step
against the geometry before printing.

### Screws (self-tapping BT3x8 and friends)

Engagement = screw length under head - stack thickness under the head. An
8 mm screw through an 8 mm plate with no counterbore engages nothing; the part
is held only by friction under the head. Counterbore so that at least 5 mm
goes into a 2.5 mm pilot. Where a screw doubles as a pivot: pilot (2.5) in the
part that holds it, clearance (3.2-3.4) in the part that turns, head in a
recess, and the instruction "tighten, then back off a quarter turn".

### What breaks first under abuse

Decide who uses it and how hard they pull. A small child on a lever they can
grab is 20-30 N; an adult, several times that. Follow the force through the
linkage to the smallest printed feature. A Ø6 stub printed *across* its layers
with the load 22 mm out on a cantilever is at 20-50 MPa, and PLA fails between
layers at 25-35 MPa. Bearings for anything that can be back-driven: a wide
journal in a split housing (fork in the wall, tongue on the lid), not a pin.
A self-locking drive (worm, high ratio) makes this worse, not better: the
user cannot move the mechanism, so the whole force lands on the weakest link.

### Fingers

A gear mesh or a worm the user can reach is a pinch point, and a reduction
turns a light touch at the crank into real force at the teeth. Close the gear
compartment with a lid and walls; leave open only sides where nothing closes
to below 10 mm.

### Parts that must find each other

Where a moving part has to land in a socket, do not rely on a loose piece
being placed within 0.5 mm. Give the socket a 2 mm 45 degree funnel and let
the light, unfixed part move to meet the heavy one. A funnel tolerates error
in both directions; a wedge or mitre seat tolerates it in one only.

## 5. Remix and licence hygiene

When a design derives from someone else's model, strip their identity from the
metadata or the upload will attach to *their* listing: `DesignModelId`,
`DesignProfileId`, `DesignerUserId`, `DesignerCover`, `ProfileUserId`,
`ProfileUserName`, `ProfileTitle`, `ProfileCover`, `DesignRegion`. Clear
`Designer` and `License` so the user fills them in, set `Origin` to `remix`, and
replace their gallery photos with renders of the actual part.

Credit the source in the description, and check the original licence: the
MakerWorld Standard Digital File License does not generally permit
redistributing derivatives. Say so rather than assuming.

## 6. Troubleshooting

| Symptom | Cause |
| --- | --- |
| "error, only geometry loaded" | a `<model>` without `<build/>`; run `check3mf.py` |
| Opens as a model, no project settings | no `Metadata/project_settings.config`; pass `--donor` |
| Prompt about the printer preset | the donor profile is for another printer; keep the current preset |
| Part floats above or sinks into the plate | the build item's z translation is not `-min_z` |
| Mating feature 15 % too wide | across-flats read from vertex radii instead of edge distance |
| Male feature will not enter | the recess has an inward lead-in taper at the mouth |
| `Genus` is not what the holes account for | coincident faces or a self-intersection in the union; or several disconnected parts in one export (genus is not additive) |
| A BOSL2 cut shows in the preview but the STL has a sealed cavity | `attach(..., inside=true)` without `shiftout=0.01`: the cutter's face is coincident with the parent's face |
| No `Status:`/`Genus:` lines at all after an export | a single polyhedron with no boolean (`PolySet`); normal for a lone BOSL2 shape |
| A collision "went away" after an edit that could not have fixed it | stale STL: OpenSCAD wrote nothing because the result was empty |
| Render is all background | camera inside the part or pointing past it; move it, do not conclude the part is empty |
| Cap or collar will not go on after printing | a bigger diameter upstream on the shaft; see Assembly path |
| Mechanism stiff at one end of travel | the housing was cut for the closed position, not the swept envelope; or a dead-point angle set slightly past the floor |
