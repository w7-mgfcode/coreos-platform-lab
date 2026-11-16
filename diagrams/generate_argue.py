"""Hand-laid Excalidraw diagrams that argue each variant's core trade-off (dark palette).

Outputs (next to this file):
  03-compose-argue-dark.excalidraw / .svg
  04-swarm-argue-dark.excalidraw / .svg

Colours are baked in as a dark palette, so open the .excalidraw files with the
Excalidraw *light* theme (its dark theme would invert them).
"""
import itertools
import json
import math
import os
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
# Local engine used for the SVG export. Override with EXCALIDRAW_ENGINE_SRC;
# the default points under the current user's home directory.
ENGINE = Path(os.environ.get('EXCALIDRAW_ENGINE_SRC')
              or Path.home() / '.local/share/excalidraw-architect-mcp/src')

BG = '#121417'
INK = '#e6e8eb'
MUTED = '#8b949e'
RULE = '#3a4049'
CODE_BG = '#0b0f14'
COL = {  # name: (stroke, fill)
    'blue': ('#60a5fa', '#16263d'),
    'sky': ('#93c5fd', '#16263d'),
    'green': ('#34d399', '#0f2a22'),
    'amber': ('#fbbf24', '#33270c'),
    'red': ('#f87171', '#361616'),
    'violet': ('#a78bfa', '#231a3d'),
    'orange': ('#fb923c', '#35200f'),
    'gray': ('#8b949e', '#1c2026'),
}
FW = 0.6  # monospace glyph width / font size


