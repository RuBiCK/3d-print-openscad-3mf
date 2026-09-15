#!/usr/bin/env python3
"""Reverse-engineer dimensions from an existing 3MF or STL.

    measure.py info    FILE
    measure.py levels  FILE [--axis z] [--min-count 4]
    measure.py profile FILE [--axis z] [--from A] [--to B] [--step S] [--inner R]
    measure.py section FILE --at V [--axis z] [--max-r R]
    measure.py scan    FILE --at V [--axis z] [--along x] [--range A B] [--step S]
    measure.py orient  FILE [--axis z] [--level DEG --write out.stl]

`scan` is the one that tells you whether a feature is a hole or a boss: it
prints where a line crossing the part enters and leaves solid material.

`orient` is for meshes saved tilted (a ramp, a part lying at an angle): it lists
the directions the flat faces point in, area-weighted, so you can pick the true
horizontal (end faces, rails, mounting faces cluster there). `--level DEG` then
rotates about --axis so that direction becomes +X, and `--write` saves the
levelled copy for the other commands to measure.
"""
import argparse, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshtools as M

AX = {'x': 0, 'y': 1, 'z': 2}


def pick(path, which=None):
    d = M.load_any(path)
    if which:
        d = {k: v for k, v in d.items() if which in k}
    if not d:
        sys.exit('no mesh matched')
    return d


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=['info', 'levels', 'profile', 'section', 'scan', 'orient'])
    p.add_argument('file')
    p.add_argument('--object', help='substring of the mesh label, when the file holds several')
    p.add_argument('--axis', default='z', choices=list(AX))
    p.add_argument('--along', default='x', choices=list(AX))
    p.add_argument('--at', type=float)
    p.add_argument('--from', dest='lo', type=float)
    p.add_argument('--to', dest='hi', type=float)
    p.add_argument('--step', type=float, default=0.5)
    p.add_argument('--range', nargs=2, type=float)
    p.add_argument('--inner', type=float, help='only measure the outline inside this radius (bores)')
    p.add_argument('--max-r', type=float)
    p.add_argument('--min-count', type=int, default=4)
    p.add_argument('--level', type=float, help='orient: angle (deg) of the face direction to make horizontal (+X)')
    p.add_argument('--write', help='orient: save the rotated mesh as STL')
    a = p.parse_args()
    ax = AX[a.axis]

    for label, (V, T) in pick(a.file, a.object).items():
        print(f'\n### {label}')
        if a.cmd == 'info':
            print(f'  vertices {len(V)}  triangles {len(T)}')
            print(f'  bbox min {np.round(V.min(0), 3)}  max {np.round(V.max(0), 3)}')
            print(f'  size     {np.round(V.max(0) - V.min(0), 3)}')
            print(f'  watertight {M.is_watertight(T)}   volume {M.volume(V, T) / 1000:.3f} cm3'
                  f'   normals {"outward" if M.volume(V, T) > 0 else "INWARD"}')

        elif a.cmd == 'levels':
            print(f'  vertex planes along {a.axis} (feature boundaries land here)')
            for v, c in M.levels(V, ax, min_count=a.min_count):
                print(f'    {v:9.4f}   n={c}')

        elif a.cmd == 'profile':
            lo = a.lo if a.lo is not None else V[:, ax].min() + 1e-3
            hi = a.hi if a.hi is not None else V[:, ax].max() - 1e-3
            print(f'  {a.axis:>8}  across-flats   outer-dia')
            v = lo
            while v <= hi + 1e-9:
                s = M.section(V, T, ax, v)
                if s:
                    ap = M.apothem(s, a.inner)
                    rx = M.radius_max(s)
                    print(f'  {v:8.3f}   {2 * ap:9.3f}   {2 * rx:9.3f}' if ap else f'  {v:8.3f}   (empty)')
                else:
                    print(f'  {v:8.3f}   (empty)')
                v += a.step

        elif a.cmd == 'section':
            s = M.section(V, T, ax, a.at)
            pts = np.array([q for seg in s for q in seg])
            if a.max_r is not None:
                pts = pts[np.hypot(pts[:, 0], pts[:, 1]) <= a.max_r]
            r = np.hypot(pts[:, 0], pts[:, 1])
            ang = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
            seen = set()
            for i in np.argsort(ang):
                k = (round(float(ang[i]), 2), round(float(r[i]), 3))
                if k in seen:
                    continue
                seen.add(k)
                print(f'  {ang[i]:8.2f} deg   r={r[i]:7.3f}   ({pts[i,0]:8.3f},{pts[i,1]:8.3f})')

        elif a.cmd == 'scan':
            oth = [i for i in range(3) if i != ax]
            lo, hi = a.range if a.range else (V[:, oth[0]].min() - 1, V[:, oth[0]].max() + 1)
            xs = np.arange(lo, hi, a.step if a.step < 0.2 else 0.02)
            e = M.scan(V, T, ax, a.at, AX[a.along], xs)
            print(f'  solid/void transitions at {a.axis}={a.at} along {a.along}:')
            print(f'    {e}')
            if len(e) >= 4:
                print('    more than one pair of edges -> the section is not simply connected:')
                print('    ring/annulus, or a central boss surrounded by a groove.')

        elif a.cmd == 'orient':
            oth = 'xyz'.replace(a.axis, '')
            print(f'  directions of flat faces in the {oth} plane (angle from +{oth[0]}, area-weighted):')
            for ang, area in M.dominant_directions(V, T, ax):
                print(f'    {ang:7.2f} deg   {area:9.1f} mm2')
            print('  a pair 90 deg apart is a box; the big one is usually a mounting face or an end face.')
            if a.level is not None:
                W = M.rotate_about(V, ax, -a.level)
                print(f'  rotated {-a.level:.2f} deg about {a.axis}: bbox {np.round(W.min(0), 3)} .. {np.round(W.max(0), 3)}')
                if a.write:
                    M.write_stl(a.write, W, T)
                    print(f'  wrote {a.write}')


if __name__ == '__main__':
    main()
