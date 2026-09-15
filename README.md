# 3D print: OpenSCAD to 3MF (`3d-print-openscad-3mf`)

A [Claude Code](https://code.claude.com) skill for designing 3D-printable
parts: model in OpenSCAD, reverse-engineer exact dimensions from an existing
3MF/STL so the new part mates with it, verify mechanisms before printing, and
package everything into a Bambu Studio project `.3mf` with named plates.

It comes in two layers:

- **General** (`SKILL.md`, `REFERENCE.md`): measuring meshes, printability,
  the 3MF anatomy, and a checklist for anything with moving parts: sweeping
  every pair of parts through the cycle for collisions, computing real travel
  extremes, checking that every part can reach its seat, screw engagement,
  what breaks first under abuse, pinch points.
- **Domains** (`domains/`, `lib/`): what a specific object system imposes on
  top, with measured numbers and a SCAD library to `use <>`. Currently:
  wooden train track (BRIO / IKEA LILLABO / Hape), from connector profiles to
  how tall a bridge must be for a train to pass under.

Scripts (`scripts/`, Python 3 + numpy, OpenSCAD on `PATH`):

| Script | What it does |
| --- | --- |
| `measure.py` | `info`, `levels`, `profile`, `section`, `scan` (hole or boss?), `orient` (level a mesh saved at an angle) |
| `sweep.py` + `sweep_template.scad` | interference sweep: every pair of parts x every step of a driving variable, reports volume and location of anything that touches |
| `make3mf.py` | pack STLs into a Bambu project: `part.stl:"Name"@"Plate"`, per-object tree supports, cover, gallery pictures, description |
| `check3mf.py` | validate a `.3mf`: `<build/>` present, project settings, objects on the bed, no overlaps per plate, plates instance every object |

## Install

Pick one. All three give you the same files; they differ in how you update.

### 1. As a plugin from this marketplace (recommended for users)

Inside Claude Code:

```
/plugin marketplace add RuBiCK/3d-print-openscad-3mf
/plugin install 3d-print-openscad-3mf@rubick
```

Update with `/plugin update 3d-print-openscad-3mf@rubick` (or `claude plugin update
3d-print-openscad-3mf@rubick` from a shell). The marketplace entry also declares
`autoUpdate: true` for Claude Code versions that honour it; 2.1.x reports the
field as ignored, so do not count on it yet.
The skill is then available as `/3d-print-openscad-3mf` and Claude also picks it
up on its own when a task is about printable parts or 3MF files.

### 2. As a personal skill via git (recommended if you want to edit it)

```sh
git clone https://github.com/RuBiCK/3d-print-openscad-3mf ~/.claude/skills/3d-print-openscad-3mf
```

It loads in every project on your machine. Because the folder carries a
`.claude-plugin/plugin.json`, Claude Code treats it as a skills-directory
plugin (`3d-print-openscad-3mf@skills-dir`): no install step, and edits to
`SKILL.md` take effect immediately. Update with `git pull` in that folder.

### 3. Inside a project, for a whole team

```sh
git submodule add https://github.com/RuBiCK/3d-print-openscad-3mf .claude/skills/3d-print-openscad-3mf
```

Everyone who clones the project gets it; update with
`git submodule update --remote`. Project-scope plugins only load after the
workspace trust dialog and when Claude Code is launched from the repo root.

## Use

Just describe the task ("make a lid that fits this box.3mf", "review this
crank mechanism before I print it", "package these STLs for my P2S") and
Claude loads the skill. The workflow it follows is in `SKILL.md`; the long-form
rules are in `REFERENCE.md`; the wooden-train specifics in
`domains/wooden-train.md`.

The scripts also work on their own:

```sh
S=~/.claude/skills/3d-print-openscad-3mf/scripts
python3 $S/measure.py scan box.3mf --at -7 --along x
python3 $S/sweep.py chk.scad --parts housing lever wheel --var angle 0 360 --step 10
python3 $S/make3mf.py -o set.3mf --donor my-exported-project.3mf --cover render.png \
        a.stl:"Housing"@"1 Housing" b.stl:"Lid"@"2 Small parts" c.stl:"Knob"@"2 Small parts" \
        --support "Housing"
python3 $S/check3mf.py set.3mf
```

`--donor` is any project you exported from your own Bambu Studio: the new file
inherits its print profile, so it opens for your printer without prompts.

## Contribute

- Fixes and new general rules go in `REFERENCE.md`; keep them free of any
  particular object.
- A new object system (another toy, a rack standard, a camera mount) gets
  `domains/<name>.md` and `lib/<name>.scad` on the same pattern: a table of
  measured dimensions with their sources, how pieces connect, what clearances
  the system needs, what worked.
- Measured means measured on a mesh or with calipers, with the source named.
  Numbers guessed from photos do not go in.
- Run `claude plugin validate .` before opening a pull request.

## Versioning

`plugin.json` deliberately has no `version` field: Claude Code then uses the
commit SHA, so every push is an update for marketplace users. Tags mark
notable states for humans; they do not gate updates.

## License

MIT. See `LICENSE`.
