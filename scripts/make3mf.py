#!/usr/bin/env python3
"""Pack one or more STLs into a Bambu Studio project .3mf.

    make3mf.py -o set.3mf --title "My Bits" --description desc.html \
               --donor any-bambu-project.3mf \
               --picture render.png --cover render.png \
               a.stl:"Part A" b.stl:"Part B"

Each STL must already be in print orientation, Z up. Parts are laid out in a
row on the bed and dropped onto z=0. Pass --donor pointing at ANY project you
exported from your own Bambu Studio to inherit its print profile; without it
the file opens as a plain model instead of as a project.
"""
import argparse, html as _html, os, shutil, subprocess, sys, tempfile, uuid, zipfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meshtools as M

NS = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
uid = lambda tag: str(uuid.uuid5(NS, tag))

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>'''

SUB = '''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources>
  <object id="{oid}" p:UUID="{uuid}" type="model">
   <mesh>
    <vertices>
{verts}    </vertices>
    <triangles>
{tris}    </triangles>
   </mesh>
  </object>
 </resources>
 <build/>
</model>
'''   # the <build/> is mandatory in the 3MF core spec. Omit it and Bambu
      # Studio reports an error and falls back to loading geometry only.


def esc2(t):
    """MakerWorld stores the description HTML-escaped inside XML, so escape twice."""
    e = lambda s: s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return e(e(t)).replace('\n', ' ')


def layout(sizes, bed, gap):
    """Row-major arrangement of (w, d) footprints centred on the bed."""
    rows, row, w = [], [], 0.0
    for s in sizes:
        if row and w + s[0] + gap > bed * 0.8:
            rows.append(row); row, w = [], 0.0
        row.append(s); w += s[0] + gap
    if row:
        rows.append(row)
    depth = sum(max(s[1] for s in r) for r in rows) + gap * (len(rows) - 1)
    pos, y = [], bed / 2 + depth / 2
    for r in rows:
        h = max(s[1] for s in r)
        y -= h / 2
        total = sum(s[0] for s in r) + gap * (len(r) - 1)
        x = bed / 2 - total / 2
        for s in r:
            pos.append((x + s[0] / 2, y))
            x += s[0] + gap
        y -= h / 2 + gap
    return pos


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('parts', nargs='+', help='file.stl, file.stl:"Display name" or file.stl:"Name"@"Plate name" '
                                            '(parts sharing a plate name go on the same plate, in order of first use)')
    p.add_argument('-o', '--out', required=True)
    p.add_argument('--title', default='')
    p.add_argument('--description', help='file containing the description as plain HTML')
    p.add_argument('--designer', default='')
    p.add_argument('--license', default='')
    p.add_argument('--donor', help='an existing Bambu .3mf to inherit Metadata/project_settings.config from')
    p.add_argument('--picture', action='append', default=[], help='png for the model gallery (repeatable)')
    p.add_argument('--cover', help='png used for the thumbnails')
    p.add_argument('--bed', type=float, default=256.0)
    p.add_argument('--gap', type=float, default=10.0, help='clear space between parts, for the brim')
    p.add_argument('--support', action='append', default=[], metavar='NAME',
                   help='enable tree supports on the object with this display name (repeatable)')
    a = p.parse_args()

    meshes, plates = [], []          # plates: names in order of first appearance
    for spec in a.parts:
        path, _, rest = spec.partition(':')
        name, _, plate = rest.partition('@')
        V, T = M.load_stl(path)
        if not M.is_watertight(T):
            sys.exit(f'{path}: mesh is not watertight, fix the model first')
        if M.volume(V, T) <= 0:
            sys.exit(f'{path}: normals point inwards')
        if plate not in plates:
            plates.append(plate)
        meshes.append((V, T, name or os.path.splitext(os.path.basename(path))[0], plates.index(plate)))

    # One layout per plate. Bambu Studio lays plates out on a grid of
    # ceil(sqrt(n)) columns, each plate stepped by 1.2 x bed (LOGICAL_PART_PLATE_GAP),
    # rows going towards -Y; world coordinates in the 3MF include that offset.
    cols = int(np.ceil(np.sqrt(len(plates))))
    step = a.bed * 1.2
    pos = [None] * len(meshes)
    for k in range(len(plates)):
        idx = [i for i, m in enumerate(meshes) if m[3] == k]
        local = layout([(np.ptp(meshes[i][0][:, 0]), np.ptp(meshes[i][0][:, 1])) for i in idx], a.bed, a.gap)
        ox, oy = (k % cols) * step, -(k // cols) * step
        for i, (x, y) in zip(idx, local):
            pos[i] = (x + ox, y + oy)

    w = tempfile.mkdtemp()
    for d in ['3D/Objects', '3D/_rels', '_rels', 'Metadata',
              'Auxiliaries/.thumbnails', 'Auxiliaries/Model Pictures']:
        os.makedirs(f'{w}/{d}', exist_ok=True)

    rels, res, items, mobj, minst, masm, cuts = [], [], [], [], [], [], []
    for i, (V, T, name, k) in enumerate(meshes):
        pid, oid, fn = 2 * i + 1, 2 * i + 2, f'object_{i + 1}.model'
        open(f'{w}/3D/Objects/{fn}', 'w').write(SUB.format(
            oid=pid, uuid=uid(f'part{i}'),
            verts=''.join(f'     <vertex x="{v[0]:.6f}" y="{v[1]:.6f}" z="{v[2]:.6f}"/>\n' for v in V),
            tris=''.join(f'     <triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>\n' for t in T)))
        cx, cy = (V[:, 0].min() + V[:, 0].max()) / 2, (V[:, 1].min() + V[:, 1].max()) / 2
        tx, ty, tz = pos[i][0] - cx, pos[i][1] - cy, -V[:, 2].min()
        rels.append(f' <Relationship Target="/3D/Objects/{fn}" Id="rel-{i + 1}" '
                    f'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
        res.append(f'  <object id="{oid}" p:UUID="{uid(f"obj{i}")}" type="model">\n   <components>\n'
                   f'    <component p:path="/3D/Objects/{fn}" objectid="{pid}" '
                   f'p:UUID="{uid(f"cmp{i}")}" transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n'
                   f'   </components>\n  </object>')
        items.append(f'  <item objectid="{oid}" p:UUID="{uid(f"item{i}")}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}" printable="1" />')
        sup = ('    <metadata key="enable_support" value="1"/>\n'
               '    <metadata key="support_type" value="tree(auto)"/>\n') if name in a.support else ''
        mobj.append(f'  <object id="{oid}">\n    <metadata key="name" value="{_html.escape(name, quote=True)}"/>\n'
                    + sup + f'    <metadata key="extruder" value="1"/>\n'
                    f'    <metadata face_count="{len(T)}"/>\n'
                    f'    <part id="{pid}" subtype="normal_part">\n'
                    f'      <metadata key="name" value="{_html.escape(name, quote=True)}"/>\n'
                    f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                    f'      <metadata key="source_object_id" value="0"/>\n'
                    f'      <metadata key="source_volume_id" value="0"/>\n'
                    f'      <metadata key="source_offset_x" value="0"/>\n'
                    f'      <metadata key="source_offset_y" value="0"/>\n'
                    f'      <metadata key="source_offset_z" value="0"/>\n'
                    f'      <mesh_stat face_count="{len(T)}" edges_fixed="0" degenerate_facets="0" '
                    f'facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n    </part>\n  </object>')
        minst.append((k, f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n'
                         f'      <metadata key="instance_id" value="0"/>\n'
                         f'      <metadata key="identify_id" value="{100 + i}"/>\n    </model_instance>'))
        masm.append(f'   <assemble_item object_id="{oid}" instance_id="0" '
                    f'transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}" offset="0 0 0" />')
        cuts.append(f' <object id="{i + 1}">\n  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n </object>')

    desc = esc2(open(a.description).read()) if a.description else ''
    thumbs = bool(a.cover)
    open(f'{w}/3D/3dmodel.model', 'w').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
        'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
        ' <metadata name="Application">BambuStudio-01.10.01.50</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        f' <metadata name="Title">{_html.escape(a.title)}</metadata>\n'
        f' <metadata name="Description">{desc}</metadata>\n'
        f' <metadata name="Designer">{_html.escape(a.designer)}</metadata>\n'
        f' <metadata name="License">{_html.escape(a.license)}</metadata>\n'
        ' <metadata name="Origin"></metadata>\n'
        + (' <metadata name="Thumbnail_Middle">/Auxiliaries/.thumbnails/thumbnail_middle.png</metadata>\n'
           ' <metadata name="Thumbnail_Small">/Auxiliaries/.thumbnails/thumbnail_small.png</metadata>\n' if thumbs else '')
        + ' <resources>\n' + '\n'.join(res) + '\n </resources>\n'
        f' <build p:UUID="{uid("build")}">\n' + '\n'.join(items) + '\n </build>\n</model>\n')

    open(f'{w}/3D/_rels/3dmodel.model.rels', 'w').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        + '\n'.join(rels) + '\n</Relationships>\n')
    open(f'{w}/_rels/.rels', 'w').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        + (' <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_3mf.png" Id="rel-2" '
           'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>\n'
           ' <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_middle.png" Id="rel-3" '
           'Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-middle"/>\n'
           ' <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_small.png" Id="rel-4" '
           'Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-small"/>\n' if thumbs else '')
        + '</Relationships>\n')
    open(f'{w}/[Content_Types].xml', 'w').write(CONTENT_TYPES)
    plate_xml = ''.join(
        f'\n  <plate>\n    <metadata key="plater_id" value="{k + 1}"/>\n'
        f'    <metadata key="plater_name" value="{_html.escape(pname, quote=True)}"/>\n'
        '    <metadata key="locked" value="false"/>\n'
        + '\n'.join(s for kk, s in minst if kk == k) + '\n  </plate>'
        for k, pname in enumerate(plates))
    open(f'{w}/Metadata/model_settings.config', 'w').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + '\n'.join(mobj)
        + plate_xml + '\n  <assemble>\n' + '\n'.join(masm) + '\n  </assemble>\n</config>\n')
    open(f'{w}/Metadata/cut_information.xml', 'w').write(
        '<?xml version="1.0" encoding="utf-8"?>\n<objects>\n' + '\n'.join(cuts) + '\n</objects>\n')

    if a.donor:
        with zipfile.ZipFile(a.donor) as z:
            if 'Metadata/project_settings.config' in z.namelist():
                open(f'{w}/Metadata/project_settings.config', 'wb').write(
                    z.read('Metadata/project_settings.config'))
            else:
                print('warning: donor has no project_settings.config')
    else:
        print('note: no --donor, so the file will open as a model, not as a project')

    for i, pic in enumerate(a.picture):
        shutil.copy(pic, f'{w}/Auxiliaries/Model Pictures/{i + 1:02d}_{os.path.basename(pic)}')
    if a.cover:
        for size, name in [(512, 'thumbnail_3mf.png'), (1000, 'thumbnail_middle.png'), (256, 'thumbnail_small.png')]:
            dst = f'{w}/Auxiliaries/.thumbnails/{name}'
            shutil.copy(a.cover, dst)
            subprocess.run(['sips', '-Z', str(size), dst], capture_output=True)

    if os.path.exists(a.out):
        os.remove(a.out)
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, fs in os.walk(w):
            for f in sorted(fs):
                pth = os.path.join(root, f)
                z.write(pth, os.path.relpath(pth, w))
    shutil.rmtree(w)
    missing = [n for n in a.support if n not in [m[2] for m in meshes]]
    if missing:
        print(f'warning: --support names not found: {missing}')
    print(f'wrote {a.out}: {len(meshes)} object(s) on {len(plates)} plate(s)')
    for (V, _, name, k), (x, y) in zip(meshes, pos):
        print(f'  plate {k + 1} {plates[k][:14]:14s} {name:28s} at X={x:6.1f} Y={y:6.1f}  height {np.ptp(V[:,2]):5.2f} mm'
              + ('  [supports]' if name in a.support else ''))


if __name__ == '__main__':
    main()
