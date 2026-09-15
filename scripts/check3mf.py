#!/usr/bin/env python3
"""Validate a Bambu Studio project .3mf before shipping it.

    check3mf.py FILE.3mf [FILE.3mf ...]

Checks the things that actually break in practice: malformed XML, dangling
relationships, sub-models missing the mandatory <build/>, ids that do not line
up between 3dmodel.model and model_settings.config, meshes that are not
watertight or have inverted normals, parts floating above or sunk into the
bed, parts off the bed or overlapping each other.
"""
import json, sys, zipfile
import xml.etree.ElementTree as ET
from collections import Counter
import numpy as np

C = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
P = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
R = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def check(path, bed=256.0):
    print(f'\n=== {path.split("/")[-1]} ===')
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    fails = []
    bad = fails.append

    for n in names:
        if n.endswith(('.model', '.rels', '.xml')) or n == 'Metadata/model_settings.config':
            try:
                ET.fromstring(z.read(n))
            except Exception as e:
                bad(f'malformed XML in {n}: {e}')
    if 'Metadata/project_settings.config' in names:
        try:
            json.loads(z.read('Metadata/project_settings.config'))
        except Exception as e:
            bad(f'project_settings.config is not valid JSON: {e}')

    for n in [x for x in names if x.endswith('.rels')]:
        for rel in ET.fromstring(z.read(n)).findall(R + 'Relationship'):
            t = rel.get('Target').lstrip('/')
            if t not in names and not t.endswith('.gcode'):
                bad(f'{n} points at {t}, which is not in the package')

    root = ET.fromstring(z.read('3D/3dmodel.model'))
    if root.find(C + 'build') is None:
        bad('3dmodel.model has no <build>')
    objs = {o.get('id'): o for o in root.find(C + 'resources').findall(C + 'object')}
    if not objs:
        bad('no objects in <resources>')

    meshes, tris = {}, 0
    for oid, o in objs.items():
        comp = o.find(C + 'components')
        if comp is None:
            bad(f'root object {oid} has no <components>')
            continue
        for c in comp.findall(C + 'component'):
            p = c.get(P + 'path', '').lstrip('/')
            if p not in names:
                bad(f'component points at {p}, missing')
                continue
            sub = ET.fromstring(z.read(p))
            if sub.find(C + 'build') is None:
                bad(f'{p} has NO <build/> - mandatory in 3MF; Bambu will load geometry only')
            so = {s.get('id'): s for s in sub.find(C + 'resources').findall(C + 'object')}
            if c.get('objectid') not in so:
                bad(f'{p} does not contain object id={c.get("objectid")}')
                continue
            mesh = so[c.get('objectid')].find(C + 'mesh')
            V = np.array([[float(v.get(k)) for k in 'xyz'] for v in mesh.find(C + 'vertices')])
            T = np.array([[int(t.get(k)) for k in ('v1', 'v2', 'v3')] for t in mesh.find(C + 'triangles')])
            tris += len(T)
            if T.max() >= len(V):
                bad(f'{p}: triangle index out of range')
                continue
            cnt = Counter()
            for t in T:
                for k in range(3):
                    cnt[(t[k], t[(k + 1) % 3])] += 1
            if not (all(v == 1 for v in cnt.values()) and all(cnt[(b, a)] == 1 for a, b in cnt)):
                bad(f'{p}: mesh is not watertight')
            Q = V[T]
            if np.einsum('ij,ij->i', Q[:, 0], np.cross(Q[:, 1], Q[:, 2])).sum() <= 0:
                bad(f'{p}: normals point inwards')
            meshes[oid] = V

    # Plates: Bambu Studio keeps world coordinates in the 3MF, with plate k on a
    # grid of ceil(sqrt(n)) columns stepped by 1.2 x bed (rows towards -Y).
    ms = ET.fromstring(z.read('Metadata/model_settings.config'))
    plates = ms.findall('plate')
    plate_of = {m.find('metadata[@key="object_id"]').get('value'): k
                for k, p in enumerate(plates) for m in p.findall('model_instance')}
    cols = max(1, int(np.ceil(np.sqrt(len(plates)))))
    origin = lambda k: np.array([(k % cols) * bed * 1.2, -(k // cols) * bed * 1.2, 0.0])

    boxes = []
    for it in root.find(C + 'build').findall(C + 'item'):
        oid = it.get('objectid')
        if oid not in objs:
            bad(f'build item references missing object {oid}')
            continue
        tr = [float(x) for x in it.get('transform').split()]
        W = meshes[oid] @ np.array(tr[:9]).reshape(3, 3) + np.array(tr[9:]) - origin(plate_of.get(oid, 0))
        if abs(W[:, 2].min()) > 1e-3:
            bad(f'object {oid} does not sit on the bed (z min = {W[:,2].min():.3f})')
        if W[:, 0].min() < 0 or W[:, 1].min() < 0 or W[:, 0].max() > bed or W[:, 1].max() > bed:
            bad(f'object {oid} is off the {bed:.0f}x{bed:.0f} bed')
        boxes.append((oid, W[:, 0].min(), W[:, 0].max(), W[:, 1].min(), W[:, 1].max(), W[:, 2].max()))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if plate_of.get(a[0], 0) != plate_of.get(b[0], 0):
                continue
            if a[1] < b[2] and b[1] < a[2] and a[3] < b[4] and b[3] < a[4]:
                bad(f'objects {a[0]} and {b[0]} overlap on the plate')

    if {o.get('id') for o in ms.findall('object')} != set(objs):
        bad('model_settings.config objects do not match 3dmodel.model')
    if not plates:
        bad('model_settings.config has no <plate>')
    elif set(plate_of) != set(objs):
        bad('the plates do not instance every object exactly once')
    for k, p in enumerate(plates):
        pid = p.find('metadata[@key="plater_id"]')
        if pid is None or pid.get('value') != str(k + 1):
            bad(f'plate {k + 1} has plater_id {None if pid is None else pid.get("value")}')

    md = {e.get('name'): (e.text or '') for e in root.findall(C + 'metadata')}
    print(f'  objects={len(objs)}  triangles={tris}  '
          f'project_settings={"Metadata/project_settings.config" in names}  '
          f'pictures={len([n for n in names if n.startswith("Auxiliaries/Model Pictures/")])}')
    for k, p in enumerate(plates):
        pn = p.find('metadata[@key="plater_name"]')
        print(f'  plate {k + 1}: {pn.get("value") if pn is not None else ""}')
        for oid, x0, x1, y0, y1, h in boxes:
            if plate_of.get(oid, 0) == k:
                print(f'    obj {oid}: X {x0:6.1f}-{x1:6.1f}  Y {y0:6.1f}-{y1:6.1f}  height {h:5.2f} mm')
    print(f'  Title: {md.get("Title", "")}')
    for f in fails:
        print('  FAIL:', f)
    print('  ->', 'OK' if not fails else f'{len(fails)} PROBLEM(S)')
    return not fails


if __name__ == '__main__':
    sys.exit(0 if all(check(f) for f in sys.argv[1:]) else 1)
