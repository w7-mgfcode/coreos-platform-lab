"""Render comparison diagrams with the locally installed Excalidraw Architect engine."""
import json
import os
import sys
from pathlib import Path

# Local engine and dependency cache. Override with the environment variables;
# the defaults point under the current user's home directory.
ENGINE = Path(os.environ.get('EXCALIDRAW_ENGINE_SRC')
              or Path.home() / '.local/share/excalidraw-architect-mcp/src')
CACHE = Path(os.environ.get('EXCALIDRAW_UV_CACHE')
             or Path.home() / '.cache/uv/archive-v0')
sys.path.insert(0, str(ENGINE))
for package in ['grandalf', 'pyparsing']:
    found = list(CACHE.glob('*/' + package))
    if found:
        sys.path.append(str(found[0].parent))

from excalidraw_mcp.core.models import DiagramGraph, Node, Edge, Direction
from excalidraw_mcp.core.palette import get_palette
from excalidraw_mcp.core.drawable import Text, Box, Style, drawable_bounds, translate
from excalidraw_mcp.diagrams.base import graph_to_drawables
from excalidraw_mcp.diagrams.structural import HighLevelSpec, layout_high_level
from excalidraw_mcp.engine.layout import compute_layout
from excalidraw_mcp.engine.draw_renderer import build_drawable_file
from excalidraw_mcp.engine.renderer import save_excalidraw
from excalidraw_mcp.export.svg_exporter import export_to_svg

OUT = Path(__file__).resolve().parent
PAL = get_palette('dark')

def label(x, y, text, size=18, color=None):
    return Text(x=x, y=y, text=text, size=size, color=color or PAL.ink)

