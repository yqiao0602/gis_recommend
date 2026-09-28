# GEE Strict Authority Gap Clusters v1

- Canonicalization-gap rows: 30
- Unmapped raw occurrences: 438
- L3-mapping-gap rows: 26
- Canonical L3-gap occurrences: 154
- Training admission: not granted

## Canonicalization Categories

- `proven_ee_type_unresolved`: 27 occurrences / 11 rows
- `typed_receiver_operator_gap`: 1 occurrences / 1 rows
- `untyped_receiver`: 410 occurrences / 22 rows

## Top Raw Method Clusters

- `untyped_receiver | <unknown> | select`: 53 occurrences / 8 rows; examples=a.select, added.select, fcsat.select, gf5_tip9.select, gldasrange.filter.select
- `untyped_receiver | <unknown> | filterdate`: 37 occurrences / 10 rows; examples=chirps.filterdate, gldas.filterdate, l5.filterbounds.filterdate, l7all.filterdate, l7ftimespace.filterdate
- `untyped_receiver | <unknown> | addbands`: 37 occurrences / 6 rows; examples=fcsat.addbands, fcsat.addbands.addbands, fcsat.addbands.addbands.addbands, fcsat.addbands.addbands.addbands.addbands, image.addbands
- `untyped_receiver | <unknown> | get`: 34 occurrences / 3 rows; examples=image.get, imagen.get, img.get, mean.get, minmax.get
- `untyped_receiver | <unknown> | rename`: 23 occurrences / 5 rows; examples=afterimg.normalizeddifference.rename, beforeimg.normalizeddifference.rename, beforewater.gt.and.rename, beforewater.lt.and.rename, boxcarmask.rename
- `untyped_receiver | <unknown> | reduce`: 22 occurrences / 2 rows; examples=chirps2000.reduce, chirps2001.reduce, chirps2002.reduce, chirps2003.reduce, chirps2004.reduce
- `untyped_receiver | <unknown> | reduceregion`: 22 occurrences / 2 rows; examples=chirps2000_mean.reduceregion, chirps2001_mean.reduceregion, chirps2002_mean.reduceregion, chirps2003_mean.reduceregion, chirps2004_mean.reduceregion
- `untyped_receiver | <unknown> | expression`: 14 occurrences / 5 rows; examples=classified.eq.expression, image.expression, img.expression, why.expression
- `untyped_receiver | <unknown> | filter`: 12 occurrences / 6 rows; examples=filtered2.filter, gldasrange.filter, l8_agu19.filter, l8_ready.filter, l8_sr.filter
- `untyped_receiver | <unknown> | neq`: 12 occurrences / 1 rows; examples=coldcandidates.size.neq, coldcandidates1.size.neq, coldcandidates2.size.neq, hotcandidates.size.neq, hotcandidates1.size.neq
- `untyped_receiver | <unknown> | filterbounds`: 10 occurrences / 7 rows; examples=blocks.filterbounds, l5.filterbounds, l7ftime.filterbounds, l8_ready.filter.filterdate.filterbounds, landsat5.filterbounds
- `untyped_receiver | <unknown> | first`: 10 occurrences / 3 rows; examples=gldasrange.filter.select.first, l7summer_images.first, lc.filter.first, mod09ga.filterdate.first, s2sr.filterbounds.filterdate.first
- `untyped_receiver | <unknown> | gt`: 9 occurrences / 3 rows; examples=afterwater.gt, beforewater.gt, image.normalizeddifference.gt, ndvi_2018.gt, redness.gt
- `untyped_receiver | <unknown> | clip`: 8 occurrences / 5 rows; examples=gf5.clip, image.classify.clip, s2_boa_oct9_2020.clip, sma.clip, sst.select.filterdate.filter.median.clip
- `untyped_receiver | <unknown> | normalizeddifference`: 8 occurrences / 4 rows; examples=afterimg.normalizeddifference, beforeimg.normalizeddifference, image.normalizeddifference, s2_2018.normalizeddifference, s2_2020.normalizeddifference
- `untyped_receiver | <unknown> | updatemask`: 8 occurrences / 3 rows; examples=diff.updatemask, maskedmvi.updatemask, maskedredness.updatemask, redness.updatemask, redness.updatemask.updatemask
- `untyped_receiver | <unknown> | median`: 7 occurrences / 4 rows; examples=l5.filterbounds.filterdate.map.median, l8_agu19.map.median, s2.median, sst.select.filterdate.filter.median, sst.select.filterdate.median
- `untyped_receiver | <unknown> | multiply`: 7 occurrences / 1 rows; examples=meanndvi8.multiply, ndvi.multiply, nee1.multiply, par.multiply
- `untyped_receiver | <unknown> | set`: 6 occurrences / 1 rows; examples=image.set, imagen.set, obj.set
- `untyped_receiver | <unknown> | filtermetadata`: 5 occurrences / 3 rows; examples=gee_tiles.filtermetadata, train.filtermetadata, trainingdata.filtermetadata, trainingdata.filtermetadata.filtermetadata
- `untyped_receiver | <unknown> | subtract`: 5 occurrences / 3 rows; examples=ndvi.multiply.subtract, ndvi_2020.subtract, target.subtract
- `untyped_receiver | <unknown> | eq`: 5 occurrences / 2 rows; examples=classified.eq, classified2.eq, water.eq
- `untyped_receiver | <unknown> | merge`: 5 occurrences / 2 rows; examples=bkt.merge, bkt.merge.merge, bkt.merge.merge.merge, soja2010.merge, soja2020.merge
- `untyped_receiver | <unknown> | tofloat`: 5 occurrences / 2 rows; examples=image.select.addbands.addbands.addbands.addbands.addbands.addbands.tofloat, img.expression.rename.tofloat
- `proven_ee_type_unresolved | <unknown> | get`: 4 occurrences / 3 rows; examples=lista.get, percentiles.get, shp_us_counties.reducecolumns.get, state_selected.reducecolumns.get
- `untyped_receiver | <unknown> | lt`: 4 occurrences / 3 rows; examples=afterwater.lt, beforewater.lt, classified.eq.convolve.lt, diff.lt
- `untyped_receiver | <unknown> | and`: 4 occurrences / 2 rows; examples=beforewater.gt.and, beforewater.lt.and, diff.lt.and
- `proven_ee_type_unresolved | <unknown> | toshort`: 4 occurrences / 1 rows; examples=y.toshort
- `proven_ee_type_unresolved | <unknown> | set`: 3 occurrences / 2 rows; examples=img.select.divide.addbands.addbands.set.set, img.select.divide.addbands.addbands.set.set.set, scamod.set.set
- `untyped_receiver | <unknown> | geometry`: 3 occurrences / 2 rows; examples=rawmvistat.geometry, roi.geometry

