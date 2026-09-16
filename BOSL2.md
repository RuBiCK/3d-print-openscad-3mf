# BOSL2 in this workflow

[BOSL2](https://github.com/BelfrySCAD/BOSL2) (Belfry OpenSCAD Library v2) is
the library to reach for when a part needs rounded or chamfered edges, real
screw holes and threads, gears, hinges, or several features placed on the
faces of a body. It replaces the hand-written `hull()` and `minkowski()`
tricks with primitives that take `rounding=`, `chamfer=`, `anchor=`, and it
lets a feature be attached to a face of its parent instead of being placed
with a translate computed by hand.

Docs: <https://github.com/BelfrySCAD/BOSL2/wiki>. Each `.scad` file in the
library documents its own modules in comments, so `grep -n "^// Module:"
~/Documents/OpenSCAD/libraries/BOSL2/screws.scad` is a fast index when
offline, and the `// Example:` blocks under each module are the authoritative
idioms.

## Install

OpenSCAD searches the user library folder printed by `openscad --info`
("User Library Path"). On macOS it is `~/Documents/OpenSCAD/libraries`, on
Linux `~/.local/share/OpenSCAD/libraries`, on Windows `My Documents\OpenSCAD\libraries`.

```sh
LIB=$(openscad --info 2>&1 | sed -n 's/^User Library Path: //p')
mkdir -p "$LIB" && git clone --depth 1 https://github.com/BelfrySCAD/BOSL2.git "$LIB/BOSL2"
openscad --info 2>&1 | grep -A2 "OpenSCAD library path"   # confirm the folder is listed
```

Update with `git -C "$LIB/BOSL2" pull`. BOSL2 has no releases; the clone's
commit is the version. There is no OpenSCAD package for it, and no Homebrew
formula: the clone *is* the install. It needs OpenSCAD 2021.01 or newer; the
2025+ nightlies with `--backend=Manifold` are what this skill assumes.

Check it works before modelling anything:

```sh
echo 'include <BOSL2/std.scad>; diff() cuboid([20,10,5], rounding=1) attach(TOP,TOP,inside=true,shiftout=0.01) cyl(d=3,h=10);' > t.scad
openscad --backend=Manifold -o t.stl t.scad   # expect Status: NoError, Genus: 1
```

## Loading it

```scad
include <BOSL2/std.scad>       // always: shapes, transforms, attachments, distributors
include <BOSL2/screws.scad>    // screw(), screw_hole(), nut(), metric and inch tables
include <BOSL2/threading.scad> // threaded_rod(), threaded_nut(), trapezoidal, ACME
include <BOSL2/gears.scad>     // spur_gear(), worm(), worm_gear(), rack(), bevel_gear()
include <BOSL2/hinges.scad>    // knuckle_hinge(), living_hinge_mask()
include <BOSL2/rounding.scad>  // round_corners(), offset_sweep(), rounded_prism()
include <BOSL2/joiners.scad>   // dovetail(), snap_pin(), rabbit_clip()
```

`include`, not `use`: the library relies on `$`-variables and on functions and
modules calling each other across files, and `use <BOSL2/std.scad>` breaks the
attachment system. Keep the skill's own `lib/*.scad` on `use <>` as before;
a domain library that itself needs BOSL2 does its own `include <BOSL2/std.scad>`.

## The idioms that matter here

All of these were compiled with `--backend=Manifold` and checked with the
genus count; copy them rather than improvising.

### Anchors instead of translates

Every BOSL2 shape takes `anchor=`. `anchor=BOTTOM` puts the part on z=0,
which is the print orientation this skill requires, with no `translate`:

```scad
cuboid([40, 30, 10], rounding=2, edges="Z", anchor=BOTTOM);  // rounded vertical edges only
cyl(d=8, h=6, chamfer2=1, anchor=BOTTOM);                    // chamfer on the top end only
tube(od=20, wall=1.6, h=15, rounding=0.8, anchor=BOTTOM);
prismoid(size1=[30, 30], size2=[20, 20], h=10, rounding=2, anchor=BOTTOM);
```

`edges="Z"` limits rounding to the edges parallel to Z, so the bottom stays
sharp and the first layer keeps its full footprint. `rounding=` on the top
edges of a part that prints standing up is fine; on the bottom edges it
becomes an overhang the slicer has to bridge, use a `chamfer` there or none.

### Attaching features to faces

A child inside a parent's braces is positioned relative to the parent's
anchors. `attach(face)` puts the child on that face pointing outward;
`attach(face, child_anchor, inside=true)` sinks it into the parent and tags it
`remove` so that `diff()` subtracts it:

```scad
diff()
cuboid([40, 30, 10], rounding=2, edges="Z", anchor=BOTTOM) {
    // M3 clearance hole with a counterbore for a socket head, 12 mm deep from the top.
    // screw_hole() tags itself "remove"; anchor=TOP puts its mouth on the face.
    attach(TOP) screw_hole("M3,12", head="socket", counterbore=true, anchor=TOP);

    // a boss on the right face, chamfered at its free end
    attach(RIGHT, BOTTOM) cyl(d=8, h=6, chamfer2=1);

    // a rounded slot 6 mm deep into the front face
    attach(FRONT, TOP, inside=true, shiftout=0.01) cuboid([12, 6, 3], rounding=1.4, edges="Y");

    // four holes on a grid, all through
    attach(TOP, TOP, inside=true, shiftout=0.01) grid_copies(spacing=[30, 20]) cyl(d=3.4, h=12);
}
```

**`shiftout=0.01` is not optional on an `inside=true` cut.** Without it the
cutter's face is coincident with the parent's face; the preview shows an open
slot, but the Manifold export of the box above came out *genus 0* with a
sealed cavity inside and a zero-thickness skin over the mouth. `shiftout`
moves the cutter out past the face and the export is genus 1 as expected.
(`screw_hole()` already extends its counterbore 0.01 above the face, which is
why it does not need it.)

Anchor names: `TOP BOTTOM LEFT RIGHT FRONT BACK CENTER`, combinable as
`TOP+RIGHT` for an edge or `TOP+RIGHT+FRONT` for a corner. Shapes that print
as a set of copies use the distributors: `xcopies(n=4, spacing=10)`,
`grid_copies(spacing=[a, b], n=[nx, ny])`, `zrot_copies(n=6, r=20)`,
`mirror_copy(RIGHT)`.

### Screws, holes, nuts

`screws.scad` knows the metric and inch tables, so a hole is named after the
screw it takes, not after a diameter looked up somewhere else:

```scad
attach(TOP) screw_hole("M3,10", head="socket", counterbore=true, anchor=TOP);  // socket head recessed
attach(TOP) screw_hole("M3,10", head="flat", anchor=TOP);                       // countersunk
attach(TOP) screw_hole("M3,10", head="none", tolerance="self tap", anchor=TOP); // pilot for a self-tapper
screw("M3,8", head="socket", drive="hex");     // the screw itself, for an assembly view or a sweep
nut("M3", thickness=2.4);                       // hex nut, e.g. to cut a nut trap with inside=true
```

`tolerance=` picks the clearance class ("close", "normal" (default), "loose",
"self tap", "tap"); `$slop` (set it once at the top, 0.2 is right for a Bambu on
0.2 mm layers) is what BOSL2 adds around anything meant to slide or thread.
The skill's own rule still applies: for a printed part entering a moulded
one, verify the fit dimension against the measured mesh; BOSL2's tables are
for standard hardware, not for someone else's plastic.

### Threads

```scad
threaded_rod(d=10, l=15, pitch=1.5, anchor=BOTTOM);         // external
threaded_nut(nutwidth=16, id=10, h=8, pitch=1.5);            // internal, hex outside
trapezoidal_threaded_rod(d=12, l=30, pitch=3, thread_angle=30, anchor=BOTTOM);  // lead screw
```

Printed threads need `$slop` around 0.2 and a pitch of at least 1.5 mm on a
0.4 nozzle to engage cleanly. Model the thread on the part that prints
vertical; a thread lying on the bed prints as bridges.

### Gears

```scad
spur_gear(mod=1.5, teeth=20, thickness=6, shaft_diam=5, anchor=BOTTOM);
worm(d=12, mod=1.5, l=20, orient=RIGHT);
worm_gear(mod=1.5, teeth=30, worm_diam=12);
rack(mod=1.5, teeth=20, thickness=6, backing=5, anchor=BOTTOM);
```

`mod` (module) must match between meshing gears; the pitch radius is
`pitch_radius(mod=1.5, teeth=20)` and the centre distance between two spur
gears is the sum of their pitch radii, `gear_dist(mod=, teeth1=, teeth2=)`.
Take the centre distance from those functions, not from a render, and then
sweep the phase over one tooth pitch as [REFERENCE.md](REFERENCE.md#sweep-the-cycle-parts-must-not-collide-anywhere-in-their-travel)
says: BOSL2 gives you an involute, not a guarantee that your housing puts the
axles in the right place.

### Hinges, 2D rounding, sweeps

```scad
knuckle_hinge(length=40, offset=4, segs=5, arm_height=2, anchor=BOTTOM);   // print-in-place hinge halves
linear_sweep(round_corners(square([30, 20], center=true), r=4), h=5);       // rounded 2D outline extruded
offset_sweep(round_corners(square([30, 20], center=true), r=4), height=8,
             top=os_circle(r=2), bottom=os_chamfer(0.4));                   // rounded top, chamfered foot
path_sweep(circle(d=3), arc(r=20, angle=90));                               // a tube along a path
```

`offset_sweep` with `bottom=os_chamfer(0.4)` is a good default for any part
whose first layer matters: it compensates elephant foot without touching the
fit dimension above it.

## When not to use it

- **Measured mating profiles.** A connector copied level by level from a
  mesh (`measure.py profile`) is a polygon to extrude, as `lib/wooden_train.scad`
  does. Rewriting it with BOSL2 primitives adds nothing and risks changing a
  number that was measured.
- **The sweep harness.** `scripts/sweep_template.scad` intersects plain
  modules; keep `posed(name)` as plain transforms. BOSL2 shapes inside the
  posed modules are fine.
- **Tiny parts, many `$fn`.** `rounding=` on every edge of a cuboid generates
  a lot of geometry; on a 0.4 nozzle nothing under 0.4 mm of rounding is
  printed anyway, so leave small edges sharp.

## Gotchas

- `include <BOSL2/std.scad>` must come before any BOSL2 call and before your
  own `$fn`; set `$fn` after it.
- A stray `translate()` between a parent and an `attach()` child breaks the
  attachment: the child no longer sees the parent's geometry. Put the
  translate on the parent, or use `move()`/`up()`/`fwd()` on the child inside
  the attach.
- `diff()` subtracts children tagged `remove` and, with `tag("keep")`, keeps
  something from being cut. Untagged children are unioned. If a hole is not
  appearing, it is untagged.
- A single BOSL2 shape with nothing subtracted exports as a `PolySet` and
  OpenSCAD prints no `Status:` or `Genus:` line for it; that is normal, the
  checks appear as soon as a `diff()` or union is involved.
- The `Genus` line only means something for one connected solid. Two parts
  side by side in one export read as *genus = sum - (n - 1)*: a box with one
  hole plus a separate rod reports genus 0. Export each part on its own, as
  the skill's workflow does anyway.
- BOSL2 warns loudly (`WARNING: ... in file ...`) when an anchor or a
  parameter is wrong and still produces something; grep the export output
  for `WARNING` as well as `Status:`.
