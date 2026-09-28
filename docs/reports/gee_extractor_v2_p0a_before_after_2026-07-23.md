# GEE Extractor v2 P0-A Before/After

- Scope: variable-bound and static object-property function bindings.
- Before: gee-source-extractor-v2.0.0.
- After: gee-source-extractor-v2.0.1.
- Records: 6.
- Training admission: not_granted.

| Source | Calls before/after | Core before/after | I/O before/after | Presentation before/after | Recovered core |
| --- | ---: | ---: | ---: | ---: | --- |
| script_4142.txt | 19/19 | 8/8 | 0/0 | 8/8 | - |
| script_179599.txt | 92/127 | 57/83 | 2/2 | 15/15 | feature.get, feature.get, feature.get, table.distinct, ee.Join.saveAll, ee.Filter.equals, ee.Join.saveAll.apply, row.get, row.select, values.flatten, row.select.set, feature.toDictionary, feature.toDictionary, feature.toDictionary.keys, feature.toDictionary.keys.remove, ee.String.slice, substrKeys.distinct, ee.Filter.stringContains, allKeys.filter, feature.toDictionary.select, feature.toDictionary.select.values, ee.Reducer.max, matches.reduce, feature.select, pairs.flatten, feature.select.set |
| script_203101.txt | 75/89 | 60/74 | 1/1 | 0/0 | s2Image.normalizedDifference, s2Image.normalizedDifference.toFloat, s2Image.select, nbr.addBands, nbr.addBands.select, nbr.addBands.select.copyProperties, image.select, qa.bitwiseAnd, qa.bitwiseAnd, qa.bitwiseAnd.eq, qa.bitwiseAnd.eq, qa.bitwiseAnd.eq.and, image.updateMask, image.updateMask.copyProperties |
| script_210697.txt | 122/161 | 74/110 | 0/0 | 4/4 | ee.Image.neq, ee.Image.subtract, ee.Image.subtract, ee.Image.subtract.clamp, ee.Image.neq.multiply, ee.Image.neq.multiply.int, ee.Image.date, ee.Image.date, ee.Image.date.difference, ee.Image.subtract.divide, ee.Image.subtract.divide.rename, ee.Image.subtract.divide.rename.float, array.arrayLength, ee.Image.arrayRepeat, ee.Reducer.sum, ee.Image.arrayRepeat.arrayAccum, ee.Image.arrayRepeat.arrayAccum.toArray, array.arraySort, sorted.arraySlice, sorted.arraySlice, left.neq, left.neq.arrayCat, indices.arrayMask, runIndices.arraySlice, runIndices.arraySlice, runIndices.arraySlice.subtract, img.subtract, img.subtract, img.multiply, img.multiply, img.multiply, img.multiply, img.multiply.add, img.multiply.add, img.multiply.multiply, img.multiply.multiply |
| script_217558.txt | 53/53 | 34/34 | 0/0 | 7/7 | - |
| script_48309.txt | 91/122 | 67/97 | 0/0 | 6/6 | image.select, image.select, image.select.subtract, image.select.subtract.pow, image.select.subtract.pow.select, ee.Number.multiply, D2.divide, D2.divide.exp, ee.Image.constant, ee.Image.constant, ee.Image.constant.subtract, ee.Image.constant.add, ee.Image.constant.subtract.divide, ee.Image.constant.subtract.divide.select, image.addBands, ee.Reducer.mean, ee.Reducer.mean, ee.Reducer.mean, ee.Image.reproject, ee.Image.reproject, ee.Image.reproject, cmg.projection, cmg.projection, cmg.projection, image.reduceResolution, image.reduceResolution, image.reduceResolution, image.reduceResolution.reproject, image.reduceResolution.reproject, image.reduceResolution.reproject |

Diagnostic evidence only; this does not populate human review fields or authorize training data.