## L3 Mapping Gaps

- `ee.feature.geometry`: 30 occurrences / 2 rows
- `ee.image.reducetovectors`: 21 occurrences / 2 rows
- `ee.featurecollection.first`: 11 occurrences / 2 rows
- `ee.image.focal_mean`: 10 occurrences / 1 rows
- `ee.featurecollection.filtermetadata`: 9 occurrences / 6 rows
- `ee.reducer.min`: 8 occurrences / 3 rows
- `ee.reducer.stddev`: 7 occurrences / 2 rows
- `ee.image.focal_median`: 6 occurrences / 1 rows
- `ee.image.pixellonlat`: 5 occurrences / 2 rows
- `ee.reducer.combine`: 5 occurrences / 2 rows
- `ee.reducer.tolist`: 4 occurrences / 2 rows
- `ee.daterange`: 4 occurrences / 1 rows
- `ee.featurecollection.reducecolumns`: 3 occurrences / 2 rows
- `ee.featurecollection.aggregate_array`: 2 occurrences / 2 rows
- `ee.featurecollection.filterdate`: 2 occurrences / 2 rows
- `ee.filter.notnull`: 2 occurrences / 2 rows
- `ee.reducer.first`: 2 occurrences / 2 rows
- `ee.reducer.minmax`: 2 occurrences / 2 rows
- `ee.image.focal_max`: 2 occurrences / 1 rows
- `ee.reducer.count`: 2 occurrences / 1 rows
- `ee.algorithms.image.segmentation.seedgrid`: 1 occurrences / 1 rows
- `ee.featurecollection.limit`: 1 occurrences / 1 rows
- `ee.featurecollection.reducetoimage`: 1 occurrences / 1 rows
- `ee.featurecollection.tolist`: 1 occurrences / 1 rows
- `ee.geometry.coordinates`: 1 occurrences / 1 rows
- `ee.image.focal_mode`: 1 occurrences / 1 rows
- `ee.image.projection`: 1 occurrences / 1 rows
- `ee.image.setmulti`: 1 occurrences / 1 rows
- `ee.imagecollection.distinct`: 1 occurrences / 1 rows
- `ee.imagecollection.flatten`: 1 occurrences / 1 rows
- `ee.imagecollection.getfilmstripthumburl`: 1 occurrences / 1 rows
- `ee.imagecollection.gte`: 1 occurrences / 1 rows
- `ee.imagecollection.tolist`: 1 occurrences / 1 rows
- `ee.imagecollection.updatemask`: 1 occurrences / 1 rows
- `ee.kernel.add`: 1 occurrences / 1 rows
- `ee.reducer.countevery`: 1 occurrences / 1 rows
- `ee.reducer.repeat`: 1 occurrences / 1 rows
