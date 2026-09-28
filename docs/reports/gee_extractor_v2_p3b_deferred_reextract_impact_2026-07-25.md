# GEE P3-B Deferred Re-extraction Impact

This report re-extracts the 28 P0 rows marked `extractor_repair_required`
with the deterministic GEE source extractor. It is an impact manifest only:
P4 human rereview is still required, and no row receives training admission here.

## Summary

- Extractor version: `gee-source-extractor-v2.0.3`
- Repair rows: 28
- Hash-verified rows: 28
- Extraction OK rows: 28
- Fail-closed rows: 0
- Core-chain changed rows: 28
- P4 rereview candidates: 28
- Training admission: `not_granted`
- Next gate: P4 human rereview of p4_rereview_candidate rows; no automatic admission

## Re-extraction statuses

- `ok`: 28

## Recovered signal categories

- `evaluation_vector_aggregation`: 10
- `index_mask`: 24
- `ml_classification`: 6
- `sampling_regional_statistics`: 17

## P4 rereview candidates

### gee_raster_core_review_004

- Categories: index_mask
- Added operators: `ee.filter.eq > table.filter > ee.filter.eq > table.filter > ee.filter.eq > table.filter > ee.filter.eq > table.filter > ee.imagecollection.filterbounds.filterdate > image.clip > image.select > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand.eq.and > image.updatemask > image.updatemask.select > image.updatemask.select.copyproperties > image.normalizeddifference`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_005

- Categories: index_mask, sampling_regional_statistics, evaluation_vector_aggregation
- Added operators: `feature.centroid > feature.centroid > feature.centroid > feature.centroid > feature.centroid > feature.centroid > feature.centroid > feature.centroid > feature.centroid > feature.centroid > fc1_point.merge > fc1_point.merge.merge > fc1_point.merge.merge.merge > fc1_point.merge.merge.merge.merge > fc1_point.merge.merge.merge.merge.merge > fc1_point.merge.merge.merge.merge.merge.merge > fc1_point.merge.merge.merge.merge.merge.merge.merge > fc1_point.merge.merge.merge.merge.merge.merge.merge.merge > fc1_point.merge.merge.merge.merge.merge.merge.merge.merge.merge > feature.get`
- Quality flags: `callback, function_callback, named_callback, untyped_receiver, native_js_call`

### gee_raster_core_review_006

- Categories: index_mask
- Added operators: `s2.level1.filterdate > s2.level1.filterdate.filtermetadata > ee.geometry.point > s2.level1.filterdate.filtermetadata.filterbounds > image.select > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand.eq.and > image.updatemask > dataset.first > dataset.first.select > indexes.addall > frame.bandnames > frame.clip > image.bandtypes > ee.kernel.square > image.select > image.select.glcmtexture`
- Quality flags: `unbound_identifier, untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_007

- Categories: index_mask, sampling_regional_statistics, ml_classification
- Added operators: `ee.imagecollection.filterdate.select > ee.imagecollection.filterdate.select.filterbounds > img.multiply > evi.size > evi.tolist > evilist.get > evilist.get > ee.number.multiply > ee.image.constant > img2.subtract > img2.subtract.multiply > img2.subtract.multiply.add > ee.image.constant > ee.image.constant.select > ee.image.constant.select.rename > ee.image.constant.select.rename.clip > img0.addbands > imglist.insert > imglist2.cat > ee.imagecollection.filterdate.select`
- Quality flags: `loop_order_unresolved, callback, function_callback, named_callback, untyped_receiver`

### gee_raster_core_review_009

- Categories: index_mask, sampling_regional_statistics
- Added operators: `ee.filter.date > ee.filter.or > image.filter > image.select > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand.eq.and > image.updatemask > image.updatemask.divide > image.updatemask.divide.select > image.updatemask.divide.select.copyproperties > allsum.map.median > allsum.map.median.clip > image.select > image.select > nir.subtract > nir.add > nir.subtract.divide`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_010

- Categories: index_mask, sampling_regional_statistics, ml_classification, evaluation_vector_aggregation
- Added operators: `imgcollection.select > imgcollection.select.filterbounds > image.neq > image.updatemask > zerofilter.clip > handtile.gt > image.updatemask > image.normalizeddifference > image.normalizeddifference.rename > image.normalizeddifference > image.normalizeddifference.rename > image.select > image.select > image.expression > image.expression.rename > image.addbands > image.addbands.addbands > image.addbands.addbands.addbands > imagestack.first > image.sampleregions`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_012

- Categories: index_mask, sampling_regional_statistics
- Added operators: `ee.geometry.point > date_end.difference > date_end.difference.round > ee.number.subtract > ee.list.sequence > date_start.advance > ee.date.advance > ee.daterange > ee.imagecollection.filterdate > ee.filter.listcontains > ee.imagecollection.filterdate.filter > ee.filter.eq > ee.imagecollection.filterdate.filter.filter > ee.imagecollection.filterdate.filter.filter.filterbounds > ee.imagecollection.filterdate.filter.filter.filterbounds.select > s1.size > s1.median > s1.median.set > s1.median.set.set > s1.median.set.set.clip`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback, unbound_identifier`

