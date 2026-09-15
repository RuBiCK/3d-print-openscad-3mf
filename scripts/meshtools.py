"""Shared mesh helpers: load 3MF/STL, section them, measure them.

Everything works on a plain (V, T) pair: V is an (n,3) float array of vertices,
T is an (m,3) int array of triangle indices. No third-party deps beyond numpy.
"""
import re, struct, zipfile
import xml.etree.ElementTree as ET
import numpy as np

CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'


# --------------------------------------------------------------------- loading
def load_stl(path):
    d = open(path, 'rb').read()
    if d[:5] == b'solid' and b'facet' in d[:2000]:                    # ASCII
        v = re.findall(rb'vertex\s+(\S+)\s+(\S+)\s+(\S+)', d)
        P = np.array(v, dtype=float).reshape(-1, 3, 3)
    else:                                                             # binary
        n = struct.unpack('<I', d[80:84])[0]
        a = np.frombuffer(d[84:84 + 50 * n], dtype=np.uint8).reshape(n, 50)
        P = a[:, :48].copy().view('<f4').reshape(n, 12)[:, 3:].reshape(n, 3, 3)
        P = P.astype(np.float64)
    return weld(P)


def weld(P, decimals=6):
    """(m,3,3) triangle soup -> (V, T), duplicate vertices merged."""
    V, inv = np.unique(np.round(P.reshape(-1, 3), decimals), axis=0, return_inverse=True)
    T = inv.reshape(-1, 3)
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    return V, T


def _mesh_from_xml(obj):
    mesh = obj.find(CORE + 'mesh')
    if mesh is None:
        return None
    V = np.array([[float(v.get(k)) for k in 'xyz'] for v in mesh.find(CORE + 'vertices')])
    T = np.array([[int(t.get(k)) for k in ('v1', 'v2', 'v3')] for t in mesh.find(CORE + 'triangles')])
    return V, T


def load_3mf(path):
    """-> {label: (V, T)} for every mesh in the package, in package order."""
    out = {}
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if n.endswith('.model')):
            root = ET.fromstring(z.read(name))
            res = root.find(CORE + 'resources')
            if res is None:
                continue
            for obj in res.findall(CORE + 'object'):
                m = _mesh_from_xml(obj)
                if m is not None:
                    out[f'{name}#{obj.get("id")}'] = m
    return out


def load_any(path):
    """-> {label: (V, T)}; STL files come back as a single entry."""
    if path.lower().endswith('.3mf'):
        return load_3mf(path)
    return {path.split('/')[-1]: load_stl(path)}


# --------------------------------------------------------------------- writing
def write_stl(path, V, T):
    P = V[T]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    L = np.linalg.norm(n, axis=1, keepdims=True)
    L[L == 0] = 1
    with open(path, 'wb') as f:
        f.write(b'\0' * 80)
        f.write(np.array([len(T)], '<u4').tobytes())
        buf = np.zeros((len(T), 12), '<f4')
        buf[:, 0:3] = n / L
        buf[:, 3:6], buf[:, 6:9], buf[:, 9:12] = P[:, 0], P[:, 1], P[:, 2]
        rec = np.zeros((len(T), 50), np.uint8)
        rec[:, :48] = buf.view(np.uint8).reshape(len(T), 48)
        f.write(rec.tobytes())


# ------------------------------------------------------------------- integrity
def is_watertight(T):
    """Every directed edge used exactly once, and its reverse present."""
    from collections import Counter
    c = Counter()
    for t in T:
        for k in range(3):
            c[(t[k], t[(k + 1) % 3])] += 1
    return all(v == 1 for v in c.values()) and all(c[(b, a)] == 1 for a, b in c)


def volume(V, T):
    """Signed volume in mm^3. Positive means normals point outwards."""
    P = V[T]
    return float(np.einsum('ij,ij->i', P[:, 0], np.cross(P[:, 1], P[:, 2])).sum() / 6)


# ------------------------------------------------------------------ sectioning
def section(V, T, axis, value):
    """Cut plane axis=value. Returns a list of 2D segments in the other two axes."""
    oth = [i for i in range(3) if i != axis]
    P = V[T]
    m = (P[:, :, axis].min(1) <= value) & (P[:, :, axis].max(1) >= value)
    segs = []
    for tri in P[m]:
        pts = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            if (a[axis] - value) * (b[axis] - value) <= 0 and a[axis] != b[axis]:
                t = (value - a[axis]) / (b[axis] - a[axis])
                pts.append((a + t * (b - a))[oth])
        if len(pts) >= 2:
            segs.append((np.asarray(pts[0]), np.asarray(pts[1])))
    return segs