class Diagram:
    def __init__(self):
        self.els = []
        self._n = itertools.count(1)
        self._seed = itertools.count(1000)

    def _id(self, p):
        return f'{p}{next(self._n)}'

    def _base(self, kind, x, y, w, h, stroke, bg='transparent', sw=2, style='solid', **kw):
        e = dict(type=kind, id=self._id(kind[:3]), x=x, y=y, width=w, height=h,
                 strokeColor=stroke, backgroundColor=bg, fillStyle='solid', strokeWidth=sw,
                 strokeStyle=style, roughness=0, opacity=100, angle=0, seed=next(self._seed),
                 version=1, versionNonce=next(self._seed), isDeleted=False, groupIds=[],
                 boundElements=None, link=None, locked=False, frameId=None, roundness=None)
        e.update(kw)
        self.els.append(e)
        return e

    # --- text -------------------------------------------------------------
    def text(self, x, y, s, size=16, color=INK, align='left', w=None, container=None, angle=0):
        lines = s.split('\n')
        width = w if w is not None else max(len(l) for l in lines) * size * FW
        height = len(lines) * size * 1.25
        return self._base('text', x, y, width, height, color, sw=1, angle=angle,
                          text=s, originalText=s, fontSize=size, fontFamily=3,
                          textAlign=align, verticalAlign='middle' if container else 'top',
                          containerId=container, lineHeight=1.25, autoResize=True)

    def _bind_text(self, shape, s, size, color, pad=8):
        lines = s.split('\n')
        th = len(lines) * size * 1.25
        t = self.text(shape['x'] + pad, shape['y'] + (shape['height'] - th) / 2, s, size, color,
                      align='center', w=shape['width'] - 2 * pad, container=shape['id'])
        shape['boundElements'] = (shape['boundElements'] or []) + [{'id': t['id'], 'type': 'text'}]
        return t

    # --- shapes -----------------------------------------------------------
    def box(self, x, y, w, h, label=None, color='gray', size=15, style='solid', sw=2,
            fill=True, text_color=None, rounded=True):
        stroke, bg = COL[color] if color in COL else (color, 'transparent')
        r = self._base('rectangle', x, y, w, h, stroke, bg if fill else 'transparent', sw, style,
                       roundness={'type': 3} if rounded else None)
        if label:
            self._bind_text(r, label, size, text_color or INK)
        return r

    def ellipse(self, x, y, w, h, label=None, color='gray', size=14):
        stroke, bg = COL[color]
        e = self._base('ellipse', x, y, w, h, stroke, bg, 2)
        if label:
            self._bind_text(e, label, size, INK, pad=w * 0.15)
        return e

    def diamond(self, x, y, w, h, label=None, color='amber', size=14):
        stroke, bg = COL[color]
        d = self._base('diamond', x, y, w, h, stroke, bg, 2)
        if label:
            self._bind_text(d, label, size, INK, pad=w * 0.22)
        return d

    def dot(self, cx, cy, r=6, color='gray'):
        stroke = COL[color][0] if color in COL else color
        return self._base('ellipse', cx - r, cy - r, 2 * r, 2 * r, stroke, stroke, 1)

    # --- linear -----------------------------------------------------------
    def _linear(self, kind, pts, stroke, sw, style, **kw):
        x0, y0 = pts[0]
        rel = [[px - x0, py - y0] for px, py in pts]
        xs = [p[0] for p in rel]
        ys = [p[1] for p in rel]
        return self._base(kind, x0, y0, max(xs) - min(xs), max(ys) - min(ys), stroke, sw=sw,
                          style=style, points=rel, lastCommittedPoint=None, **kw)

    def line(self, pts, color='gray', sw=2, style='solid'):
        stroke = COL[color][0] if color in COL else color
        return self._linear('line', pts, stroke, sw, style)

    def arrow(self, pts, color='gray', sw=2, style='solid', label=None, size=13,
              start=None, end=None, head='arrow', tail=None):
        stroke = COL[color][0] if color in COL else color
        a = self._linear('arrow', pts, stroke, sw, style,
                         startBinding={'elementId': start['id'], 'focus': 0, 'gap': 4} if start else None,
                         endBinding={'elementId': end['id'], 'focus': 0, 'gap': 4} if end else None,
                         startArrowhead=tail, endArrowhead=head, elbowed=False)
        for shape in (start, end):
            if shape is not None:
                shape['boundElements'] = (shape['boundElements'] or []) + [{'id': a['id'], 'type': 'arrow'}]
        if label:
            mx, my = _midpoint(pts)
            lines = label.split('\n')
            w = max(len(l) for l in lines) * size * FW
            h = len(lines) * size * 1.25
            t = self.text(mx - w / 2, my - h / 2, label, size, stroke, align='center', w=w,
                          container=a['id'])
            a['boundElements'] = (a['boundElements'] or []) + [{'id': t['id'], 'type': 'text'}]
        return a

    # --- composite --------------------------------------------------------
    def code(self, x, y, w, title, body, color='#7ee787', size=13):
        lines = body.split('\n')
        h = 40 + len(lines) * size * 1.25 + 16
        self.box(x, y, w, h, color='gray', fill=False, sw=1, rounded=False)
        self.els[-1]['backgroundColor'] = CODE_BG
        self.els[-1]['strokeColor'] = RULE
        self.text(x + 16, y + 12, title, 12, MUTED)
        body = body.replace(' ', '\u00a0')  # SVG collapses runs of spaces
        self.text(x + 16, y + 36, body, size, color)
        return y + h

    def save(self, slug):
        doc = {'type': 'excalidraw', 'version': 2, 'source': 'https://excalidraw.com',
               'elements': self.els,
               'appState': {'viewBackgroundColor': BG, 'gridSize': 20, 'theme': 'light',
                            'exportBackground': True, 'exportWithDarkMode': False},
               'files': {}}
        path = OUT / f'{slug}.excalidraw'
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
        sys.path.insert(0, str(ENGINE))
        from excalidraw_mcp.export.svg_exporter import export_to_svg
        export_to_svg(path, OUT / f'{slug}.svg')
        print('wrote', path.name, len(self.els), 'elements')


def _midpoint(pts):
    segs = list(zip(pts, pts[1:]))
    lens = [math.dist(a, b) for a, b in segs]
    half = sum(lens) / 2
    for (a, b), L in zip(segs, lens):
        if half <= L:
            t = half / L if L else 0
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        half -= L
    return pts[-1]


def header(d, kicker, title, sub):
    d.text(40, 30, kicker, 15, MUTED)
    d.text(40, 58, title, 36, INK)
    d.text(40, 110, sub, 18, MUTED)