### gee_raster_core_review_014

- Categories: sampling_regional_statistics
- Added operators: `img_base.bandnames > img_fus.bandnames > img_base.subtract > img_base.subtract > img_base.subtract.multiply > ee.reducer.sum > ndvi_sub2.reduceregion > ndvi_sub2.reduceregion.values > ndvi_sub2.reduceregion.values.get > ee.reducer.count > img_base.reduceregion > img_base.reduceregion.values > img_base.reduceregion.values.get > ee.number.divide > ee.number.divide.sqrt`
- Quality flags: `untyped_receiver`

### gee_raster_core_review_018

- Categories: index_mask, sampling_regional_statistics, evaluation_vector_aggregation
- Added operators: `sa.geometry > image.filterdate > data.clip > data.clip.copyproperties > preci.select > ee.reducer.mean > ee.reducer.mean.setoutputs > image.reduceregions > image.id > feature.set > rainfall.map.flatten > table.distinct > ee.join.saveall > ee.filter.equals > ee.join.saveall.apply > row.get > feature.get > feature.get > row.select > values.flatten`
- Quality flags: `untyped_receiver, callback, function_callback`

### gee_raster_core_review_020

- Categories: index_mask, sampling_regional_statistics, evaluation_vector_aggregation
- Added operators: `ee.geometry.polygon > l8.filterbounds > l8.filterbounds.filterdate > l8.filterbounds.filterdate.sort > l8_filter.first > image.select > image.select.multiply > image.select.multiply.add > image.select > image.select.multiply > image.select.multiply.add > image.addbands > image.addbands.addbands > l8_scalling.select > l8_scalling.select > l8_scalling.expression > ndbi.gt > ndbi_bangunan.reducetovectors > fc.get > ee.number.eq`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_021

- Categories: index_mask
- Added operators: `ee.filter.listcontains > ee.filter.listcontains > ee.imagecollection.filter.filter > ee.filter.eq > ee.imagecollection.filter.filter.filter > ee.imagecollection.filter.filter.filter.filterbounds > ee.imagecollection.filter.filter.filter.filterbounds.filterdate > ee.imagecollection.filter.filter.filter.filterbounds.filterdate.map.min > ee.imagecollection.filter.filter.filter.filterbounds.filterdate.map.min.select > s1_grd.clip`
- Quality flags: `untyped_receiver`

### gee_raster_core_review_022

- Categories: index_mask
- Added operators: `ee.geometry.polygon > a500.toarrayperband > q250.select > q250.select.toarrayperband > image.arrayslice > image.arrayslice > right.subtract > image.arrayslice > image.arrayslice > right.subtract > q250.size > ee.list.sequence > ee.image.constant > ndvis.arraylength > indexes.arrayslice > diffdoys.multiply > diffndvis.abs > diffndvis.abs.lt > diffndvis.abs > diffndvis.abs.lt`
- Quality flags: `untyped_receiver, callback, function_callback`

### gee_raster_core_review_026

- Categories: index_mask, ml_classification, evaluation_vector_aggregation
- Added operators: `image.select > qa.bitwiseand > qa.bitwiseand > qa.bitwiseand.and > qa.bitwiseand > qa.bitwiseand.and.or > image.mask > ee.reducer.min > image.mask.reduce > cloud.not > image.updatemask > image.updatemask.updatemask > image.updatemask.updatemask.divide > lc_inegi.select > dataset.select > dataset.select.median > dataset.select.median.clip > lc2.clip > image.normalizeddifference > image.normalizeddifference.rename`
- Quality flags: `callback, function_callback, named_callback, untyped_receiver`

### gee_raster_core_review_027

- Categories: sampling_regional_statistics
- Added operators: `ee.imagecollection.filter.filterbounds > ee.imagecollection.filter.filterbounds.filtermetadata > ee.imagecollection.filter.filterbounds.filtermetadata.map.select > collection.median > ee.image.tofloat.clip > imnormfunction.imnormalize > ee.reducer.minmax > indus.geometry > composite.reduceregion > composite.bandnames > composite.select > name.cat > minmax.get > name.cat > minmax.get > band.unitscale > ee.imagecollection.fromimages > ee.imagecollection.fromimages.tobands > composite.bandnames > ee.imagecollection.fromimages.tobands.rename`
- Quality flags: `unbound_identifier, untyped_receiver, callback, function_callback`

