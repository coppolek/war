#!/usr/bin/env python3
"""
osm2rg.py — converte una città reale (OpenStreetMap) nella mappa di Riviera Gunship.

Solo libreria standard di Python 3.8+ (Pillow opzionale per l'anteprima).

Esempi:
  # scarica da Overpass e converte (3,6 km x 3,6 km attorno al centro indicato)
  python3 osm2rg.py --name rimini --title Rimini --center 44.0627,12.5683 --out ../public/maps/rimini.js --preview rimini.png

  # usa un file già scaricato (Overpass JSON con "out geom", es. da overpass-turbo.eu > Esporta > dati grezzi)
  python3 osm2rg.py --name milano --center 45.4642,9.1900 --input milano_overpass.json --out ../public/maps/milano.js

  # per salvare solo il download (utile se il VPS scarica e tu converti altrove)
  python3 osm2rg.py --center 41.9028,12.4964 --download-only roma_overpass.json

Opzioni utili: --tile-m 30 (metri per tile; la mappa è 120x120 tile), --base LAT,LON (dove sta l'eliporto),
--bbox S,W,N,E (alternativa a --center).
"""
import argparse, base64, json, math, random, sys, time, urllib.request, urllib.parse

N = 120          # deve coincidere con N del gioco
T = 48           # unità di gioco per tile
MIRRORS = ['https://overpass-api.de/api/interpreter',
           'https://overpass.kumi.systems/api/interpreter',
           'https://overpass.private.coffee/api/interpreter']

# tipi di tile del gioco
SAND, PLAZA, LOT, COBBLE, ROAD_X, WATER, CONCRETE, GRASS, ROAD_Y, ROAD_X_ = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
CROSS = 9

def query(s, w, n, e):
    bb = f'({s:.6f},{w:.6f},{n:.6f},{e:.6f})'
    return f'''[out:json][timeout:240];
(
 way["building"]{bb};
 way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]{bb};
 way["waterway"~"^(river|canal)$"]{bb};
 way["natural"~"^(water|coastline|beach|wood|scrub)$"]{bb};
 way["landuse"~"^(residential|commercial|retail|industrial|forest|grass|meadow|farmland|orchard|vineyard|cemetery|recreation_ground|village_green)$"]{bb};
 way["leisure"~"^(park|garden|pitch|playground|golf_course)$"]{bb};
 way["aeroway"~"^(aerodrome|runway|apron|helipad)$"]{bb};
 way["railway"="rail"]{bb};
 way["place"="square"]{bb};
);
out geom;'''

def download(q):
    last = None
    for url in MIRRORS:
        for attempt in range(2):
            try:
                print('Scarico da', url, '...', file=sys.stderr)
                req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(),
                                             headers={'User-Agent': 'riviera-gunship-osm2rg/1.0'})
                with urllib.request.urlopen(req, timeout=300) as r:
                    return json.loads(r.read().decode('utf-8'))
            except Exception as ex:
                last = ex; print('  errore:', ex, file=sys.stderr); time.sleep(3)
    sys.exit('Download fallito: %s\nProva con --input su un file scaricato da overpass-turbo.eu' % last)

class Proj:
    def __init__(self, s, w, n, e, tile_m):
        self.lat0 = n; self.lon0 = w; self.cos = math.cos(math.radians((s + n) / 2)); self.tm = tile_m
    def tile(self, lat, lon):      # coordinate in tile (float): i verso est, j verso sud
        return ((lon - self.lon0) * 111320 * self.cos / self.tm, (self.lat0 - lat) * 110540 / self.tm)

def pip(x, y, poly):
    ins = False; n = len(poly); j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi: ins = not ins
        j = i
    return ins

def bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)