def make(swarm=False):
    slug = '02-swarm-dark' if swarm else '01-compose-dark'
    title = 'B / Docker Swarm' if swarm else 'A / Docker Compose'
    subtitle = ('Elvetett alternatíva • klaszter és két webes példány, nagyobb üzemeltetési feladat' if swarm
                else 'Választott változat • egy VM, reprodukálható szolgáltatások')
    rows = ([{'label': 'FCOS VM-ek', 'items': ['node-1\nmanager + worker', 'node-2\nmanager + worker', 'node-3\nmanager + worker']}]
            if swarm else [{'label': 'FCOS VM', 'items': ['app-01\nDocker CE + Compose']}])
    topology = HighLevelSpec(cluster_label=(
        'PROXMOX LAB  /  3 VM ugyanazon a hoston: közös fizikai hibapont' if swarm else
        'PROXMOX LAB  /  1 Fedora CoreOS VM'), rows=rows)
    top = layout_high_level(topology, PAL)
    nodes = [
        ('client', 'Belső kliens\nDNS + CA trust'),
        ('fw', 'Tűzfal\nProxmox + host'),
        ('proxy', 'Caddy + belső CA\n1 példány' + (' / node-1' if swarm else '')),
        ('web', 'WordPress + SMTP\n' + ('2 példány / node-2,3' if swarm else '1 példány')),
        ('db', 'MariaDB\n' + ('1 példány / node-1' if swarm else 'helyi volume')),
        ('mail', 'Postfix relay\n' + ('1 példány / node-1' if swarm else 'belső SMTP-hálózat')),
        ('relay', 'Külső SMTP relay\n→ tesztpostafiók'),
        ('logs', 'Alloy → Loki → Grafana\nweb- és SMTP-logok'),
    ]
    edges = [
        ('client','fw','HTTPS','solid'), ('fw','proxy','443 / belső LAN','solid'),
        ('proxy','web','HTTP / privát','solid'), ('web','db','SQL','solid'),
        ('web','mail','SMTP','solid'), ('mail','relay','587 / STARTTLS','solid'),
        ('proxy','logs','access log','dotted'), ('mail','logs','mail log','dotted'),
    ]
    if swarm:
        nodes.append(('files','Közös fájltár / NFS\nWordPress uploads'))
        edges.append(('web','files','fájlok','solid'))
    graph = DiagramGraph(nodes=[Node(id=i,label=t) for i,t in nodes],
                         edges=[Edge(from_id=a,to_id=b,label=l,style=s) for a,b,l,s in edges],
                         direction=Direction.LEFT_RIGHT)
    drawing = graph_to_drawables(compute_layout(graph), PAL, focal_ids={'proxy','web'})
    gx,gy,gr,gb=drawable_bounds(drawing)
    tx,ty,tr,tb=drawable_bounds(top)
    width=max(gr-gx, tr-tx, 1320)
    margin=44
    elements=[label(margin,28,'CORELAB  /  INFRASTRUKTÚRA-TERV  /  DÖNTÉSI VÁLTOZAT',15,PAL.muted),
              label(margin,64,title,38),label(margin,120,subtitle,21)]
    elements += translate(top, margin-tx, 176-ty)
    elements.append(label(margin+(tr-tx)+58,196,'BELSŐ HTTPS / AUTOMATIKUS TANÚSÍTVÁNY',15,PAL.accent))
    elements.append(label(margin+(tr-tx)+58,231,'Caddy: tls internal; automatikus kiadás és megújítás.\nGyökér-CA: kliens és Checkmk trust store; CA-adatok mentése.',18))
    y=176+(tb-ty)+32
    info=('Quorum: 2 / 3 manager  •  docker stack deploy  •  privát overlay hálózatok' if swarm else
          'Butane → Ignition → systemd  •  docker compose up -d  •  elkülönített bridge hálózatok')
    elements.append(label(margin,y,info,19,PAL.accent))
    y+=56
    elements.append(label(margin,y,'SZOLGÁLTATÁSOK ÉS ADATUTAK  /  logikai nézet; a szaggatott nyíl logtovábbítás',16,PAL.muted))
    y+=42
    elements+=translate(drawing,margin-gx,y-gy)
    y+=gb-gy+42
    # Full-width explanatory bands keep placement and external dependencies explicit.
    bands=[
      ('KÜLSŐ MONITORING',
       'Független Checkmk → HTTPS / cert ellenőrzés + host- és Docker-agent.\n'
       'CPU, memória, lemez, konténerállapot, SMTP queue; a monitoring elérése forrás-IP-re korlátozott.'),
      ('VÉDELEM ÉS BIZALOM',
       ('443 csak belső LAN-ról; SSH csak admin hálózatról. Swarm: 2377/TCP, 7946/TCP+UDP, 4789/UDP csak node-ok között.\n'
        'A 443 routing mesh mögött Caddy terminálja a TLS-t. DB / SMTP / Loki / NFS nem publikus; Grafana Caddy mögött, belépéssel.' if swarm else
        '443 csak belső LAN-ról; SSH csak admin hálózatról. Docker továbbított forgalmára külön tűzfalszabályok.\n'
        'DB / SMTP / Loki hostport nélkül; Grafana Caddy mögött, belépéssel. SELinux aktív; minimális konténerjogosultságok.')),
      ('TARTÓS ADAT ÉS SECRETS',
       ('Caddy CA + MariaDB + Postfix queue + Loki/Grafana: node-1-re kötött tartós adatok. Alloy minden node-on.\n'
        'WordPress: azonos, rögzített image + közös uploads; NFS külön szolgáltatás. Swarm secrets; titkosított külső mentés.' if swarm else
        'MariaDB + WordPress uploads + Caddy CA + Postfix queue + Loki: tartós volume-ok; titkosított mentés a VM-en kívül.\n'
        'Compose secrets: jogosultságkezelt fájlokból; a titkosítás külön feladat. CA gyökértanúsítvány a kliensre és Checkmk-ra.')),
      ('DÖNTÉSI SZEMPONT',
       ('Előny: két webes task, gördülő frissítés, ütemezés és natív secrets. A két webes taskot külön node-ra kell helyezni.\n'
        'Korlát: node-1, NFS és a közös Proxmox host hibapont. Ez a terv nem teljes HA; ahhoz további redundancia kell.' if swarm else
        'Előny: kisebb scope, könnyebb hibakeresés és reprodukálható beadás. A kötelező szolgáltatások bemutathatók.\n'
        'Korlát: VM / host kiesésekor áll a szolgáltatás; frissítéskor tervezett leállás. Visszaállítás mentésből.')),
    ]
    for heading,body in bands:
        elements.append(Box(x=margin,y=y,width=width,height=111,style=Style(fill=PAL.surface_alt,stroke=PAL.rule,roughness=0,stroke_width=1,rounded=False)))
        elements.append(label(margin+20,y+14,heading,15,PAL.accent if heading=='DÖNTÉSI SZEMPONT' else PAL.muted))
        elements.append(label(margin+20,y+44,body,18))
        y+=125
    status = ('Elvetett alternatíva (2026-11-13); Docker CE, nem az FCOS beépített Moby' if swarm else
              'Docker CE, nem az FCOS beépített Moby (eldöntve: 2026-11-13)')
    elements.append(label(margin,y+4, 'TERV, NEM TELEPÍTÉSI IGAZOLÁS  •  ' + status + '  •  CA-adatok mentése kötelező',15,PAL.muted))
    sources = ('Docker Swarm admin / services / ingress' if swarm else 'Docker Compose secrets; Docker iptables tűzfal')
    elements.append(label(margin,y+32, 'Források: ' + sources + '; Caddy Automatic HTTPS; Checkmk Docker monitoring. Részletek: SOURCES.txt',14,PAL.muted))
    doc=build_drawable_file(elements,theme_name='dark')
    # ASCII arrows keep the exported labels portable across local font sets.
    for element in doc['elements']:
        if element.get('type') == 'text':
            for field in ['text','originalText']:
                if field in element:
                    element[field] = element[field].replace('→', '>')
    doc['appState']['viewBackgroundColor']=PAL.canvas
    doc['appState']['exportBackground']=True
    doc['appState']['exportWithDarkMode']=False
    doc['appState']['customData']={'comparison':{'variant':'swarm' if swarm else 'compose','graph':graph.model_dump(mode='json'),'topology':topology.model_dump(mode='json')}}
    save_excalidraw(doc,str(OUT/(slug+'.excalidraw')))
    export_to_svg(OUT/(slug+'.excalidraw'),OUT/(slug+'.svg'))
    print(slug, 'created', round(width), 'wide')

if __name__=='__main__':
    make(False)
    make(True)