# =============================================================================
# A / Compose: one VM, five isolated networks, mandatory host firewall plus two
# supplementary layers, one failure domain
# =============================================================================
def compose():
    d = Diagram()
    header(d, 'CORELAB  /  A VÁLTOZAT  /  DOCKER COMPOSE  /  VÁLASZTOTT VÁLTOZAT',
           'Egy VM, öt elszigetelt hálózat',
           'A kötelező határ a hosttűzfal; a Proxmox-tűzfal és a hálózati tagság kiegészítő réteg '
           '- de minden egyetlen hibatartományban fut.')

    # Nested boundaries: failure domain > Proxmox firewall > host firewall (= the VM)
    d.box(290, 180, 1490, 835, color='red', fill=False, style='dashed', sw=2, rounded=False)
    d.text(310, 987, 'PROXMOX HOST  ·  egyetlen fizikai hibatartomány: VM- vagy hostkiesés = teljes leállás',
           14, COL['red'][0])
    d.box(360, 230, 1380, 750, color='amber', fill=False, sw=4, rounded=False)
    d.text(380, 206, 'PROXMOX VM-TŰZFAL  ·  VM-határ  ·  kiegészítő réteg', 14, COL['amber'][0])
    d.box(385, 262, 1330, 695, color='orange', fill=False, sw=2, style='dashed', rounded=False)
    d.text(400, 238, 'HOST-TŰZFAL  ·  kötelező réteg  ·  INPUT + DOCKER-USER (továbbított konténerforgalom)', 14, COL['orange'][0])
    d.text(410, 276, 'FCOS VM app-01  ·  SELinux  ·  Docker CE + Compose', 15, INK)

    # Containers (columns) and networks (lanes) – membership drawn as bus taps
    cols = [('caddy', 'Caddy\nCA + TLS', 'blue'), ('wp', 'WordPress\nuploads', 'blue'),
            ('db', 'MariaDB\nDB volume', 'green'), ('pf', 'Postfix\nqueue', 'orange'),
            ('gf', 'Grafana\nbeállítások', 'violet'), ('lk', 'Loki\nlogadat', 'violet'),
            ('al', 'Alloy\npozíciók', 'violet')]
    X0, STEP, BW, BY, BH = 640, 150, 130, 330, 66
    shape, cx = {}, {}
    for i, (k, label, c) in enumerate(cols):
        x = X0 + i * STEP
        shape[k] = d.box(x, BY, BW, BH, label, c, size=14)
        cx[k] = x + BW / 2

    lanes = [  # name, y, colour, purpose, members
        ('web', 460, 'blue', 'proxy → app', ['caddy', 'wp']),
        ('database  [internal]', 520, 'green', 'app → SQL · nincs kijárat', ['wp', 'db']),
        ('mail', 580, 'orange', 'app → SMTP', ['wp', 'pf']),
        ('grafana-proxy', 640, 'sky', 'proxy → logfelület', ['caddy', 'gf']),
        ('logs  [internal]', 700, 'violet', 'gyűjtés + lekérdezés', ['al', 'lk', 'gf']),
    ]
    deepest = {}
    for _, y, _, _, members in lanes:
        for m in members:
            deepest[m] = max(deepest.get(m, 0), y)
    for k, y in deepest.items():
        d.line([(cx[k], BY + BH), (cx[k], y)], color=RULE, sw=1)
    for name, y, c, purpose, members in lanes:
        xs = [cx[m] for m in members]
        d.line([(min(xs), y), (max(xs), y)], color=c, sw=3)
        for m in members:
            d.dot(cx[m], y, 7, c)
        d.text(410, y - 21, name, 15, COL[c][0])
        d.text(410, y - 1, purpose, 12, MUTED)

    # Log convergence above the boxes, SMTP egress above that
    d.arrow([(cx['caddy'], BY), (cx['caddy'], 308), (cx['al'], 308), (cx['al'], BY)],
            color='violet', sw=2, style='dashed', label='access log + mail log → Alloy',
            start=shape['caddy'], end=shape['al'])
    d.line([(cx['pf'], BY), (cx['pf'], 308)], color='violet', sw=2, style='dashed')
    d.dot(cx['pf'], 308, 4, 'violet')

    relay = d.ellipse(1800, 250, 270, 80, 'Külső SMTP relay\n→ tesztpostafiók', 'orange')
    d.arrow([(cx['pf'] + 40, BY), (cx['pf'] + 40, 290), (1800, 290)], color='orange', sw=2,
            label='587/TCP · STARTTLS + auth', start=shape['pf'], end=relay)

    # Left: who may cross the walls
    client = d.ellipse(40, 300, 240, 90, 'Belső kliens\nroot CA trust', 'blue')
    d.arrow([(280, 350), (640, 350)], color='blue', sw=3, label='443/TCP · belső LAN',
            start=client, end=shape['caddy'])
    bad = d.ellipse(40, 520, 240, 90, 'Nem jogosult\nkliens', 'red')
    d.arrow([(280, 565), (356, 565)], color='red', sw=2, style='dashed', start=bad, head='bar')
    d.text(40, 622, '3306 · 25 · 3100 · Docker API\n→ DROP a Proxmox-tűzfalon\n   és a hosttűzfalon', 13, COL['red'][0])
    admin = d.ellipse(40, 720, 240, 80, 'Admin hálózat', 'gray')
    d.arrow([(280, 760), (405, 760)], color='gray', sw=2, label='22', start=admin)

    # Right: external dependencies
    cmk = d.ellipse(1800, 470, 290, 90, 'Checkmk (független)\nagent · HTTPS · cert', 'green')
    d.arrow([(1800, 515), (1718, 515)], color='green', sw=2, start=cmk)
    bkp = d.ellipse(1800, 700, 290, 90, 'Mentési cél, VM-en kívül\ntitkosított mentés', 'green')
    d.arrow([(1718, 745), (1800, 745)], color='green', sw=2, end=bkp)

    # Evidence inside the VM
    d.code(410, 748, 380, 'Caddyfile  ·  belső CA, automatikus kiadás',
           'app.corelab.test {\n  tls internal\n  reverse_proxy wordpress:80\n}\n'
           'logs.corelab.test {\n  tls internal\n  reverse_proxy grafana:3000\n}')
    d.code(810, 748, 380, 'compose.yaml  ·  hálózati tagság (részlet)',
           'services:\n  mariadb:\n    networks: [database]\n  wordpress:\n'
           '    networks: [web, database, mail]\nnetworks:\n  database: { internal: true }\n'
           '  logs:     { internal: true }')
    d.code(1210, 748, 490, 'DOCKER-USER  ·  példa, iptables backend, fiktív IP',
           '-A DOCKER-USER -m conntrack \\\n   --ctstate ESTABLISHED,RELATED -j RETURN\n'
           '-A DOCKER-USER -i ens18 \\\n   ! -s 10.10.20.0/24 -j DROP\n\n'
           '# csak INPUT szűrése nem védi\n# a publikált konténerportot', color='#fdba74')

    # Boot / reproducibility timeline
    d.text(40, 1050, 'INDULÁS ÉS REPRODUKÁLHATÓSÁG', 15, COL['amber'][0])
    steps = ['Butane\n(Gitben)', 'Ignition\n(első boot)', 'systemd unit\n(Docker után)',
             'docker compose\nup -d', 'healthcheck +\nCheckmk OK']
    xs = [340 + i * 330 for i in range(len(steps))]
    d.arrow([(xs[0], 1090), (xs[-1] + 120, 1090)], color='amber', sw=2)
    for x, s in zip(xs, steps):
        d.dot(x, 1090, 8, 'amber')
        d.text(x - 80, 1106, s, 14, INK, align='center', w=160)
    d.text(40, 1180, 'TERV, NEM TELEPÍTÉSI IGAZOLÁS  ·  Forrás: docs/architecture.md  ·  '
           'Docker CE, nem az FCOS beépített Moby (eldöntve: 2026-11-13)', 13, MUTED)
    d.save('03-compose-argue-dark')


