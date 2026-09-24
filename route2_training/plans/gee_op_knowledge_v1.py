"""GEE operation knowledge table v1 (⑥-2-① frozen companion asset).

Covers the corpus head (top-60 ops cover the overwhelming majority of
20k sampled rows; 807 distinct ops total). Unmapped ops are FAIL-CLOSED
downstream: steps get intent='unsupported operation' and the row enters
the coverage report - never silently passed.

Entry shape:
  op: (family, intent, in_type, out_type, roles[], kind)
  kind: 'op' = emits a step; 'filter' = ee.Filter modifier (predicate
        constraint); 'reducer' = ee.Reducer modifier (statistic
        constraint); 'ctor' = provisioning constructor.
"""

T_RC = 'raster_collection'
T_R = 'raster'
T_V = 'vector'
T_F = 'feature'
T_G = 'geometry'
T_S = 'scalar'
T_T = 'text'
T_L = 'list'
T_D = 'date'
T_P = 'parameters'
T_C = 'classifier'

K = {}


def k(op, family, intent, tin, tout, roles=(), kind='op'):
    K[op] = {'family': family, 'intent': intent, 'in': tin, 'out': tout,
             'roles': list(roles), 'kind': kind}


# ---- constructors ----
for op, t in [('ee.Image', T_R), ('ee.ImageCollection', T_RC), ('ee.Feature', T_F),
              ('ee.FeatureCollection', T_V), ('ee.Number', T_S), ('ee.String', T_T),
              ('ee.List', T_L), ('ee.Date', T_D), ('ee.Dictionary', T_P),
              ('ee.Array', T_L), ('ee.Geometry', T_G)]:
    k(op, 'GEOMETRY_DEFINE' if t == T_G else 'COLLECTION_MGMT',
      f'provision a {t} value', None, t, kind='ctor')
k('ee.Geometry.Point', 'GEOMETRY_DEFINE', 'provision a point geometry', None, T_G, kind='ctor')
k('ee.Geometry.Rectangle', 'GEOMETRY_DEFINE', 'provision a rectangle geometry', None, T_G, kind='ctor')
k('ee.Image.constant', 'COLLECTION_MGMT', 'provision a constant raster', None, T_R, kind='ctor')
k('ee.Image.pixelArea', 'BAND_ARITHMETIC', 'compute per-pixel area raster', None, T_R, kind='ctor')
k('ee.ImageCollection.fromImages', 'COLLECTION_MGMT', 'assemble an image collection from images', T_L, T_RC)
k('ee.Number.parse', 'BAND_ARITHMETIC', 'parse a text value into a number', T_T, T_S)

# ---- collection filtering ----
k('ee.ImageCollection.filterDate', 'TEMPORAL_FILTER', 'filter an image collection by date range', T_RC, T_RC, ['date constraint'])
k('ee.ImageCollection.filter', 'SPATIAL_FILTER', 'filter an image collection by predicate', T_RC, T_RC, ['filter predicate'])
k('ee.FeatureCollection.filter', 'ATTRIBUTE_FILTER', 'filter a feature collection by predicate', T_V, T_V, ['filter predicate'])
k('ee.ImageCollection.filterBounds', 'SPATIAL_FILTER', 'filter an image collection by spatial extent', T_RC, T_RC, ['spatial extent'])
k('ee.ImageCollection.filterMetadata', 'ATTRIBUTE_FILTER', 'filter an image collection by metadata property', T_RC, T_RC, ['property condition'])
k('ee.FeatureCollection.filterBounds', 'SPATIAL_FILTER', 'filter a feature collection by spatial extent', T_V, T_V, ['spatial extent'])
k('ee.FeatureCollection.filterMetadata', 'ATTRIBUTE_FILTER', 'filter a feature collection by metadata property', T_V, T_V, ['property condition'])

# ---- band / property manipulation ----
k('ee.ImageCollection.select', 'BAND_SELECT', 'select bands from every image in the collection', T_RC, T_RC, ['band selector'])
k('ee.Image.select', 'BAND_SELECT', 'select bands from the raster', T_R, T_R, ['band selector'])
k('ee.Image.rename', 'BAND_SELECT', 'rename the selected bands', T_R, T_R, ['band names'])
k('ee.Image.addBands', 'BAND_SELECT', 'append new bands to the raster', T_R, T_R, ['bands to append'])
k('ee.ImageCollection.map', 'ITERATIVE_APPLY', 'apply an operation to every element of the collection', T_RC, T_RC, ['per-element operation'])
k('ee.List.map', 'ITERATIVE_APPLY', 'apply an operation to every element of the list', T_L, T_L, ['per-element operation'])

# ---- reduction / aggregation ----
for red in ['mean', 'median', 'sum', 'min', 'max', 'stdDev', 'first', 'count',
            'percentile', 'product', 'minMax', 'toMean']:
    k(f'ee.Reducer.{red}', 'AGGREGATION', f'aggregate using the {red} statistic', None, None,
      [f'{red} statistic'], kind='reducer')
