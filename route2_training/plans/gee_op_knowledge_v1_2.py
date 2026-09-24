"""GEE operation knowledge table v1.2 - Round 2 additions (owner-approved).

~30 deterministic entries from the Round-1 failure redistribution audit,
each independently screened against the four-part standard (deterministic
intent + typed I/O + slot roles + renderable).

Explicitly REJECTED (stays fail-closed):
  - bare 'ee.Algorithms'  (namespace prefix artifact)
  - bare 'ee.Terrain'     (namespace prefix artifact)
Bare aliases 'rename' / 'multiply' / 'buffer' map to their existing
fully-specified operations (extractor spelling variants).
"""

from route2_training.plans.gee_op_knowledge_v1_1 import K as _K_r1

K = dict(_K_r1)


def _k(op, family, intent, tin, tout, roles=(), kind='op'):
    K[op] = {'family': family, 'intent': intent, 'in': tin, 'out': tout,
             'roles': list(roles), 'kind': kind, 'round': 'v1.2-r2'}


# --- bare aliases -> existing fully-specified entries ---
_k('rename', 'BAND_SELECT', 'rename the selected bands', 'raster', 'raster', ['band names'])
_k('multiply', 'BAND_ARITHMETIC', 'combine rasters by multiply', ('raster', 'raster'), 'raster')
_k('buffer', 'VECTOR_GEOMETRY', 'buffer a geometry by a distance', 'geometry', 'geometry', ['buffer distance'])

# --- reducers (modifiers) ---
for red in ['variance', 'linearRegression', 'toList', 'linearFit', 'firstNonNull', 'mode']:
    k_intent = {'variance': 'aggregate using the variance statistic',
                'linearRegression': 'reduce with a linear regression fit',
                'toList': 'collect reduced values into a list',
                'linearFit': 'reduce with a robust linear fit',
                'firstNonNull': 'take the first non-null value',
                'mode': 'aggregate using the mode statistic'}[red]
    _k(f'ee.Reducer.{red}', 'AGGREGATION', k_intent, None, None,
       [f'{red} statistic'], kind='reducer')

# --- filters (modifiers) ---
_k('ee.Filter.dayOfYear', 'TEMPORAL_FILTER', 'predicate: property within a day-of-year range',
   None, None, ['day-of-year range predicate'], kind='filter')
_k('ee.Filter.notNull', 'ATTRIBUTE_FILTER', 'predicate: property is not null',
   None, None, ['non-null predicate'], kind='filter')

# --- classifier / clusterer constructors ---
_k('ee.Classifier.smileCart', 'CLASSIFICATION', 'train a CART decision-tree classifier',
   None, 'classifier', kind='ctor')
_k('ee.Clusterer.wekaKMeans', 'CLASSIFICATION', 'train a k-means clusterer',
   None, 'classifier', kind='ctor')

# --- raster band/cast/arithmetic ---
_k('ee.Image.float', 'BAND_ARITHMETIC', 'cast the raster values to floating point', 'raster', 'raster')
_k('ee.Image.byte', 'BAND_ARITHMETIC', 'cast the raster values to byte', 'raster', 'raster')
_k('ee.Image.pow', 'BAND_ARITHMETIC', 'raise the raster values to a power', 'raster', 'raster', ['exponent'])
_k('ee.Image.expression', 'BAND_ARITHMETIC', 'compute band arithmetic from an expression',
   'raster', 'raster', ['arithmetic expression'])
_k('ee.Image.arrayProject', 'BAND_ARITHMETIC', 'project the array bands along axes',
   'raster', 'raster', ['array axes'])
_k('ee.ImageCollection.toBands', 'BAND_SELECT', 'convert the collection into a multi-band raster',
   'raster_collection', 'raster')

# --- composition / paint ---
_k('ee.Image.paint', 'COMPOSITE', 'paint vector features onto the raster',
   ('raster', 'vector'), 'raster', ['painted features'])

# --- vector/collection management ---
_k('ee.ImageCollection.merge', 'COLLECTION_MGMT', 'merge two collections into one',
   ('raster_collection', 'raster_collection'), 'raster_collection')
_k('ee.Image.copyProperties', 'COLLECTION_MGMT', 'copy metadata properties onto the raster',
   'raster', 'raster', ['source properties'])
_k('ee.Join.apply', 'SPATIAL_JOIN', 'join two collections by a match condition',
   ('vector', 'vector'), 'vector', ['join condition'])

# --- geometry ---
_k('ee.Geometry.buffer', 'VECTOR_GEOMETRY', 'buffer a geometry by a distance',
   'geometry', 'geometry', ['buffer distance'])

# --- neighborhood kernels ---
_k('ee.Kernel.fixed', 'NEIGHBORHOOD', 'provision a fixed neighbourhood kernel definition',
   None, 'parameters', kind='ctor')

# --- export ---
_k('Export.image.toDrive', 'EXPORT_OUTPUT', 'export the raster to cloud storage',
   'raster', None, ['export destination'])

# --- temporal/date utilities ---
_k('ee.Date.getRelative', 'TEMPORAL_FILTER', 'get the relative difference between two dates',
   'date', 'scalar')
_k('ee.Date.difference', 'TEMPORAL_FILTER', 'compute the difference between two dates',
   ('date', 'date'), 'scalar')

# --- list utilities ---
_k('ee.List.add', 'COLLECTION_MGMT', 'append a value to the list', 'list', 'list')
_k('ee.List.cat', 'COLLECTION_MGMT', 'concatenate two lists', ('list', 'list'), 'list')
_k('ee.List.repeat', 'COLLECTION_MGMT', 'repeat a value into a list', None, 'list', kind='ctor')
