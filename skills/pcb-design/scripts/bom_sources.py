#!/usr/bin/env python3
"""Build a BOM with ordering links at several distributors.

    python bom_sources.py kicad/board.kicad_sch -o docs/bom.md [--html docs/bom.html]
    python bom_sources.py --csv existing-bom.csv -o docs/bom.md

Reads these symbol fields: MPN, Manufacturer, and the distributor order codes LCSC,
Mouser, DigiKey, Farnell (each may hold the order code or a full product URL). For
every BOM line it writes links to Mouser, DigiKey, Farnell, LCSC and Octopart:

  listed   the symbol carries that distributor's order code: the link uses it
  search   no order code: a search for the MPN at that distributor

Search links are not proof the part is stocked there. At release, open them (or query
the distributors), write the confirmed order codes back into the symbol fields, and
record the date in design-notes.md. Lines without an MPN are errors (exit code 1).
"""
import argparse
import csv
import datetime
import html
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote

FIELDS = ['Reference', 'Value', 'Footprint', '${QUANTITY}', '${DNP}', 'MPN', 'Manufacturer',
          'LCSC', 'Mouser', 'DigiKey', 'Farnell', 'Datasheet']
SEARCH = [
    ('Mouser', 'https://www.mouser.com/c/?q={}'),
    ('DigiKey', 'https://www.digikey.com/en/products/result?keywords={}'),
    ('Farnell', 'https://www.farnell.com/search?st={}'),
    ('LCSC', 'https://www.lcsc.com/search?q={}'),
    ('Octopart', 'https://octopart.com/search?q={}'),
]


def find_cli():
    for c in (shutil.which('kicad-cli'), '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
              r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'):
        if c and os.path.isfile(c):
            return c
    sys.exit('kicad-cli not found')


def export(sch):
    out = os.path.join(tempfile.mkdtemp(), 'bom.csv')
    r = subprocess.run([find_cli(), 'sch', 'export', 'bom', '-o', out, '--fields', ','.join(FIELDS),
                        '--group-by', 'Value,Footprint,MPN,${DNP}', sch], capture_output=True, text=True)
    if r.returncode or not os.path.isfile(out):
        sys.exit('kicad-cli sch export bom failed:\n' + (r.stdout + r.stderr)[-500:])
    return out


def links(row):
    """-> [(distributor, url, 'listed' | 'search')]"""
    mpn = row.get('MPN', '').strip()
    out = []
    for dist, pattern in SEARCH:
        code = row.get(dist, '').strip()
        if code.lower().startswith('http'):
            out.append((dist, code, 'listed'))
        elif code:
            out.append((dist, pattern.format(quote(code)), 'listed'))
        elif mpn:
            out.append((dist, pattern.format(quote(mpn)), 'search'))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('schematic', nargs='?')
    ap.add_argument('--csv', help='use an existing BOM CSV instead of exporting one')
    ap.add_argument('-o', '--output', required=True, help='Markdown file to write')
    ap.add_argument('--html', help='also write a standalone HTML table')
    a = ap.parse_args()
    if not a.csv and not a.schematic:
        ap.error('give a schematic or --csv')
    rows = list(csv.DictReader(open(a.csv or export(a.schematic), encoding='utf-8-sig')))
    for r in rows:      # tolerate the labels kicad-cli or other tools use
        for old, new in (('QUANTITY', 'Qty'), ('${QUANTITY}', 'Qty'), ('Refs', 'Reference'), ('${DNP}', 'DNP')):
            if old in r and new not in r:
                r[new] = r[old]
    fitted = [r for r in rows if not r.get('DNP', '').strip()]
    no_mpn = [r for r in fitted if not r.get('MPN', '').strip()]
    multi = [r for r in fitted if sum(1 for d in ('LCSC', 'Mouser', 'DigiKey', 'Farnell') if r.get(d, '').strip()) >= 2]
    today = datetime.date.today().isoformat()
    summary = ('%d line(s), %d fitted; %d without an MPN; %d with order codes at two or more distributors'
               % (len(rows), len(fitted), len(no_mpn), len(multi)))
    md = ['# Bill of materials', '', 'Generated %s. %s.' % (today, summary), '',
          '`listed` links use an order code stored in the schematic; `search` links only search for the MPN.', '',
          '| Refs | Qty | Value | Footprint | Manufacturer | MPN | Where to buy | DNP |', '|---|---|---|---|---|---|---|---|']
    trs = []
    for r in rows:
        ls = links(r)
        buy = ' · '.join('[%s](%s)%s' % (d, u, '' if k == 'listed' else ' (search)') for d, u, k in ls) or '**no MPN**'
        fp = r.get('Footprint', '').split(':')[-1]
        md.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            r.get('Reference', ''), r.get('Qty', ''), r.get('Value', ''), fp, r.get('Manufacturer', ''),
            r.get('MPN', '') or '**missing**', buy, r.get('DNP', '')))
        hbuy = ' · '.join('<a href="%s">%s</a>%s' % (html.escape(u), d, '' if k == 'listed' else ' <small>(search)</small>')
                          for d, u, k in ls) or '<b>no MPN</b>'
        trs.append('<tr>' + ''.join('<td>%s</td>' % c for c in (
            html.escape(r.get('Reference', '')), html.escape(r.get('Qty', '')), html.escape(r.get('Value', '')),
            html.escape(fp), html.escape(r.get('Manufacturer', '')),
            html.escape(r.get('MPN', '')) or '<b>missing</b>', hbuy, html.escape(r.get('DNP', '')))) + '</tr>')
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    open(a.output, 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    if a.html:
        open(a.html, 'w', encoding='utf-8').write(
            '<!doctype html><meta charset="utf-8"><title>Bill of materials</title>'
            '<style>body{font:14px system-ui,sans-serif;margin:2rem}table{border-collapse:collapse}'
            'td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top}th{background:#f3f3f3;text-align:left}'
            'tr:nth-child(even){background:#fafafa}</style>'
            '<h1>Bill of materials</h1><p>Generated %s. %s.</p><table><tr>%s</tr>%s</table>'
            % (today, html.escape(summary),
               ''.join('<th>%s</th>' % h for h in ('Refs', 'Qty', 'Value', 'Footprint', 'Manufacturer', 'MPN', 'Where to buy', 'DNP')),
               ''.join(trs)))
    print(summary)
    print('wrote %s%s' % (a.output, (' and ' + a.html) if a.html else ''))
    return 1 if no_mpn else 0


if __name__ == '__main__':
    sys.exit(main())
