---
name: 3d-print-openscad-3mf
description: Design 3D-printable parts in OpenSCAD and package them into Bambu Studio project .3mf files, including reverse-engineering exact dimensions from an existing 3MF or STL so a new part mates with it, and verifying mechanisms (interference over a cycle, assembly path, screw engagement) before printing. Use when modelling a printable part, measuring an existing mesh to make something fit it, designing a replacement or adapter for an existing object, reviewing a moving assembly for a child's toy, or building and validating .3mf files for Bambu Studio or MakerWorld.
---

# Printable parts: OpenSCAD to Bambu 3MF

## Quick start

```sh
S="${CLAUDE_SKILL_DIR}/scripts"      # the folder this SKILL.md lives in

# 0. moving parts or a known object system? see 'Two layers' below
# 1. measure whatever the part has to mate with
python3 $S/measure.py info    existing.3mf
python3 $S/measure.py levels  existing.3mf --axis z          # exact feature planes
python3 $S/measure.py scan    existing.3mf --at -7 --along x # hole or boss?
python3 $S/measure.py profile existing.3mf --from 0 --to 20 --step 0.5
python3 $S/measure.py orient  tilted.3mf --level 151.9 --write level.stl  # mesh saved at an angle

# 2. model it, 3. export, checking Status: NoError and the expected Genus
openscad --backend=Manifold --export-format binstl -o part.stl part.scad

# 3b. if it moves: sweep every pair of parts through the cycle
python3 $S/sweep.py chk.scad --parts casa tablero rueda --var crank 0 16

# 4. package (one plate per part, named) and validate
python3 $S/make3mf.py -o set.3mf --title "Name" --description desc.html \
        --donor any-project-you-exported.3mf --cover render.png \
        casa.stl:"Casa"@"1 Casa" tablero.stl:"Tablero"@"2 Tablero" \
        tapa.stl:"Tapa"@"3 Small parts" reten.stl:"Reten"@"3 Small parts" \
        --support "Pillar"          # tree supports on that one object only
python3 $S/check3mf.py set.3mf
```

## Workflow

1. **Measure before modelling.** Never infer a mating feature from a photo or a
   file name. `scan` prints where a line crosses solid material: more than one
   pair of edges means the section is not simply connected, so what looked like
   a socket may be a boss inside a ring. Getting this backwards wastes the whole
   design. A mesh saved tilted: `orient` first, then measure the levelled copy.
2. **Model parametrically**, with the fit dimensions as named parameters at the
   top of the file so a bad fit is a one-line change and a reprint. Variants
   (`punta = "macho" | "inglete"`) as a selector, never as duplicate files.
   Rounded edges, screw holes, threads, gears, hinges and features placed on
   the faces of a body come from [BOSL2](BOSL2.md) (`include <BOSL2/std.scad>`),
   which the user library folder must contain; the install and the verified
   idioms are in that file, including the `shiftout=0.01` every inside cut needs.
3. **Model in print orientation**, Z up, the part sitting on z=0, so the STL
   drops straight onto the plate. A part that is easier to write in its
   assembly pose gets an `_asm()` module plus a wrapper that reorients it.
4. **Verify against the source** when you copy a profile off someone else's
   mesh: run `measure.py profile` on both and compare level by level. Agreement
   should be within 0.01 mm.
5. **If it moves, prove it.** Renders hide a 1 mm collision at 70 degrees of a
   cycle. Write the sweep harness (`scripts/sweep_template.scad`) and run
   `sweep.py` over every pair of parts and the whole cycle; then walk the
   assembly checklist in [REFERENCE.md](REFERENCE.md#4-mechanisms-and-assemblies)
   (can each part reach its place, how much thread does each screw engage,
   what breaks first when a child pulls on it).
6. **Package and validate.** `check3mf.py` exits non-zero on failure, so it can
   gate a commit.
7. **Render pictures** for the gallery with
   `openscad -o pic.png --imgsize=1200,1000 --camera=0,0,15,68,0,32,110 part.scad`.
   Look at every render you make: an all-background image means the camera is
   inside the part or aimed past it, not that the part is fine.

## Non-negotiables

- Every `<model>` in a 3MF needs a `<build/>` element, sub-models included.
  Omit it and Bambu Studio reports an error and loads geometry only. `make3mf.py`
  writes it; `check3mf.py` catches it.
- Without `Metadata/project_settings.config` the file opens as a plain model,
  not a project. Pass `--donor` pointing at any project exported from the user's
  own Bambu Studio, so the profile matches their printer.
- Measure across-flats from the distance to the section's *edges*, never from
  vertex radii. Slicing a hexagonal prism only yields its corners, which reads
  15.5 % too wide. `meshtools.apothem()` does it correctly.
- Check the `Genus` in the OpenSCAD output against what you expect: 0 for a
  solid, +1 per through-hole (a lid with 4 screw holes and a bore is genus 5).
  A stray extra hole or a self-intersection shows up here.
- **OpenSCAD writes no file when the result is empty** ("Current top level
  object is empty"). Delete the target before every export in a loop, or you
  will measure the previous run's file and call a collision "fixed".
- Design so nothing needs support: cap blind holes with a cone or pyramid rather
  than a flat ceiling, keep overhangs within about 45 degrees of vertical, and
  put the mating feature on the plate. A part printed upside down can carry a
  wide flat roof with no bridging at all.
- Clearance for a printed part entering a moulded one: about 0.3 mm on the fit
  dimension. Tighter binds after elephant-foot, looser rattles.
- Never let a hole have to pass over a larger feature on its way to its seat: a
  cap with a Ø8.5 bore cannot be lowered over a Ø10 head on the same shaft.
  Check the assembly path of every part with a hole before printing anything.

## Two layers: general rules and domain notes

- **[BOSL2.md](BOSL2.md)**: installing the BOSL2 library into OpenSCAD and the
  idioms this skill relies on (anchors, `attach()` + `diff()`, `screw_hole()`,
  threads, gears, rounding), each verified with a Manifold export.
- **[REFERENCE.md](REFERENCE.md)** applies to *any* printable object:
  measurement recipes, printability, the 3MF anatomy (including several named
  plates), the mechanism and assembly checklist (sweeping moving parts for
  collisions, computing real travel extremes, whether every part can reach its
  seat, screw engagement, what breaks first under abuse, pinch points, funnels
  for parts that must find each other), remix hygiene, troubleshooting.
- **`domains/`** holds what a particular object system imposes on top of that,
  with measured numbers and a `lib/` file to `use <>`:
  - [domains/wooden-train.md](domains/wooden-train.md) + `lib/wooden_train.scad`:
    BRIO / IKEA 40 mm track. Connector profiles, how pieces drop together,
    65 mm ramp rise, 60 mm train clearance, pillars as track pieces, Mega Bloks.

When a task is about a moving or multi-part object, read REFERENCE section 4
before modelling and run the sweep before packaging, whatever the domain.
When it is about a track layout, read the domain note too and take the
numbers from the library instead of re-measuring. A new object system (a
different toy, a rack standard) gets its own `domains/<name>.md` and
`lib/<name>.scad` on the same pattern: measured table, how pieces connect,
what clearances the system needs, what worked.

Scripts in `scripts/`: `meshtools.py` (importable helpers), `measure.py`,
`sweep.py` + `sweep_template.scad`, `make3mf.py`, `check3mf.py`. They need
only numpy, plus `openscad` on PATH for modelling and `sips` (macOS) for
thumbnails. Models that use BOSL2 also need it cloned into the OpenSCAD user
library folder (see [BOSL2.md](BOSL2.md#install)).
