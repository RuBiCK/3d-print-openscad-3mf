#!/usr/bin/env python3
"""Interference sweep for a mechanism modelled in OpenSCAD.

    sweep.py chk.scad --parts casa tablero rueda biela --var crank 0 16 \
             [--pairs "casa tablero" "rueda sinfin"] [--jobs 8] [--min 0.05]

Runs `chk.scad` for every pair of parts and every value of the sweep variable,
exports the boolean intersection, and reports the pairs whose intersection has
volume: the value, the mm3 and where it is (bounding box). Zero everywhere
means nothing touches anywhere in the cycle.

`chk.scad` is yours: copy sweep_template.scad next to the model and fill in
posed(name) so it places each part exactly as the assembly view does (same
transforms as your montaje() module). The script drives it with
-D A="<part>" -D B="<part>" -D <var>=<value>.

Why a script and not eyeballing renders: a 1 mm collision at 70 deg of a
cycle is invisible in a render and jams a self-locking mechanism.
"""
import argparse, itertools, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshtools as M


def run(scad, a, b, var, val, outdir):
    f = os.path.join(outdir, f'{a}_{b}_{val:g}.stl')
    if os.path.exists(f):
        os.remove(f)   # OpenSCAD writes nothing for an empty result: never read a stale file
    r = subprocess.run(['openscad', '--backend=Manifold', '--export-format', 'binstl',
                        '-D', f'A="{a}"', '-D', f'B="{b}"', '-D', f'{var}={val:g}',
                        '-o', f, scad], capture_output=True, text=True)
    if not os.path.exists(f):
        if 'empty' in r.stderr or 'empty' in r.stdout:
            return (a, b, val, 0.0, None)
        return (a, b, val, None, r.stderr.strip().splitlines()[-3:])
    V, T = M.load_stl(f)
    if len(T) == 0:
        return (a, b, val, 0.0, None)
    return (a, b, val, abs(M.volume(V, T)), (V.min(0), V.max(0)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('scad')
    p.add_argument('--parts', nargs='+', required=True, help='names posed() understands')
    p.add_argument('--pairs', nargs='*', help='"a b" pairs to check; default: every pair of --parts')
    p.add_argument('--var', nargs=3, metavar=('NAME', 'FROM', 'TO'), required=True,
                   help='sweep variable and its integer range, inclusive')
    p.add_argument('--step', type=float, default=1.0)
    p.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    p.add_argument('--min', type=float, default=0.01, help='mm3 below which a result counts as zero')
    p.add_argument('--keep', help='directory to keep the intersection STLs in (default: temp)')
    a = p.parse_args()

    name, lo, hi = a.var[0], float(a.var[1]), float(a.var[2])
    vals = list(np.arange(lo, hi + a.step / 2, a.step))
    pairs = [tuple(s.split()) for s in a.pairs] if a.pairs else list(itertools.combinations(a.parts, 2))
    outdir = a.keep or tempfile.mkdtemp(prefix='sweep_')
    os.makedirs(outdir, exist_ok=True)
    jobs = [(x, y, v) for v in vals for x, y in pairs]
    print(f'{len(pairs)} pairs x {len(vals)} values of {name} = {len(jobs)} intersections, {a.jobs} at a time')

    hits, errors, done = [], [], 0
    with ThreadPoolExecutor(a.jobs) as ex:
        for res in ex.map(lambda j: run(a.scad, j[0], j[1], name, j[2], outdir), jobs):
            x, y, v, vol, extra = res
            done += 1
            if vol is None:
                errors.append((x, y, v, extra))
            elif vol > a.min:
                hits.append((x, y, v, vol, extra))
    for x, y, v, extra in errors:
        print(f'  ERROR {x}/{y} at {name}={v:g}: {extra}')
    if not hits:
        print(f'  no interference above {a.min} mm3 in any pair at any {name}')
    else:
        print(f'  {len(hits)} interference(s):')
        for x, y, v, vol, (lo_, hi_) in sorted(hits, key=lambda h: (h[0], h[1], h[2])):
            print(f'  {x:12s} {y:12s} {name}={v:<5g} {vol:8.3f} mm3   x {lo_[0]:7.2f}..{hi_[0]:7.2f}'
                  f'  y {lo_[1]:7.2f}..{hi_[1]:7.2f}  z {lo_[2]:7.2f}..{hi_[2]:7.2f}')
    if not a.keep:
        for f in os.listdir(outdir):
            os.remove(os.path.join(outdir, f))
        os.rmdir(outdir)
    sys.exit(1 if hits or errors else 0)


if __name__ == '__main__':
    main()