# =============================================================================
# B / Swarm: three nodes, but state gravitates to node-1
# =============================================================================
def swarm():
    d = Diagram()
    header(d, 'CORELAB  /  B VÁLTOZAT  /  DOCKER SWARM  /  ELVETETT ALTERNATÍVA',
           'Három node - de az állapot node-1-re gravitál',
           'A webes réteg két node-on skálázódik, a stateful szolgáltatások node-1-hez kötöttek; '
           'a három VM egy fizikai hoston fut.')

    # Quorum is logical: one decision shared by the three managers
    q = d.diamond(950, 150, 220, 110, 'Raft quorum\n2 / 3 manager', 'amber')
    d.box(380, 280, 1260, 630, color='red', fill=False, style='dashed', sw=2, rounded=False)
    d.text(400, 884, 'PROXMOX HOST  ·  3 VM ≠ 3 hibatartomány: a host kiesése mindhárom node-ot viszi',
           14, COL['red'][0])

    n1 = d.box(420, 300, 400, 575, color='red', sw=3, rounded=False)
    n1['backgroundColor'] = '#1a1315'
    n2 = d.box(880, 300, 340, 575, color='gray', sw=2, rounded=False)
    n3 = d.box(1260, 300, 340, 575, color='gray', sw=2, rounded=False)
    d.text(436, 312, 'node-1 · manager + worker', 16, INK)
    d.text(436, 334, 'stateful · node.hostname==node-1', 13, COL['red'][0])
    d.text(896, 312, 'node-2 · manager + worker', 16, INK)
    d.text(896, 334, 'node.labels.web == true', 13, MUTED)
    d.text(1276, 312, 'node-3 · manager + worker', 16, INK)
    d.text(1276, 334, 'node.labels.web == true', 13, MUTED)
    for cxn in (620, 1050, 1430):
        d.line([(1060, 260), (cxn, 300)], color='amber', sw=1, style='dashed')

    # Published 443 on every node -> routing mesh converges on the single Caddy
    tabs = []
    for tx in (750, 1150, 1530):
        tabs.append(d.box(tx, 287, 60, 26, '443', 'blue', size=13, rounded=False))
    caddy = d.box(440, 400, 220, 62, 'Caddy + belső CA\n1 replica · CA-adat', 'blue', size=14)
    d.arrow([(1560, 313), (1560, 368), (540, 368), (540, 400)], color='blue', sw=2,
            style='dashed', label='ingress routing mesh: 443 minden node-on', end=caddy)
    for tx in (780, 1180):
        d.line([(tx, 313), (tx, 368)], color='blue', sw=2, style='dashed')
        d.dot(tx, 368, 4, 'blue')
    client = d.ellipse(40, 255, 240, 90, 'Belső kliens\nDNS → node-1 IP', 'blue')
    d.arrow([(280, 300), (748, 300)], color='blue', sw=3, label='443/TCP', start=client, end=tabs[0])

    # node-1: everything that owns data
    db = d.box(440, 490, 220, 62, 'MariaDB\n1 replica · helyi volume', 'green', size=14)
    pf = d.box(440, 580, 220, 62, 'Postfix\n1 replica · helyi queue', 'orange', size=14)
    lk = d.box(440, 670, 220, 62, 'Loki\n1 replica · logadat', 'violet', size=14)
    gf = d.box(680, 670, 125, 62, 'Grafana\n1 replica', 'violet', size=14)
    d.arrow([(660, 701), (680, 701)], color='violet', sw=2, start=lk, end=gf)
    d.text(490, 748, 'helyi volume: nincs replikáció', 13, COL['red'][0])

    # Stateless web tier: Caddy -> service VIP -> two tasks (fan-out), tasks -> node-1 (convergence)
    vip = d.ellipse(1170, 382, 110, 44, 'VIP', 'blue', size=13)
    d.arrow([(660, 431), (1170, 404)], color='blue', sw=2, label='HTTP · overlay web',
            start=caddy, end=vip)
    wp1 = d.box(900, 450, 300, 70, 'WordPress task 1\nrögzített image@digest', 'blue', size=14)
    wp2 = d.box(1280, 450, 300, 70, 'WordPress task 2\nrögzített image@digest', 'blue', size=14)
    d.arrow([(1195, 424), (1060, 450)], color='blue', sw=2, start=vip, end=wp1)
    d.arrow([(1255, 424), (1420, 450)], color='blue', sw=2, start=vip, end=wp2)
    d.arrow([(900, 505), (660, 521)], color='green', sw=2, label='SQL (mindkét task)', start=wp1, end=db)
    d.arrow([(910, 520), (660, 611)], color='orange', sw=2, label='SMTP (mindkét task)', start=wp1, end=pf)

    # Shared uploads leave the cluster
    nfs = d.box(1040, 950, 400, 66, 'Közös NFS · külső NAS / storage VM\nWordPress uploads', 'green', size=14)
    d.arrow([(1050, 520), (1130, 950)], color='green', sw=2, label='uploads', start=wp1, end=nfs)
    d.arrow([(1430, 520), (1350, 950)], color='green', sw=2, start=wp2, end=nfs)

    # Alloy is global: one per node on a shared spine
    d.line([(420, 805), (1600, 805)], color='violet', sw=3)
    for x in (470, 960, 1300):
        d.dot(x, 805, 8, 'violet')
        d.text(x + 14, 784, 'Alloy', 13, COL['violet'][0])
    d.arrow([(470, 797), (470, 732)], color='violet', sw=2, end=lk)
    d.text(490, 814, 'Alloy · global: node-onként 1', 13, MUTED)
    d.line([(420, 845), (1600, 845)], color='sky', sw=2, style='dashed')
    d.text(440, 851, 'overlay: web · database · mail · logs · grafana-proxy  -  VXLAN 4789/UDP csak node-ok között',
           13, COL['sky'][0])

    # Left: externals
    admin = d.ellipse(40, 430, 240, 80, 'Admin hálózat\nstack deploy', 'gray')
    d.arrow([(280, 470), (420, 470)], color='gray', sw=2, label='22', start=admin, end=n1)
    relay = d.ellipse(40, 560, 240, 80, 'Külső SMTP relay\n→ tesztpostafiók', 'orange')
    d.arrow([(440, 611), (280, 600)], color='orange', sw=2, label='587', start=pf, end=relay)
    cmk = d.ellipse(40, 690, 240, 80, 'Checkmk\nquorum · replika', 'green')
    d.arrow([(280, 730), (420, 730)], color='green', sw=2, label='agent', start=cmk, end=n1)
    bkp = d.ellipse(40, 820, 240, 80, 'Mentési cél\nklaszteren kívül', 'green')
    d.arrow([(420, 860), (280, 860)], color='green', sw=2, label='titkosítva', start=n1, end=bkp)

    # Right: failure consequences, coloured by severity
    d.text(1700, 280, 'HA KIESIK ...', 15, COL['amber'][0])
    fails = [('green', 'egy WordPress task', 'újraütemezés; a másik task kiszolgál'),
             ('amber', 'node-2 vagy node-3', 'quorum OK; 1 web marad, a 2. pending'),
             ('red', 'node-1', 'CA/proxy, DB, SMTP, log ki - app használhatatlan'),
             ('red', 'két manager', 'quorumvesztés: nincs ütemezés/módosítás'),
             ('amber', 'NFS', 'közös uploads hibás vagy blokkolt'),
             ('red', 'Proxmox host', 'mindhárom VM kiesik'),
             ('red', 'belépési IP (node-1)', 'nincs kliensoldali alternatíva')]
    for i, (c, ev, cons) in enumerate(fails):
        y = 316 + i * 62
        d.dot(1710, y + 9, 7, c)
        d.text(1730, y, ev, 15, INK)
        d.text(1730, y + 21, cons, 13, COL[c][0])

    d.text(1700, 770, 'GÖRDÜLŐ FRISSÍTÉS  ·  parallelism 1  ·  stop-first', 15, COL['amber'][0])
    steps = ['T1 stop', 'T1 új', 'T1 healthy', 'T2 stop', 'T2 új']
    d.arrow([(1715, 815), (2300, 815)], color='amber', sw=2)
    for i, s in enumerate(steps):
        x = 1720 + i * 125
        d.dot(x, 815, 7, 'amber')
        d.text(x - 50, 830, s, 13, INK, align='center', w=100)
    d.text(1700, 862, 'közben 1 task szolgál ki;\nDB-séma kompatibilitás feltétel', 13, MUTED)

    # Evidence
    d.code(40, 1060, 580, 'stack.yaml  ·  elhelyezés és frissítés (részlet)',
           'wordpress:\n  image: registry.lab/corelab-wp:1.0.0@sha256:...\n  secrets: [db_password]\n'
           '  deploy:\n    replicas: 2\n    placement:\n      max_replicas_per_node: 1\n'
           '      constraints: [node.labels.web == true]\n'
           '    update_config: { parallelism: 1, order: stop-first }\nmariadb:\n  deploy:\n'
           '    placement:\n      constraints: [node.hostname == node-1]')
    d.code(660, 1060, 560, 'tűzfal  ·  klaszterportok',
           '443/tcp       belső kliens → MINDEN node (mesh)\n22/tcp        admin hálózat → node-ok\n'
           '2377/tcp      node-ok → managerek\n7946/tcp+udp  node ↔ node (gossip)\n'
           '4789/udp      node ↔ node (VXLAN), csak megbízható háló\n'
           'NFS           csak web node-ok → NFS\n587/tcp       Postfix → külső relay', color='#fdba74')
    d.box(1260, 1060, 560, 150, None, 'red', fill=True, sw=2, rounded=False)
    d.text(1280, 1076, 'TELJES HA-HOZ MÉG HIÁNYZIK', 15, COL['red'][0])
    d.text(1280, 1108, '· több fizikai hibatartomány\n· redundáns belépés: VIP / load balancer\n'
           '· DB-replikáció és HA fájltár\n· proxy/CA állapot koordinálása több Caddy között',
           14, INK)
    d.text(40, 1340, 'TERV, NEM TELEPÍTÉSI IGAZOLÁS  ·  Forrás: docs/alternatives/swarm.md  ·  '
           'Elvetett alternatíva (2026-11-13)', 13, MUTED)
    d.save('04-swarm-argue-dark')


if __name__ == '__main__':
    compose()
    swarm()
