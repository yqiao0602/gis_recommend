"""Dump the authoritative QGIS processing registry (Layer B source).

Run with QGIS python:  D:\\01_software\\09_GIS_Tools\\QGIS\\bin\\python-qgis-ltr.bat
route2_training\\profile\\dump_qgis_registry.py

Emits one JSON record per registered algorithm: id, name, provider,
shortDescription, parameterDefinitions (name/description/type/mandatory/
default), outputDefinitions (name/type). This is the authoritative
parameter-schema source for the Operator Capability Profile Layer B,
and shortDescription seeds Layer C operation_intent.
"""

import json
import sys
from pathlib import Path

OUT = Path(__file__).parent / 'qgis_registry_dump_v1.json'


def main() -> int:
    import os
    qgis_root = Path(os.environ.get('QGIS_ROOT',
                                    r'D:\01_software\09_GIS_Tools\QGIS'))
    plugins = qgis_root / 'apps' / 'qgis-ltr' / 'python' / 'plugins'
    if plugins.exists():
        sys.path.append(str(plugins))
    from qgis.core import QgsApplication
    QgsApplication.setPrefixPath(str(qgis_root / 'apps' / 'qgis-ltr'), True)
    app = QgsApplication([], False)
    app.initQgis()
    import processing  # noqa: F401
    from processing.core.Processing import Processing
    Processing.initialize()  # actually load the algorithm providers

    reg = QgsApplication.processingRegistry()
    records = []
    for alg in reg.algorithms():
        try:
            params = []
            for p in alg.parameterDefinitions():
                try:
                    params.append({
                        'name': p.name(),
                        'description': p.description(),
                        'type': p.type() if hasattr(p, 'type') else str(p),
                        'mandatory': not p.flags() or True,  # fixed below
                        'default': str(p.defaultValue()) if p.defaultValue() is not None else None,
                    })
                except Exception as pe:  # per-parameter resilience
                    params.append({'name': getattr(p, 'name', lambda: None)(),
                                   'error': str(pe)[:120]})
            # mandatory flag: optional params are flagged Optional
            for p, rec in zip(alg.parameterDefinitions(), params):
                from qgis.core import QgsProcessingParameterDefinition
                rec['mandatory'] = not bool(p.flags() & QgsProcessingParameterDefinition.FlagOptional)
            outs = []
            for o in alg.outputDefinitions():
                outs.append({'name': o.name(), 'description': o.description(),
                             'type': o.type() if hasattr(o, 'type') else str(o)})
            records.append({
                'id': alg.id(),
                'name': alg.displayName(),
                'provider': alg.provider().name() if alg.provider() else None,
                'shortDescription': alg.shortDescription(),
                'parameters': params,
                'outputs': outs,
            })
        except Exception as ae:
            records.append({'id': getattr(alg, 'id', lambda: f'<err:{ae}>')(),
                            'error': str(ae)[:200]})

    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = [r for r in records if 'error' not in r]
    print(f'dumped {len(ok)}/{len(records)} algorithms -> {OUT}')
    from collections import Counter
    print('by provider:', Counter(r['provider'] for r in ok).most_common(8))
    return 0


if __name__ == '__main__':
    sys.exit(main())