### gee_raster_core_review_029

- Categories: index_mask, sampling_regional_statistics, ml_classification
- Added operators: `finish.difference > days.subtract > ee.list.sequence > start.advance > daystart.advance > ee.filter.eq > ee.imagecollection.filtermetadata.filter > ee.imagecollection.filtermetadata.filter.filterdate > ee.imagecollection.filtermetadata.filter.filterdate.filterbounds > ee.imagecollection.filtermetadata.filter.filterdate.filterbounds.median > composite.bandnames > composite.bandnames.size > composite.bandnames.size.eq > composite.set > daystart.millis > composite.set.set > ee.imagecollection.filtermetadata > allimagesinranges1.filterdate > allimagesinranges1.filterdate.first > allimagesinranges1.filterdate.first.clip`
- Quality flags: `untyped_receiver, callback, function_callback`

### gee_raster_core_review_030

- Categories: index_mask, sampling_regional_statistics
- Added operators: `ee.imagecollection.filterbounds.filterdate > image.select > image.select > red.add > nir.divide > nir.divide.multiply > fapar.rename > ee.reducer.sum > s2_fapar.reduce > img.normalizeddifference > img.normalizeddifference.rename > s2.map.max > img.normalizeddifference > img.normalizeddifference.rename > s2.map.max > image.select > image.select > red.add > nir.divide > nir.divide.multiply`
- Quality flags: `callback, function_callback, named_callback, untyped_receiver`

### gee_raster_core_review_031

- Categories: index_mask, sampling_regional_statistics
- Added operators: `ee.data.setdefaultworkloadtag > ee.list.sequence > ee.string.cat > ee.string.cat.cat > ee.number.int > ee.string.cat.cat.cat > ee.string.cat.cat.cat.cat > ee.image.loadgeotiff > ee.number.int > ee.string.cat > ee.number.int > ee.string.cat > ee.number.int > ee.string.cat > ee.number.int > ee.string.cat > ee.number.int > ee.string.cat > ee.image.loadgeotiff.select > ee.imagecollection.tobands.select`
- Quality flags: `callback, function_callback, untyped_receiver`

### gee_raster_core_review_033

- Categories: index_mask
- Added operators: `ee.date.fromymd > st_date.advance > l8.filterdate > imagecollection.select > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand.eq.and > imagecollection.updatemask > l8.filterdate.map.sort > image.clip > image.normalizeddifference > image.normalizeddifference.rename > image.addbands > img.select > img.select.visualize > rgbvis.getvideothumburl > l8.filterdate > imagecollection.select`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_034

- Categories: index_mask
- Added operators: `lai_global_2003_1500_unseason_g_d_erci_unmask_greenup_lt_dormancy.gte > mcd12q2_2003_full.updatemask > image.select > image.select > image.select > image.select.gte > image.date > image.date.difference > ee.image.constant > ee.image.constant.subtract > ee.image.constant.subtract.int > image.date > image.date.difference > ee.image.int > ee.image.int.rename > pheno.subtract > pheno.subtract.updatemask > pheno.subtract.updatemask.toint > time.addbands > time.addbands.copyproperties`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_035

- Categories: evaluation_vector_aggregation
- Added operators: `ee.imagecollection.filterdate.filterbounds > ee.imagecollection.filterdate.filterbounds.select > image.clip > image.divide > image.add > image.multiply > image.multiply.add > image.add.divide > image.add.divide.rename > image.divide.addbands > ee.list.sequence > ee.list.sequence > ee.filter.calendarrange > d16ndvi.filter > ee.filter.calendarrange > d16ndvi.filter.filter > d16ndvi.filter.filter.mean > d16ndvi.filter.filter.mean.set > d16ndvi.filter.filter.mean.set.set > ee.date.fromymd`
- Quality flags: `callback, function_callback, named_callback, untyped_receiver`

### gee_raster_core_review_038

- Categories: index_mask
- Added operators: `ee.filter.eq > ee.filter.listcontains > ee.imagecollection.filter.filter > ee.filter.eq > ee.imagecollection.filter.filter.filter > ee.imagecollection.filter.filter.filter.filtermetadata > ee.imagecollection.filter.filter.filter.filtermetadata.filterbounds > ee.imagecollection.filter.filter.filter.filtermetadata.filterbounds.select > ee.filter.eq > ee.filter.listcontains > ee.imagecollection.filter.filter > ee.filter.eq > ee.imagecollection.filter.filter.filter > ee.imagecollection.filter.filter.filter.filtermetadata > ee.imagecollection.filter.filter.filter.filtermetadata.filterbounds > ee.imagecollection.filter.filter.filter.filtermetadata.filterbounds.select > collectionhh.filterdate > collectionhh.filterdate > collectionhv.filterdate > collectionhv.filterdate`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_042

