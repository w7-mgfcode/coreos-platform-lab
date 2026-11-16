"""Easy-to-read architecture pair to attach to the clarification message.

  07-arch-a-compose-dark.*  - Compose on one Fedora CoreOS VM
  08-arch-b-swarm-dark.*    - Swarm on three Fedora CoreOS VMs
"""
from generate_argue import COL, INK, MUTED, Diagram


def frame(d, title, sub):
    d.text(40, 30, title, 30, INK)
    d.text(40, 76, sub, 17, MUTED)
    d.box(280, 150, 960, 640, color='red', fill=False, style='dashed', sw=2, rounded=False)
    d.text(300, 760, 'Otthoni Proxmox lab', 14, COL['red'][0])


def externals(d, monitor_target, relay_y):
    user = d.ellipse(40, 250, 180, 90, 'Felhasználó', 'blue', size=15)
    cmk = d.ellipse(1300, 250, 200, 90, 'Checkmk\nmonitoring', 'green', size=15)
    relay = d.ellipse(1300, relay_y, 200, 90, 'Külső SMTP\nrelay', 'orange', size=15)
    d.arrow([(1300, 295), (1222, 295)], color='green', sw=2, start=cmk, end=monitor_target)
    return user, relay


def legend(d):
    d.line([(40, 830), (90, 830)], color=INK, sw=2)
    d.text(100, 821, 'forgalom', 14, MUTED)
    d.line([(220, 830), (270, 830)], color='violet', sw=2, style='dashed')
    d.text(280, 821, 'logok', 14, MUTED)


def compose():
    d = Diagram()
    frame(d, 'A)  Docker Compose  ·  egy CoreOS VM',
          'Minden egy gépen fut, a szolgáltatások külön hálózatokon, tűzfal mögött.')
    vm = d.box(320, 190, 900, 480, color='amber', fill=False, sw=3, rounded=False)
    d.text(340, 202, 'Fedora CoreOS VM  ·  Docker Compose  ·  tűzfal', 15, INK)
    caddy = d.box(380, 250, 200, 90, 'Caddy\nHTTPS · belső CA', 'blue')
    wp = d.box(680, 250, 200, 90, 'WordPress', 'blue')
    db = d.box(980, 250, 200, 90, 'MariaDB', 'green')
    logs = d.box(380, 480, 200, 90, 'Loki + Grafana\nkereshető logok', 'violet')
    pf = d.box(680, 480, 200, 90, 'Postfix', 'orange')
    d.text(350, 620, 'külön hálózatok: web · adatbázis · levél · logok', 14, COL['sky'][0])

    user, relay = externals(d, vm, 480)
    d.arrow([(220, 295), (380, 295)], color='blue', sw=3, label='HTTPS', start=user, end=caddy)
    d.arrow([(580, 295), (680, 295)], color='blue', sw=2, start=caddy, end=wp)
    d.arrow([(880, 295), (980, 295)], color='green', sw=2, label='SQL', start=wp, end=db)
    d.arrow([(780, 340), (780, 480)], color='orange', sw=2, label='email', start=wp, end=pf)
    d.arrow([(880, 525), (1300, 525)], color='orange', sw=2, label='SMTP', start=pf, end=relay)
    d.arrow([(480, 340), (480, 480)], color='violet', sw=2, style='dashed', label='log', start=caddy, end=logs)
    d.arrow([(680, 525), (580, 525)], color='violet', sw=2, style='dashed', start=pf, end=logs)
    legend(d)
    d.save('07-arch-a-compose-dark')


def swarm():
    d = Diagram()
    frame(d, 'B)  Docker Swarm  ·  három CoreOS VM',
          'A WordPress két példányban fut, a többi szolgáltatás az első gépen marad.')
    n1 = d.box(320, 190, 900, 220, color='amber', fill=False, sw=3, rounded=False)
    d.text(336, 200, 'node-1  ·  Fedora CoreOS', 14, INK)
    d.box(320, 450, 440, 205, color='amber', fill=False, sw=3, rounded=False)
    d.text(336, 460, 'node-2', 14, INK)
    d.box(780, 450, 440, 205, color='amber', fill=False, sw=3, rounded=False)
    d.text(796, 460, 'node-3', 14, INK)

    caddy = d.box(350, 250, 190, 90, 'Caddy\nHTTPS · belső CA', 'blue', size=14)
    logs = d.box(570, 250, 190, 90, 'Loki + Grafana', 'violet', size=14)
    db = d.box(790, 250, 190, 90, 'MariaDB', 'green', size=14)
    pf = d.box(1010, 250, 190, 90, 'Postfix', 'orange', size=14)

    grp = d.box(400, 500, 780, 115, color='blue', fill=False, style='dashed', sw=2, rounded=False)
    d.box(420, 515, 280, 80, 'WordPress #1', 'blue')
    d.box(880, 515, 280, 80, 'WordPress #2', 'blue')
    d.text(400, 623, 'egy WordPress szolgáltatás, 2 példány', 14, COL['blue'][0])
    nfs = d.box(560, 700, 420, 52, 'közös fájltár (NFS)', 'green', size=15)

    user, relay = externals(d, n1, 380)

    d.arrow([(220, 295), (350, 295)], color='blue', sw=3, label='HTTPS', start=user, end=caddy)
    d.arrow([(470, 340), (470, 500)], color='blue', sw=2, start=caddy, end=grp)
    d.arrow([(885, 500), (885, 340)], color='green', sw=2, label='SQL', start=grp, end=db)
    d.arrow([(1105, 500), (1105, 340)], color='orange', sw=2, label='email', start=grp, end=pf)
    d.arrow([(1200, 320), (1260, 320), (1310, 400)], color='orange', sw=2, label='SMTP', start=pf, end=relay)
    d.arrow([(900, 615), (900, 700)], color='green', sw=2, label='fájlok', start=grp, end=nfs)
    d.arrow([(540, 295), (570, 295)], color='violet', sw=2, style='dashed', start=caddy, end=logs)
    d.arrow([(1105, 250), (1105, 228), (665, 228), (665, 250)], color='violet', sw=2,
            style='dashed', label='log', start=pf, end=logs)
    legend(d)
    d.save('08-arch-b-swarm-dark')


if __name__ == '__main__':
    compose()
    swarm()