def _dist_to_seg(a, b):
    d = b - a
    L = float(d @ d)
    if L < 1e-12:
        return float(np.hypot(*a))
    t = max(0.0, min(1.0, float(-a @ d) / L))
    return float(np.hypot(*(a + t * d)))


def apothem(segs, rmax_filter=None):
    """Smallest distance from the axis to the outline.

    Use this, never the minimum vertex radius: slicing a hexagonal prism only
    produces its corner points, so vertex radii give the circumradius and you
    would read a hexagon 15.5 % too wide. Across-flats = 2 * apothem.
    """
    d = [_dist_to_seg(a, b) for a, b in segs]
    if rmax_filter is not None:
        d = [x for x in d if x <= rmax_filter]
    return min(d) if d else None


def radius_max(segs):
    if not segs:
        return None
    return max(max(float(np.hypot(*a)), float(np.hypot(*b))) for a, b in segs)


def levels(V, axis, decimals=4, min_count=1):
    """Distinct coordinates along `axis` where vertices cluster.

    The fastest way to find exact feature boundaries in someone else's mesh:
    steps, chamfers and shoulders all land on a shared plane.
    """
    vals, counts = np.unique(np.round(V[:, axis], decimals), return_counts=True)
    return [(float(v), int(c)) for v, c in zip(vals, counts) if c >= min_count]


def scan(V, T, axis, value, along, samples):
    """Solid/void transitions along a scan line inside the plane axis=value.

    This is the tool that tells you whether a feature is a hole or a boss.
    Returns the coordinates where the line crosses the surface.
    """
    free = [i for i in range(3) if i not in (axis, along)][0]
    P = V[T]
    A2, B2, C2 = P[:, 0][:, [along, axis]], P[:, 1][:, [along, axis]], P[:, 2][:, [along, axis]]
    cr = lambda u, v: u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]
    den = cr(B2 - A2, C2 - A2)

    def inside(u):
        p = np.array([u, value])
        w0, w1, w2 = cr(B2 - A2, p - A2), cr(C2 - B2, p - B2), cr(A2 - C2, p - C2)
        m = (((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))) & (np.abs(den) > 1e-12)
        if not m.any():
            return False
        a, b, c = cr(C2[m] - B2[m], p - B2[m]), cr(A2[m] - C2[m], p - C2[m]), cr(B2[m] - A2[m], p - A2[m])
        s = a + b + c
        f = (a * P[m, 0, free] + b * P[m, 1, free] + c * P[m, 2, free]) / s
        return int((f > 0).sum()) % 2 == 1

    hits = np.array([inside(u) for u in samples])
    return [round(float((samples[i] + samples[i - 1]) / 2), 3)
            for i in range(1, len(samples)) if hits[i] != hits[i - 1]]


def face_normals(V, T):
    """Unit normals and areas of every triangle."""
    P = V[T]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    a = np.linalg.norm(n, axis=1) / 2
    return n / np.maximum(2 * a, 1e-12)[:, None], a


def dominant_directions(V, T, axis=2, bins=720, top=8, min_area=0.5):
    """Area-weighted histogram of face normals in the plane perpendicular to `axis`.

    A mesh that was saved tilted (a ramp, a lid at an angle) still has flat end
    faces, mounting faces or rails; their normals pile up in a few directions
    and give the true "level". Returns [(angle_deg, area_mm2), ...], angles in
    [0, 180) because a face and its opposite count as the same direction.
    """
    n, a = face_normals(V, T)
    oth = [i for i in range(3) if i != axis]
    m = (np.abs(n[:, axis]) < 0.05) & (a > min_area)
    ang = np.degrees(np.arctan2(n[m, oth[1]], n[m, oth[0]])) % 180
    h, e = np.histogram(ang, bins=bins, range=(0, 180), weights=a[m])
    idx = np.argsort(h)[::-1]
    out, taken = [], []
    for i in idx:
        c = (e[i] + e[i + 1]) / 2
        if h[i] <= 0 or any(abs(((c - t) + 90) % 180 - 90) < 2 for t in taken):
            continue
        taken.append(c)
        out.append((float(c), float(h[i])))
        if len(out) >= top:
            break
    return out


def rotate_about(V, axis, deg):
    """Rotate vertices by `deg` degrees about a coordinate axis (right-hand rule)."""
    oth = [i for i in range(3) if i != axis]
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    W = V.copy()
    u, v = V[:, oth[0]], V[:, oth[1]]
    W[:, oth[0]] = c * u - s * v
    W[:, oth[1]] = s * u + c * v
    return W