k('ee.Reducer.group', 'AGGREGATION', 'group the reduction by property', None, None, ['grouping property'], kind='reducer')
k('ee.Reducer.combine', 'AGGREGATION', 'combine two reducers', None, None, ['combined statistics'], kind='reducer')
k('ee.Reducer.repeat', 'AGGREGATION', 'repeat the reduction over multiple outputs', None, None, ['repeat count'], kind='reducer')
k('ee.ImageCollection.mean', 'AGGREGATION', 'reduce the collection to its temporal mean raster', T_RC, T_R, ['mean statistic'])
k('ee.ImageCollection.median', 'AGGREGATION', 'reduce the collection to its temporal median raster', T_RC, T_R, ['median statistic'])
k('ee.ImageCollection.sum', 'AGGREGATION', 'reduce the collection to its temporal sum raster', T_RC, T_R, ['sum statistic'])
k('ee.ImageCollection.min', 'AGGREGATION', 'reduce the collection to its temporal minimum raster', T_RC, T_R, ['minimum statistic'])
k('ee.ImageCollection.max', 'AGGREGATION', 'reduce the collection to its temporal maximum raster', T_RC, T_R, ['maximum statistic'])
k('ee.ImageCollection.reduce', 'AGGREGATION', 'reduce the collection with a statistic', T_RC, T_R, ['statistic'])
k('ee.Image.reduce', 'AGGREGATION', 'reduce the raster bands with a statistic', T_R, T_R, ['statistic'])
k('ee.Image.reduceRegion', 'REGIONAL_STATS', 'reduce raster values over a region into statistics', T_R, T_P, ['region geometry', 'statistic'])
k('ee.Image.reduceRegions', 'REGIONAL_STATS', 'reduce raster values over many regions into per-region statistics', T_R, T_V, ['region features', 'statistic'])
k('ee.ImageCollection.reduceColumns', 'REGIONAL_STATS', 'reduce collection properties into aggregate statistics', T_V, T_P, ['statistic', 'property selector'])
k('ee.FeatureCollection.reduceColumns', 'REGIONAL_STATS', 'reduce feature properties into aggregate statistics', T_V, T_P, ['statistic', 'property selector'])
k('ee.Image.sample', 'SAMPLE_EXTRACTION', 'sample raster values at points', T_R, T_F, ['sample points'])
k('ee.Image.sampleRegions', 'SAMPLE_EXTRACTION', 'sample raster values over feature regions', T_R, T_F, ['region features'])

# ---- band math / index ----
for op in ['ee.Image.multiply', 'ee.Image.divide', 'ee.Image.add', 'ee.Image.subtract']:
    a = op.split('.')[-1]
    k(op, 'BAND_ARITHMETIC', f'combine rasters by {a}', (T_R, T_R), T_R)
k('ee.Image.normalizedDifference', 'SPECTRAL_INDEX', 'compute the normalized difference of two bands', T_R, T_R, ['two band selectors'])
k('ee.Image.where', 'THRESHOLD_LOGIC', 'assign values where a condition holds', T_R, T_R, ['condition mask'])
k('ee.Image.updateMask', 'MASKING', 'update the raster validity mask', T_R, T_R, ['mask raster'])
k('ee.Image.mask', 'MASKING', 'extract or apply the validity mask', T_R, T_R, ['mask raster'])
k('ee.Image.unmask', 'MASKING', 'replace masked values with fallback values', T_R, T_R, ['fallback values'])
k('ee.Image.clip', 'SPATIAL_CLIP', 'clip the raster to a geometry', (T_R, T_G), T_R, ['clip geometry'])
k('ee.Image.clipToCollection', 'SPATIAL_CLIP', 'clip the raster to the union of feature geometries', (T_R, T_V), T_R, ['clip features'])
k('ee.Image.toFloat', 'BAND_ARITHMETIC', 'cast the raster values to floating point', T_R, T_R)
k('ee.Image.toByte', 'BAND_ARITHMETIC', 'cast the raster values to byte', T_R, T_R)
k('ee.Image.gt', 'THRESHOLD_LOGIC', 'threshold the raster above a value', T_R, T_R, ['threshold value'])
k('ee.Image.lt', 'THRESHOLD_LOGIC', 'threshold the raster below a value', T_R, T_R, ['threshold value'])
k('ee.Image.gte', 'THRESHOLD_LOGIC', 'threshold the raster at or above a value', T_R, T_R, ['threshold value'])
k('ee.Image.lte', 'THRESHOLD_LOGIC', 'threshold the raster at or below a value', T_R, T_R, ['threshold value'])
k('ee.Image.eq', 'THRESHOLD_LOGIC', 'test raster equality against a value', T_R, T_R, ['comparison value'])
k('ee.Image.neq', 'THRESHOLD_LOGIC', 'test raster inequality against a value', T_R, T_R, ['comparison value'])
k('ee.Image.focal_mean', 'NEIGHBORHOOD', 'smooth the raster with a neighbourhood mean', T_R, T_R, ['neighbourhood kernel'])
k('ee.Image.focal_max', 'NEIGHBORHOOD', 'compute the neighbourhood maximum', T_R, T_R, ['neighbourhood kernel'])
k('ee.Image.focal_min', 'NEIGHBORHOOD', 'compute the neighbourhood minimum', T_R, T_R, ['neighbourhood kernel'])
k('ee.Image.blend', 'COMPOSITE', 'blend two rasters for visual composite', (T_R, T_R), T_R)
k('ee.Image.rgb', 'COMPOSITE', 'compose three bands into a visual rgb product', T_R, T_R, ['three band selectors'])

