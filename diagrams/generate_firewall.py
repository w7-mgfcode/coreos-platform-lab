"""Three-layer firewall diagram: 09-tuzfal-dark.*"""
from generate_argue import COL, INK, MUTED, Diagram


def firewall():
    d = Diagram()
    d.text(40, 30, 'Tűzfal  ·  három réteg', 30, INK)
    d.text(40, 76, 'Kívülről befelé: Proxmox, host, Docker-hálózatok.', 17, MUTED)

    # Nested layers – every connection has to pass all of them
    d.box(300, 150, 1000, 560, color='amber', fill=False, sw=4, rounded=False)
    d.text(316, 162, '1  Proxmox tűzfal', 15, COL['amber'][0])
    host = d.box(340, 200, 920, 470, color='orange', fill=False, sw=3, style='dashed', rounded=False)
    d.text(356, 212, '2  Host tűzfal (DOCKER-USER)', 15, COL['orange'][0])
    d.box(380, 250, 840, 380, color='sky', fill=False, sw=2, style='dashed', rounded=False)
    d.text(396, 262, '3  Docker-hálózatok', 15, COL['sky'][0])

    caddy = d.box(420, 330, 170, 70, 'Caddy', 'blue', size=15)
    wp = d.box(650, 330, 170, 70, 'WordPress', 'blue', size=15)
    db = d.box(900, 300, 190, 70, 'MariaDB\nnincs internet', 'green', size=14)
    pf = d.box(900, 420, 190, 70, 'Postfix', 'orange', size=15)
    logs = d.box(420, 520, 190, 70, 'Loki + Grafana\nnincs internet', 'violet', size=14)
    d.arrow([(505, 400), (505, 520)], color='violet', sw=2, style='dashed', label='log', start=caddy, end=logs)

    d.arrow([(590, 365), (650, 365)], color='blue', sw=2, start=caddy, end=wp)
    d.arrow([(820, 350), (900, 335)], color='green', sw=2, start=wp, end=db)
    d.arrow([(820, 385), (900, 450)], color='orange', sw=2, start=wp, end=pf)

    relay = d.ellipse(1360, 420, 190, 70, 'Külső SMTP\nrelay', 'orange')
    d.arrow([(1090, 455), (1360, 455)], color='orange', sw=2, label='csak 587', start=pf, end=relay)

    # Allowed sources on the left, everyone else stops at layer 1
    lan = d.ellipse(40, 330, 200, 70, 'Belső hálózat', 'blue')
    d.arrow([(240, 365), (420, 365)], color='blue', sw=3, label='443', start=lan, end=caddy)
    adm = d.ellipse(40, 440, 200, 70, 'Admin', 'gray')
    d.arrow([(240, 475), (338, 475)], color='gray', sw=2, label='22', start=adm, end=host)
    cmk = d.ellipse(40, 550, 200, 70, 'Checkmk', 'green')
    d.arrow([(240, 585), (338, 585)], color='green', sw=2, label='agent', start=cmk, end=host)
    bad = d.ellipse(40, 660, 200, 70, 'Bárki más', 'red')
    d.arrow([(240, 695), (298, 695)], color='red', sw=2, style='dashed', start=bad, head='bar')
    d.text(316, 684, 'tiltva', 15, COL['red'][0])

    d.text(40, 770, 'A tiltott kapcsolatokat tesztekkel igazolom.', 15, MUTED)
    d.save('09-tuzfal-dark')


if __name__ == '__main__':
    firewall()