def area(poly):
    a = 0
    for k in range(len(poly)):
        x1, y1 = poly[k]; x2, y2 = poly[(k + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2

def fill_poly(grid, poly, val, cond=None):
    x0, y0, x1, y1 = bbox(poly)
    for j in range(max(0, int(y0)), min(N - 1, int(y1)) + 1):
        for i in range(max(0, int(x0)), min(N - 1, int(x1)) + 1):
            if pip(i + .5, j + .5, poly) and (cond is None or cond(grid[j][i])): grid[j][i] = val

def walk(poly, step=.3):
    """punti campionati lungo una polilinea (tile float)"""
    for a in range(len(poly) - 1):
        x1, y1 = poly[a]; x2, y2 = poly[a + 1]
        L = max(abs(x2 - x1), abs(y2 - y1)); k = max(1, int(L / step))
        for q in range(k + 1):
            yield x1 + (x2 - x1) * q / k, y1 + (y2 - y1) * q / k

def stamp(cells, line, r=0):
    for x, y in walk(line):
        i, j = int(math.floor(x)), int(math.floor(y))
        for dj in range(-r, r + 1):
            for di in range(-r, r + 1):
                if 0 <= i + di < N and 0 <= j + dj < N: cells.add((i + di, j + dj))

def main():
    ap = argparse.ArgumentParser(description='OpenStreetMap -> mappa Riviera Gunship')
    ap.add_argument('--name', default='citta', help='identificatore (usato in ?m=nome)')
    ap.add_argument('--title', default=None)
    ap.add_argument('--center', help='LAT,LON del centro')
    ap.add_argument('--bbox', help='S,W,N,E')
    ap.add_argument('--tile-m', type=float, default=30.0, help='metri per tile (default 30 -> mappa 3,6 km)')
    ap.add_argument('--input', help='file Overpass JSON già scaricato')
    ap.add_argument('--download-only', metavar='FILE')
    ap.add_argument('--base', help='LAT,LON eliporto/base (default: aeroporto o zona libera)')
    ap.add_argument('--out', default=None)
    ap.add_argument('--preview', default=None, help='PNG di anteprima (richiede Pillow)')
    ap.add_argument('--max-houses', type=int, default=6500)
    a = ap.parse_args()
    if a.bbox:
        s, w, n, e = map(float, a.bbox.split(','))
    elif a.center:
        lat, lon = map(float, a.center.split(','))
        half = N * a.tile_m / 2
        dlat = half / 110540; dlon = half / (111320 * math.cos(math.radians(lat)))
        s, n, w, e = lat - dlat, lat + dlat, lon - dlon, lon + dlon
    else:
        ap.error('serve --center o --bbox')
    if a.input:
        data = json.load(open(a.input, encoding='utf-8'))
    else:
        data = download(query(s, w, n, e))
        if a.download_only:
            json.dump(data, open(a.download_only, 'w')); print('salvato', a.download_only); return
    P = Proj(s, w, n, e, a.tile_m)
    # per --bbox adatta la scala perché il box entri nei 120 tile
    if a.bbox:
        wm = (e - w) * 111320 * P.cos; hm = (n - s) * 110540
        P.tm = max(wm, hm) / N
    els = [x for x in data.get('elements', []) if x.get('type') == 'way' and x.get('geometry')]
    print('elementi:', len(els), file=sys.stderr)
    def geo(el): return [P.tile(g['lat'], g['lon']) for g in el['geometry']]

    grid = [[GRASS] * N for _ in range(N)]
    occ = [[0] * N for _ in range(N)]
    water_poly, built, green, beach, plaza = [], [], [], [], []
    rivers, roads, rails, coast, runways, aero = [], [], [], [], [], []
    houses_src = []
    for el in els:
        tg = el.get('tags', {}); pts = geo(el)
        if len(pts) < 2: continue
        closed = el['geometry'][0] == el['geometry'][-1] and len(pts) >= 4
        if 'building' in tg and closed: houses_src.append((pts, tg)); continue
        hw = tg.get('highway')
        if hw:
            if hw == 'pedestrian' and closed and tg.get('area') == 'yes': plaza.append(pts)
            else: roads.append((pts, hw, tg))
            continue
        if tg.get('waterway') in ('river', 'canal'): rivers.append((pts, tg.get('waterway'))); continue
        nat, lu, le, ae = tg.get('natural'), tg.get('landuse'), tg.get('leisure'), tg.get('aeroway')
        if nat == 'coastline': coast.append(pts); continue
        if nat == 'water' and closed: water_poly.append(pts); continue
        if nat == 'beach' and closed: beach.append(pts); continue
        if nat in ('wood', 'scrub') and closed: green.append(pts); continue
        if lu in ('residential', 'commercial', 'retail', 'industrial') and closed: built.append(pts); continue
        if lu and closed: green.append(pts); continue
        if le and closed: green.append(pts); continue
        if tg.get('place') == 'square' and closed: plaza.append(pts); continue
        if ae == 'runway': runways.append(pts); continue
        if ae in ('aerodrome', 'apron') and closed: aero.append(pts); continue
        if tg.get('railway') == 'rail': rails.append(pts); continue

    # --- terreno ---
    for p in built: fill_poly(grid, p, LOT)
    for p in green: fill_poly(grid, p, GRASS)
    for p in beach: fill_poly(grid, p, SAND)
    for p in plaza: fill_poly(grid, p, PLAZA)
    # edifici: occupazione
    for pts, tg in houses_src:
        fill_poly(occ, pts, 1)
    for j in range(N):
        for i in range(N):
            if occ[j][i]:
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        jj, ii = j + dj, i + di
                        if 0 <= jj < N and 0 <= ii < N and grid[jj][ii] in (GRASS,): grid[jj][ii] = LOT
    # centro storico: zone molto dense -> acciottolato
    for j in range(N):
        for i in range(N):
            if grid[j][i] == LOT:
                c = sum(occ[jj][ii] for jj in range(max(0, j - 2), min(N, j + 3)) for ii in range(max(0, i - 2), min(N, i + 3)))
                if c >= 20: grid[j][i] = COBBLE
    # acqua: poligoni, mare (flood fill dalle coste), fiumi
    for p in water_poly: fill_poly(grid, p, WATER)
    if coast:
        barrier = set()
        for c in coast: stamp(barrier, c)
        seeds = set()
        for c in coast:
            for k in range(len(c) - 1):
                x1, y1 = c[k]; x2, y2 = c[k + 1]
                L = math.hypot(x2 - x1, y2 - y1)
                if L < 1e-6: continue
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                nx, ny = -(y2 - y1) / L, (x2 - x1) / L        # a destra del verso (asse y verso sud) = mare
                for dist in (1.6, 2.5):
                    i, j = int(math.floor(mx + nx * dist)), int(math.floor(my + ny * dist))
                    if 0 <= i < N and 0 <= j < N and (i, j) not in barrier: seeds.add((i, j))
        stack = list(seeds); sea = set(seeds)
        while stack:
            i, j = stack.pop()
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ii, jj = i + di, j + dj
                if 0 <= ii < N and 0 <= jj < N and (ii, jj) not in barrier and (ii, jj) not in sea:
                    sea.add((ii, jj)); stack.append((ii, jj))
        for (i, j) in sea: grid[j][i] = WATER
        # spiaggia: fascia di sabbia 2 tile lungo il mare (se non costruita)
        for j in range(N):
            for i in range(N):
                if grid[j][i] != WATER and not occ[j][i]:
                    near = any(0 <= j + dj < N and 0 <= i + di < N and grid[j + dj][i + di] == WATER and (i + di, j + dj) in sea
                               for dj in range(-2, 3) for di in range(-2, 3))
                    if near and grid[j][i] in (GRASS, LOT): grid[j][i] = SAND
    rv = set()
    for pts, kind in rivers: stamp(rv, pts, 1 if kind == 'river' else 0)
    for (i, j) in rv:
        if not occ[j][i]: grid[j][i] = WATER
    # ferrovia
    rl = set()
    for p in rails: stamp(rl, p)
    for (i, j) in rl:
        if grid[j][i] != WATER: grid[j][i] = CONCRETE
    # aeroporto
    base = None
    if a.base:
        la, lo = map(float, a.base.split(',')); bx, by = P.tile(la, lo); base = [int(bx), int(by)]
    for p in aero:
        fill_poly(grid, p, GRASS, cond=lambda v: v != WATER)
        if base is None:
            x0, y0, x1, y1 = bbox(p)
            if x1 - x0 > 12 and y1 - y0 > 12: base = [int((x0 + x1) / 2), int((y0 + y1) / 2)]
    rw = set()
    for p in runways: stamp(rw, p, 1)
    for (i, j) in rw:
        if grid[j][i] != WATER: grid[j][i] = CONCRETE
    # strade (sopra l'acqua solo i ponti)
    rd = set(); bridge_cells = set()
    for pts, hw, tg in roads:
        if tg.get('tunnel') in ('yes', 'building_passage', 'culvert'): continue
        cells = set(); stamp(cells, pts, 1 if hw in ('motorway', 'trunk', 'primary') else 0)
        isb = tg.get('bridge') not in (None, 'no')
        for (i, j) in cells:
            if grid[j][i] == WATER and not isb: continue
            if grid[j][i] == WATER: bridge_cells.add((i, j))
            rd.add((i, j))
    def isr(i, j): return (i, j) in rd
    bridges = []
    for (i, j) in rd:
        h = isr(i - 1, j) or isr(i + 1, j); v = isr(i, j - 1) or isr(i, j + 1)
        t = CROSS if (h and v) else (ROAD_Y if v and not h else ROAD_X)
        if (i, j) in bridge_cells: bridges.append([i, j, 'c' if t == ROAD_Y else 'r'])
        grid[j][i] = t
    # bordo = acqua come nel gioco (muro invisibile)
    for k in range(N):
        for (i, j) in ((k, 0), (k, N - 1), (0, k), (N - 1, k)): grid[j][i] = WATER

    # --- base: area libera lontano da edifici e acqua ---
    if base is not None and not (8 <= base[0] < N - 8 and 7 <= base[1] < N - 7): base = None
    if base is None or grid[base[1]][base[0]] == WATER:
        best, bp = -1, [N // 2, N // 2]
        for j in range(10, N - 10):
            for i in range(10, N - 10):
                if grid[j][i] in (WATER,) or occ[j][i]: continue
                sc = 0
                for r in (3, 5, 7):
                    ok = all(not occ[jj][ii] and grid[jj][ii] != WATER for jj in range(j - r, j + r + 1) for ii in range(i - r, i + r + 1))
                    if ok: sc = r
                    else: break
                if sc > best: best, bp = sc, [i, j]
        base = bp
    base[0] = max(8, min(N - 9, base[0])); base[1] = max(7, min(N - 8, base[1]))

    # --- edifici ---
    def levels(tg):
        v = tg.get('building:levels')
        try: return float(str(v).split(';')[0])
        except Exception: pass
        b = tg.get('building', 'yes')
        return {'house': 2, 'detached': 2, 'residential': 3, 'apartments': 5, 'hotel': 6, 'commercial': 4, 'retail': 2,
                'industrial': 1.5, 'warehouse': 1.5, 'church': 3, 'cathedral': 5, 'garage': 1, 'garages': 1, 'shed': 1}.get(b, 2.5)
    def hq(v): return int(max(12, min(72, round(v / 6) * 6)))
    sizes = [18, 24, 30, 36, 42]
    def qs(v): return min(sizes, key=lambda s: abs(s - v))
    rng = random.Random(7)
    houses = []
    for pts, tg in houses_src:
        x0, y0, x1, y1 = bbox(pts)
        if x1 < 0 or y1 < 0 or x0 > N or y0 > N: continue
        ar = area(pts); bb = max(1e-6, (x1 - x0) * (y1 - y0)); k = math.sqrt(max(.5, min(1, ar / bb)))
        hh = hq(levels(tg) * 3.2 * (T / P.tm))
        col = rng.randrange(9)
        bw, bd = (x1 - x0) * T * k, (y1 - y0) * T * k
        nx, ny = max(1, math.ceil(bw / 42)), max(1, math.ceil(bd / 42))
        if nx * ny > 12: nx, ny = min(nx, 4), min(ny, 3)
        for qi in range(nx):
            for qj in range(ny):
                cx = x0 + (qi + .5) * (x1 - x0) / nx; cy = y0 + (qj + .5) * (y1 - y0) / ny
                if (nx > 1 or ny > 1) and not pip(cx, cy, pts): continue
                houses.append([int(cx * T), int(cy * T), qs(bw / nx), qs(bd / ny), hh, col, ar])
    # niente case sull'area della base
    houses = [h for h in houses if not (base[0] - 6 <= h[0] // T <= base[0] + 7 and base[1] - 5 <= h[1] // T <= base[1] + 6)]
    houses = [h for h in houses if 0 <= h[0] < N * T and 0 <= h[1] < N * T]
    houses = [h for h in houses if grid[h[1] // T][h[0] // T] != WATER or (h[0] // T, h[1] // T) in bridge_cells]
    if len(houses) > a.max_houses:
        houses.sort(key=lambda h: -h[6]); houses = houses[:a.max_houses]
    houses = [h[:6] for h in houses]

    flat = bytearray(grid[j][i] for j in range(N) for i in range(N))
    out = {'n': N, 'name': a.title or a.name, 'tm': round(P.tm, 2), 't': base64.b64encode(bytes(flat)).decode(),
           'h': houses, 'b': bridges, 'base': base}
    stats = {k: sum(1 for v in flat if v == k) for k in range(10)}
    print('tile:', stats, '| edifici:', len(houses), '| ponti:', len(bridges), '| base:', base, '| metri/tile:', round(P.tm, 1), file=sys.stderr)
    if a.out:
        js = 'window.RG_MAPS=window.RG_MAPS||{};window.RG_MAPS[%s]=%s;\n' % (json.dumps(a.name), json.dumps(out, separators=(',', ':')))
        open(a.out, 'w', encoding='utf-8').write(js); print('scritto', a.out, len(js) // 1024, 'KB', file=sys.stderr)
    if a.preview:
        try:
            from PIL import Image
            col = {SAND: (226, 204, 160), PLAZA: (182, 176, 164), LOT: (150, 146, 136), COBBLE: (170, 150, 120), ROAD_X: (60, 62, 66),
                   WATER: (44, 112, 140), CONCRETE: (120, 120, 118), GRASS: (96, 140, 70), ROAD_Y: (60, 62, 66), CROSS: (60, 62, 66)}
            S = 6; im = Image.new('RGB', (N * S, N * S))
            px = im.load()
            for j in range(N):
                for i in range(N):
                    for dj in range(S):
                        for di in range(S): px[i * S + di, j * S + dj] = col[grid[j][i]]
            for h in houses:
                x, y = int(h[0] / T * S), int(h[1] / T * S)
                for dj in range(-2, 3):
                    for di in range(-2, 3):
                        if 0 <= x + di < N * S and 0 <= y + dj < N * S: px[x + di, y + dj] = (220, 190, 150)
            bx, by = base[0] * S, base[1] * S
            for dj in range(-8, 9):
                for di in range(-8, 9):
                    if 0 <= bx + di < N * S and 0 <= by + dj < N * S: px[bx + di, by + dj] = (255, 80, 60)
            im.save(a.preview); print('anteprima', a.preview, file=sys.stderr)
        except ImportError:
            print('Pillow non installato: anteprima saltata (pip install pillow)', file=sys.stderr)

if __name__ == '__main__': main()