# ---- vector ops ----
k('ee.FeatureCollection.map', 'ITERATIVE_APPLY', 'apply an operation to every feature', T_V, T_V, ['per-feature operation'])
k('ee.FeatureCollection.select', 'BAND_SELECT', 'select properties of the features', T_V, T_V, ['property selector'])
k('ee.FeatureCollection.geometry', 'GEOMETRY_DEFINE', 'dissolve the collection into its union geometry', T_V, T_G)
k('ee.Feature.geometry', 'GEOMETRY_DEFINE', 'extract the feature geometry', T_F, T_G)
k('ee.FeatureCollection.first', 'SAMPLE_EXTRACTION', 'take the first feature of the collection', T_V, T_F)

# ---- geometry / grid ----
k('ee.Geometry.Point', 'GEOMETRY_DEFINE', 'provision a point geometry', None, T_G, kind='ctor')

# ---- classification ----
k('ee.Classifier.smileRandomForest', 'CLASSIFICATION', 'train a random-forest classifier', None, T_C, kind='ctor')
k('ee.Classifier.train', 'CLASSIFICATION', 'train the classifier on labelled samples', (T_C, T_F), T_C, ['labelled samples', 'label property'])
k('ee.Image.classify', 'CLASSIFICATION', 'classify the raster with a trained classifier', (T_R, T_C), T_R, ['trained classifier'])

# ---- conditional ----
k('ee.Algorithms.If', 'THRESHOLD_LOGIC', 'choose between two values by condition', None, None, ['condition'])

# ---- filters (modifiers) ----
for op, pred in [('ee.Filter.eq', 'property equals value'), ('ee.Filter.neq', 'property not equal to value'),
                 ('ee.Filter.lt', 'property less than value'), ('ee.Filter.gt', 'property greater than value'),
                 ('ee.Filter.lte', 'property at most value'), ('ee.Filter.gte', 'property at least value'),
                 ('ee.Filter.date', 'property within date range'), ('ee.Filter.calendarRange', 'property within calendar range'),
                 ('ee.Filter.listContains', 'list property contains value'), ('ee.Filter.and', 'all predicates hold'),
                 ('ee.Filter.or', 'any predicate holds'), ('ee.Filter.not', 'predicate negated'),
                 ('ee.Filter.bounds', 'property within spatial bounds')]:
    k(op, 'SPATIAL_FILTER', f'predicate: {pred}', None, None, [pred], kind='filter')

# ---- scalar / text / list / date utilities ----
for op, a in [('ee.Number.multiply', 'multiply'), ('ee.Number.add', 'add'),
              ('ee.Number.subtract', 'subtract'), ('ee.Number.divide', 'divide'),
              ('ee.Number.pow', 'raise to a power'), ('ee.Number.abs', 'take absolute value')]:
    k(op, 'BAND_ARITHMETIC', f'{a} scalar values', None, T_S)
k('ee.Number.max', 'BAND_ARITHMETIC', 'take the larger scalar', None, T_S)
k('ee.Number.min', 'BAND_ARITHMETIC', 'take the smaller scalar', None, T_S)
k('ee.Number.round', 'BAND_ARITHMETIC', 'round the scalar', None, T_S)
k('ee.String.cat', 'BAND_ARITHMETIC', 'concatenate text values', None, T_T)
k('ee.List.sequence', 'COLLECTION_MGMT', 'generate a numeric sequence', None, T_L, kind='ctor')
k('ee.List.get', 'COLLECTION_MGMT', 'get an element of the list', T_L, None)
k('ee.Date.advance', 'TEMPORAL_FILTER', 'advance the date by an offset', T_D, T_D, ['date offset'])
k('ee.Date.fromYMD', 'TEMPORAL_FILTER', 'build a date from year month day', None, T_D, kind='ctor')
k('ee.Date.millis', 'TEMPORAL_FILTER', 'convert the date to milliseconds', T_D, T_S)
k('ee.Date.parse', 'TEMPORAL_FILTER', 'parse a date from text', T_T, T_D)
k('ee.Dictionary.get', 'COLLECTION_MGMT', 'get an entry of the parameter map', T_P, None)
k('ee.Terrain.slope', 'TERRAIN_DERIVED', 'compute the terrain slope', T_R, T_R)
k('ee.Terrain.hillshade', 'TERRAIN_DERIVED', 'render a hillshade from elevation', T_R, T_R)


if __name__ == '__main__':
    print(f'knowledge table v1: {len(K)} operations')
    from collections import Counter
    print('kinds:', Counter(v['kind'] for v in K.values()))
