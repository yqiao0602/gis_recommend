"""GEE operation knowledge table v1.1 - Round 1 additions (owner-approved).

Adds ONLY the owner-approved top-10 unknown operations, each satisfying
the four-part standard: deterministic intent + typed I/O + slot roles +
PLAN_SCHEMA_v1 renderability.

Explicitly REJECTED: bare 'ee.Algorithms' (9.5k events) - it is an
un-splittable extractor prefix artifact; the prefix alone cannot
determine behavior, so it stays fail-closed per owner discipline.
"""

from route2_training.plans.gee_op_knowledge_v1 import K as _K_v1

K = dict(_K_v1)


def _k(op, family, intent, tin, tout, roles=(), kind='op'):
    K[op] = {'family': family, 'intent': intent, 'in': tin, 'out': tout,
             'roles': list(roles), 'kind': kind, 'round': 'v1.1-r1'}


# 1. polygon constructor (13.4k events)
_k('ee.Geometry.Polygon', 'GEOMETRY_DEFINE', 'provision a polygon geometry',
   None, 'geometry', kind='ctor')
# 2. membership predicate (12.5k)
_k('ee.Filter.inList', 'ATTRIBUTE_FILTER', 'predicate: property value is contained in a list',
   None, None, ['list membership predicate'], kind='filter')
# 3. date formatting utility (11.8k)
_k('ee.Date.format', 'TEMPORAL_FILTER', 'format a date value as text',
   'date', 'text')
# 4. band concatenation (11.1k)
_k('ee.Image.cat', 'BAND_SELECT', 'concatenate the bands of multiple rasters',
   ('raster', 'raster'), 'raster', ['bands to combine'])
# 5. integer cast (10.1k)
_k('ee.Number.int', 'BAND_ARITHMETIC', 'cast the scalar to an integer',
   'scalar', 'scalar')
# 6. feature property assignment (10.1k)
_k('ee.Feature.set', 'COLLECTION_MGMT', 'set properties on a feature',
   'feature', 'feature', ['property values'])
# 7. collection sort (9.7k)
_k('ee.ImageCollection.sort', 'COLLECTION_MGMT', 'sort the collection by a property',
   'raster_collection', 'raster_collection', ['sort property'])
# 8. coordinate-band generation (9.4k)
_k('ee.Image.pixelLonLat', 'BAND_ARITHMETIC', 'add longitude and latitude coordinate bands to the raster',
   'raster', 'raster', ['coordinate bands'])
# 9. equality predicate alias (9.1k)
_k('ee.Filter.equals', 'ATTRIBUTE_FILTER', 'predicate: property equals value',
   None, None, ['property equals value'], kind='filter')
# 10. bare 'ee.Algorithms' - REJECTED (un-splittable prefix; stays fail-closed)
