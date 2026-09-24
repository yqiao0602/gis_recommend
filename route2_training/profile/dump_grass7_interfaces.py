"""Dump GRASS module interfaces - pure python, no shell layers.

For each grass7 module: run <module>.exe --interface-description with an
explicit Windows env; if no exe, parse the .py script's '# %' interface
header comments (the authoritative source GRASS generates its interface
from). Emits records in the same shape as qgis_registry_dump_v1.json.
"""
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent
G83 = r'D:\01_software\09_GIS_Tools\QGIS\apps\grass\grass83'
PY39 = r'D:\01_software\09_GIS_Tools\QGIS\apps\Python39\python.exe'

env = dict(os.environ)
env['GISBASE'] = G83
env['GISRC'] = 'E:/tmp/gisrc'
env['PYTHONPATH'] = G83 + r'\etc\python'
env['PATH'] = ';'.join([G83 + r'\bin', G83 + r'\scripts', G83 + r'\lib',
                        G83 + r'\extrabin',
                        r'D:\01_software\09_GIS_Tools\QGIS\apps\Python39',
                        r'D:\01_software\09_GIS_Tools\QGIS\bin',
                        env.get('PATH', '')])


def parse_header_py(py_path: Path, mod: str):
    """Parse '# %' interface header comments from a GRASS script module."""
    desc, params, outs = '', [], []
    cur = None
    for raw in py_path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line.startswith('# %'):
            continue
        body = line[3:].strip()
        if body == 'option':
            cur = {'name': None, 'description': '', 'type': 'literal',
                   'mandatory': False}
            params.append(cur)
            continue
        if body == 'flag' or body.startswith('end') or body == 'module':
            if body == 'module':
                continue
            cur = None
            continue
        if cur is None:
            if body.startswith('description:'):
                desc = body.split(':', 1)[1].strip()
            continue
        key, _, val = body.partition(':')
        val = val.strip()
        if key == 'key':
            cur['name'] = val
        elif key == 'description':
            cur['description'] = (cur['description'] + ' ' + val).strip()
        elif key == 'label':
            cur['description'] = (val + ' ' + cur['description']).strip()
        elif key == 'required':
            cur['mandatory'] = val == 'yes'
        elif key == 'gisprompt':
            parts = [p.split(':')[0] for p in val.split(',')]
            if 'raster' in parts:
                cur['type'] = 'raster'
            elif 'vector' in parts:
                cur['type'] = 'vector'
    return {'id': f'grass7:{mod}', 'name': mod, 'provider': 'GRASS',
            'shortDescription': desc,
            'parameters': [p for p in params if p['name']],
            'outputs': []}


def main() -> None:
    mods = [l.strip() for l in (BASE / 'grass7_modules.txt').read_text().splitlines() if l.strip()]
    records, nofile = [], []
    for mod in mods:
        exe = Path(G83) / 'bin' / (mod + '.exe')
        scr = Path(G83) / 'scripts' / (mod + '.py')
        if exe.exists():
            try:
                r = subprocess.run([str(exe), '--interface-description'],
                                   capture_output=True, timeout=60, env=env)
                root = ET.fromstring(r.stdout.decode('utf-8', errors='replace'))
                params = []
                for p in root.findall('parameter'):
                    gis = p.find('gisprompt')
                    elem = gis.get('element') if gis is not None else None
                    params.append({
                        'name': p.get('name'),
                        'description': ((p.findtext('label') or '').strip() + ' - '
                                        + (p.findtext('description') or '').strip()).strip(' -'),
                        'type': {'raster': 'raster', 'vector': 'vector', 'file': 'file'}.get(elem, 'literal'),
                        'mandatory': p.get('required') == 'yes',
                        'default': None})
                outs = [{'name': o.get('name'),
                         'description': (o.findtext('description') or '').strip(),
                         'type': {'raster': 'raster', 'vector': 'vector'}.get(
                             (o.find('gisprompt').get('element')
                              if o.find('gisprompt') is not None else None), 'file')}
                        for o in root.findall('output')]
                records.append({'id': f'grass7:{mod}', 'name': mod, 'provider': 'GRASS',
                                'shortDescription': (root.findtext('description') or '').strip(),
                                'parameters': params, 'outputs': outs})
                continue
            except Exception:
                pass  # fall through to header parse
        if scr.exists():
            records.append(parse_header_py(scr, mod))
        else:
            nofile.append(mod)
    (BASE / 'qgis_registry_dump_grass7_v1.json').write_text(
        json.dumps(records, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'records: {len(records)} | no-source: {len(nofile)}')
    if nofile:
        print('no-source modules:', nofile[:10], '...' if len(nofile) > 10 else '')


if __name__ == '__main__':
    main()