- Categories: index_mask
- Added operators: `sug.select > sug.select.gt > sug.select > sug.select.lt > sug.select.gt.and > sug.select > sug.select.gt > sug.select > sug.select.lt > sug.select.gt.and > sug.select > sug.select.gt > sug.select > sug.select.lt > sug.select.gt.and > sug.select > sug.select.gt > sug.select > sug.select.lt > sug.select.gt.and`
- Quality flags: `untyped_receiver`

### gee_raster_core_review_044

- Categories: index_mask, sampling_regional_statistics, evaluation_vector_aggregation
- Added operators: `glacierimages.mosaic > glacierimages.mosaic.unmask > glacierimages.mosaic.unmask.reproject > elvalgaemask.unmask > elvalgaemask.unmask.rename > elvalgaemask.unmask.rename.set > elvalgaemask.not > elvalgaemask.not.unmask > elvalgaemask.not.unmask.rename > elvalgaemask.not.unmask.rename.set > hialgaemask.or > hialgaemask.or.rename > hialgaemask.or.rename.set > ee.filter.inlist > regions.filter > ee.filter.calendarrange > terraday.filter > i.date > i.date.getrelative > i.date.getrelative.toint`
- Quality flags: `unbound_identifier, untyped_receiver, callback, function_callback`

### gee_raster_core_review_045

- Categories: index_mask, sampling_regional_statistics, evaluation_vector_aggregation
- Added operators: `featurecollection.aggregate_array > ee.list.distinct > ee.filter.eq > featurecollection.filter > tempfc.union > unionfc.first > ee.feature.set > meso_regions.geometry > meso_regions.geometry.dissolve > ee.reducer.sum > testareaimage.reduceregion > reducer.get > ee.number.multiply > ee.number.multiply.multiply > ee.number.multiply.multiply.divide > area.getinfo > ee.image.pixelarea.divide > ee.reducer.sum > img.reduceregion > area2.get`
- Quality flags: `untyped_receiver, callback, function_callback`

### gee_raster_core_review_046

- Categories: index_mask, sampling_regional_statistics, ml_classification, evaluation_vector_aggregation
- Added operators: `maskwater.select > maskwater.select.eq > enddate.difference > ee.list.sequence > ee.geometry.point > ee.geometry.point > ee.geometry.rectangle > basin.geometry > basin.geometry.area > imagen.select > imagen.select > imagen.select.gt > imagen.select > imagen.select.gt > imagen.select.gt.and > quality.bitwiseand > quality.bitwiseand.eq > imagen.select.gt.and.and > quality.bitwiseand > quality.bitwiseand.eq`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

### gee_raster_core_review_047

- Categories: index_mask
- Added operators: `image.select > image.select > image.select.bitwiseand > image.select.bitwiseand.rightshift > getqabits.expression > image.select > image.select.bitwiseand > image.select.bitwiseand.rightshift > getqabits.expression > image.select > image.select.bitwiseand > image.select.bitwiseand.rightshift > getqabits.expression > image.select > image.select.bitwiseand > image.select.bitwiseand.rightshift > getqabits.expression > landwaterflag.eq > cloud.not > landwaterflag.eq.and`
- Quality flags: `untyped_receiver, loop_order_unresolved, native_js_call`

### gee_raster_core_review_049

- Categories: sampling_regional_statistics
- Added operators: `l8.filterbounds > spatialfiltered.filterdate > temporalfiltered.sort > sorted.first > image.get > image.get > image.select > image.get > qcal.multiply > qcal.multiply.add > image.get > image.get > k1.divide > k1.divide.add > k1.divide.add.log > k2.divide > k2.divide.subtract > image.select > image.select > image.select.subtract`
- Quality flags: `untyped_receiver`

### gee_raster_core_review_050

- Categories: index_mask, sampling_regional_statistics, ml_classification, evaluation_vector_aggregation
- Added operators: `ee.filter.lt > s2.filterdate > s2.filterdate.filterbounds > s2.filterdate > s2.filterdate.filterbounds > s2.filterdate > s2.filterdate.filterbounds > s2.filterdate > s2.filterdate.filterbounds > ee.number.pow > ee.number.pow.int > ee.number.pow > ee.number.pow.int > image.select > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand > qa.bitwiseand.eq > qa.bitwiseand.eq.and > image.updatemask`
- Quality flags: `untyped_receiver, callback, function_callback, named_callback`

## Guardrail

`p4_rereview_candidate=true` only means the deterministic extractor now
recovers additional source-grounded core calls. It does not mean the row is
complete, task-text faithful, mapped to L3, or eligible for train/val/test.
