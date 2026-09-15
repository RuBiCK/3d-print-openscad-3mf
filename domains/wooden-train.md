# Domain: wooden train track (BRIO / IKEA LILLABO / Hape / clones)

Everything here is specific to the 40 mm wooden track system. The general
rules for printable parts and mechanisms are in `../REFERENCE.md`; this file
only adds what the track system imposes. Library: `../lib/wooden_train.scad`
(`use <>` it; every number below is a parameter there).

## Measured dimensions (from meshes of real pieces, not estimated)

| Feature | Value | Source |
| --- | --- | --- |
| Track section | 40 wide (39.8 measured) x 12.0 thick | `jointbrio_3pcs.3mf`, ramp mesh |
| Wheel grooves | 5.4 wide measured, model 6.0; 3.0 deep; centres at +-13.0 | ramp mesh |
| Male peg | neck 6.0 wide, round head Ø12.0 centred 11.0 from the face, cut flat at 17.0 | `jointbrio_3pcs.3mf` |
| Female socket | funnel mouth 15.4 (2.5 deep), neck 7.3, chamber Ø12.7 centred 11.0, floor at 17.5 | `wood-train-turnplate-less-mats.3mf` |
| Long straight "D" | 216 between connector faces | catalogue, matches ramp |
| Ramp (ascending track) | rises 64.7 over 216; ends 12 thick | `ramp-wood-train-brio-ikea-aldi.3mf`, via `measure.py orient` |
| Mega Bloks Maxi stud | pitch 31.75, Ø26.92 outside, Ø22.92 inside, 19.05 tall | community baseplate mesh, MakerWorld 2224183 |

Both connector centres landing on 11.0 from the face is the cross-check that
the profiles are right. Clones vary by a few tenths: model the peg at 0 slack
with a `peg_slack` parameter, and platforms that hold a track at 40.8.

## How the pieces go together (this drives every design decision)

- **Pegs drop in from above.** The head (Ø12) is wider than the socket neck
  (7.3), so pieces never slide together sideways. The socket is a through slot
  over the full 12 mm; the peg carries the full 12 mm height. Anything that
  must connect to the layout must allow that vertical drop, and a hinged deck
  that lands in a socket is doing the same thing the official lifting bridge
  does.
- **A moving track end needs air and a funnel.** A deck hinged at mid-height
  moves its tip forward 0.12 mm in the first 5 degrees: leave 0.3 mm between
  the tip and the socket face, give the socket 0.6 mm extra clearance (the peg
  arrives rotating, not straight down), and cut a 2 mm 45 degree funnel around
  the socket mouth (`wt_female_funnel`) so the loose pillar centres itself.
- **Curves need a flat platform.** A curve leaving a platform sweeps sideways,
  so side guides are only allowed where the neighbour is known to be a
  straight (the deck side of a bridge pillar). The far side stays flat.
- **A pillar is a piece of track.** Do not make a plain block for a track to
  rest on: make the pillar a track piece (female towards the moving part, male
  towards the next piece, 17 mm shelves at track-floor level on both sides
  where the neighbours rest, grooves through). Connections set back 17 mm keep
  the peg flush with the pillar and print it supported on its own shelf. The
  Mega Bloks pillar and the drawbridge pillars are both built this way.

## Elevation and clearance

- One standard ramp lifts the track **65 mm**; that is the height of every
  pillar in an elevated section, and it is what one ramp on each side
  connects to.
- A train on a track under a bridge needs **60 mm of free height** (12 of
  track plus about 45 of engine plus margin; IKEA engines are lower, BRIO
  engines with a chimney are the tallest). With the deck at 65, that leaves a
  5 mm slab. So pillars are portals: two piers and a slab, opening at least
  48 mm wide for a track to cross underneath, 45 degree corbels at the top
  corners. A hollow box with a hip roof does *not* work: the roof takes the
  height exactly where the train is.
- Portal printing: a pillar that also carries track on top prints standing,
  so its ceiling is a 36 mm bridge between corbels (fine on a Bambu). A pillar
  that bolts to a housing prints upside down with the slab on the bed and
  needs no bridge at all.

## Wooden-train mechanisms that worked

- Lifting deck as a crank-rocker: worm (self-locking, so the deck stays where
  it is left) -> 16-tooth wheel with an eccentric pin -> link -> lug on the
  deck. One direction of cranking raises then lowers; no end stops to force.
  Open the housing with the deck's swept envelope, not its closed outline
  (the v1 deck hit the housing from 60 degrees on).
- A 3-year-old pulling the open deck puts ~55 N into the link; the wheel
  needs a Ø27 journal in a split bearing, not a Ø6 stub.

## Mega Bloks pillar (for track on top of First Builders blocks)

Socket 20 deep (deeper than the 19.05 stud so the piece seats on the block
face), 0.30 diametral slack for centring, and grip from three rounded ribs
that only engage the first 8 mm from the mouth. Grip force is proportional to
interference x length: shortening the ribs was the control that worked
(rib_h 0.19 / rib_len 8 = easy to remove but firm). Add a 2 mm vent or the
trapped air pushes the piece off; in the track version route the vent out the
side so there is no hole where the train runs. Rotate rib positions 1.5
degrees off the cylinder's facet seam or the export gets degenerate edges.
