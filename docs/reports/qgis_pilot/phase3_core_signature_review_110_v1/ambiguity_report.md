# QGIS Core Signature Ambiguity Report

Unresolved review rows: 60 of 121.

| Record | Class | Status | Reason | Top candidate IDs |
| --- | --- | --- | --- | --- |
| script_56299 | Buffer | unresolved_provider_conflict | exact_matches_conflict_with_provider_evidence | native:buffer, gdal:buffervectors, gdal:onesidebuffer, grass7:v.buffer, native:bufferbym |
| script_56301 | ClipRasterByMask | unresolved_no_exact_match | no_exact_class_match | gdal:cliprasterbymasklayer, gdal:cliprasterbyextent, native:clip, gdal:clipvectorbypolygon, gdal:warpreproject |
| script_56303 | ClipVectorByMask | unresolved_no_exact_match | no_exact_class_match | gdal:clipvectorbypolygon, native:clip, gdal:cliprasterbymasklayer, gdal:clipvectorbyextent, gdal:cliprasterbyextent |
| script_56305 | CreateCloudOptimizedGeoTIFF | unresolved_no_exact_match | no_exact_class_match | saga:createtileshapefromvirtualpointcloud, saga:createvirtualpointclouddataset, saga:exportgeotiff, native:categorizeusingstyle, native:createattributeindex |
| script_56306 | DatasetIdentify | unresolved_no_exact_match | no_exact_class_match | native:detectvectorchanges, native:meshexportcrosssection, native:meshexporttimeseries, native:meshrasterize, saga:createvirtualpointclouddataset |
| script_56307 | Datasources2Vrt | unresolved_no_exact_match | no_exact_class_match | gdal:buildvirtualvector, qgis:executesql |
| script_56310 | GdalAlgorithm | unresolved_no_exact_match | no_exact_class_match | gdal:gdal2tiles, gdal:gdal2xyz, saga:gdalformats |
| script_56311 | GdalAlgorithmDialog | unresolved_no_exact_match | no_exact_class_match | gdal:gdal2tiles, gdal:gdal2xyz, saga:gdalformats, saga:variogramdialog |
| script_56311 | GdalParametersPanel | unresolved_no_exact_match | no_exact_class_match | gdal:gdal2tiles, gdal:gdal2xyz, saga:earthsorbitalparameters, saga:gdalformats |
| script_56312 | GdalAlgorithmProvider | unresolved_no_exact_match | no_exact_class_match | gdal:gdal2tiles, gdal:gdal2xyz, saga:gdalformats |
| script_56313 | GdalConnectionDetails | unresolved_no_exact_match | no_exact_class_match | gdal:gdal2tiles, gdal:gdal2xyz, gdal:importvectorintopostgisdatabasenewconnection, saga:gdalformats |
| script_56313 | GdalUtils | unresolved_no_exact_match | no_exact_class_match | gdal:gdal2tiles, gdal:gdal2xyz, saga:gdalformats |
| script_56321 | OgrToPostGis | unresolved_no_exact_match | no_exact_class_match | gdal:importvectorintopostgisdatabasenewconnection, gdal:importvectorintopostgisdatabaseavailableconnections, saga:importerdaslangis, gdal:aspect, gdal:buffervectors |
| script_56325 | buildvrt | unresolved_no_exact_match | no_exact_class_match | gdal:buildvirtualraster, gdal:merge, gdal:pansharp, gdal:cliprasterbymasklayer, gdal:overviews |
| script_56331 | gdaladdo | unresolved_no_exact_match | no_exact_class_match | gdal:overviews, gdal:warpreproject, gdal:aspect, gdal:buildvirtualraster, gdal:cliprasterbyextent |
| script_56332 | gdalcalc | unresolved_no_exact_match | no_exact_class_match | gdal:rastercalculator, gdal:fillnodata, gdal:rasterize, gdal:aspect, gdal:cliprasterbyextent |
| script_56334 | gdaltindex | unresolved_no_exact_match | no_exact_class_match | gdal:tileindex, gdal:buildvirtualraster, gdal:retile, grass7:r.sun.incidout, grass7:r.sun.insoltime |
| script_56338 | ogr2ogr | unresolved_no_exact_match | no_exact_class_match | gdal:convertformat, gdal:rearrange_bands, gdal:translate, otb:ComputeOGRLayersFeaturesStatistics, otb:OGRLayerClassifier |
| script_56339 | Ogr2OgrToPostGisList | unresolved_no_exact_match | no_exact_class_match | gdal:importvectorintopostgisdatabaseavailableconnections, gdal:importvectorintopostgisdatabasenewconnection, qgis:listuniquevalues, gdal:buffervectors, gdal:dissolve |
| script_56340 | ogrinfojson | unresolved_no_exact_match | no_exact_class_match | gdal:ogrinfo, grass7:r.info |
| script_56342 | pct2rgb | unresolved_no_exact_match | no_exact_class_match | gdal:pcttorgb, gdal:rgbtopct, saga:splitrgbbands, grass7:i.his.rgb, grass7:i.rgb.his |
| script_56350 | rgb2pct | unresolved_no_exact_match | no_exact_class_match | gdal:rgbtopct, gdal:pcttorgb, saga:splitrgbbands, grass7:i.his.rgb, grass7:i.rgb.his |
| script_56354 | tpi | unresolved_no_exact_match | no_exact_class_match | gdal:tpitopographicpositionindex, saga:topographicpositionindextpi, saga:tpibasedlandformclassification, saga:multiscaletopographicpositionindextpi, gdal:aspect |
| script_56356 | tri | unresolved_no_exact_match | no_exact_class_match | gdal:triterrainruggednessindex, gdal:griddatametrics, native:addfieldtoattributestable, native:createattributeindex, native:deleteduplicategeometries |
| script_56361 |  | unresolved_no_class_scope | no_class_scope_in_trace |  |
| script_56362 | EliminateSelection | unresolved_no_exact_match | no_exact_class_match | qgis:eliminateselectedpolygons, qgis:randomselection, qgis:randomselectionwithinsubsets, otb:SampleSelection, saga:3dpointsselection |
| script_56363 | ParameterExecuteSql | unresolved_no_exact_match | no_exact_class_match | gdal:executesql, qgis:executesql, native:postgisexecutesql, native:spatialiteexecutesql, native:spatialiteexecutesqlregistered |
| script_56364 | FieldsPyculator | unresolved_no_exact_match | no_exact_class_match | qgis:advancedpythonfieldcalculator, native:fieldcalculator, native:addxyfields, native:refactorfields, native:retainfields |
| script_56366 | HubDistanceLines | unresolved_no_exact_match | no_exact_class_match | qgis:distancetonearesthublinetohub, qgis:distancetonearesthubpoints, gdal:gridinversedistance, gdal:gridinversedistancenearestneighbor, gdal:pointsalonglines |
| script_56367 | HubDistancePoints | unresolved_no_exact_match | no_exact_class_match | qgis:distancetonearesthubpoints, qgis:distancetonearesthublinetohub, gdal:gridinversedistance, gdal:gridinversedistancenearestneighbor, gdal:pointsalonglines |
| script_56371 | MeanAndStdDevPlot | unresolved_no_exact_match | no_exact_class_match | qgis:meanandstandarddeviationplot, qgis:barplot, qgis:boxplot, qgis:polarplot, native:meancoordinates |
| script_56372 | PointDistance | unresolved_no_exact_match | no_exact_class_match | qgis:distancematrix, saga:pointtopointdistances, gdal:gridinversedistance, gdal:gridinversedistancenearestneighbor, grass7:r.distance |
| script_56374 | PointsFromLines | unresolved_no_exact_match | no_exact_class_match | saga:contourlinesfrompoints, gdal:pointsalonglines, native:meshexportcrosssection, native:meshexporttimeseries, qgis:generatepointspixelcentroidsalongline |
| script_56376 | QgisAlgorithm | unresolved_no_exact_match | no_exact_class_match |  |
| script_56376 | QgisFeatureBasedAlgorithm | unresolved_no_exact_match | no_exact_class_match | native:convertgpxfeaturetype, native:filter, otb:GridBasedImageResampling, saga:imcorrfeaturetracking, saga:lapseratebasedtemperaturedownscaling |
| script_56377 | QgisAlgorithmProvider | unresolved_no_exact_match | no_exact_class_match |  |
| script_56378 | RandomPointsAlongLines | unresolved_no_exact_match | no_exact_class_match | qgis:randompointsalongline, gdal:pointsalonglines, native:pointsalonglines, native:randompointsonlines, qgis:randompointsinlayerbounds |
| script_56379 | RandomPointsLayer | unresolved_no_exact_match | no_exact_class_match | qgis:randompointsinlayerbounds, qgis:randompointsalongline, qgis:randompointsinsidepolygons, native:randompointsinextent, native:randompointsinpolygons |
| script_56380 | RandomPointsPolygons | unresolved_no_exact_match | no_exact_class_match | qgis:randompointsinsidepolygons, native:randompointsinpolygons, qgis:randompointsalongline, qgis:randompointsinlayerbounds, native:randompointsinextent |
| script_56381 | RasterCalculator | unresolved_provider_evidence_ambiguous | multiple_provider_groups_in_evidence | qgis:rastercalculator, gdal:rastercalculator, saga:rastercalculator, saga:coordinatetransformationraster, saga:coordinatetransformationrasterlist |
| script_56385 | ParameterReliefColors | unresolved_no_exact_match | no_exact_class_match | grass7:r.relief, qgis:relief, gdal:colorrelief, grass7:i.colors.enhance, grass7:r.colors |
| script_56386 | SetRasterStyle | unresolved_no_exact_match | no_exact_class_match | qgis:setstyleforrasterlayer, native:setlayerstyle, native:setmfromraster, qgis:setstyleforvectorlayer, native:cellstackpercentrankfromrasterlayer |
| script_56387 | SetVectorStyle | unresolved_no_exact_match | no_exact_class_match | qgis:setstyleforvectorlayer, native:setlayerstyle, qgis:setstyleforrasterlayer, otb:VectorDataSetField, gdal:buildvirtualvector |
| script_56391 | ColoringAlgorithm | unresolved_no_exact_match | no_exact_class_match | qgis:topologicalcoloring |
| script_56391 | Graph | unresolved_no_exact_match | no_exact_class_match | gdal:tpitopographicpositionindex, saga:directgeoreferencingofairbornephotographs, saga:exportscalablevectorgraphicssvgfile, saga:geographiccoordinaterasters, saga:geographicdistances |
| script_56391 | TopoColor | unresolved_no_exact_match | no_exact_class_match | qgis:topologicalcoloring, gdal:colorrelief, grass7:i.topo.coor.ill, grass7:i.topo.corr, grass7:r.what.color |
| script_56396 | Processing | unresolved_no_exact_match | no_exact_class_match | saga:changeagridsnodatavaluebulkprocessing, saga:lapseratebasedtemperaturedownscalingbulkprocessing |
| script_56397 | ProcessingConfig | unresolved_no_exact_match | no_exact_class_match | saga:changeagridsnodatavaluebulkprocessing, saga:lapseratebasedtemperaturedownscalingbulkprocessing |
| script_56397 | Setting | unresolved_no_exact_match | no_exact_class_match | saga:worldfilefromflightandcamerasettings |
| script_56397 | SettingsWatcher | unresolved_no_exact_match | no_exact_class_match | saga:worldfilefromflightandcamerasettings |
| script_56398 |  | unresolved_no_class_scope | no_class_scope_in_trace |  |
| script_56399 |  | unresolved_no_class_scope | no_class_scope_in_trace |  |
| script_56400 | AddScriptFromFileAction | unresolved_no_exact_match | no_exact_class_match | saga:worldfilefromflightandcamerasettings, native:addautoincrementalfield, native:addfieldtoattributestable, native:adduniquevalueindexfield, native:addxyfields |
| script_56401 | DeleteScriptAction | unresolved_no_exact_match | no_exact_class_match | native:deleteduplicategeometries, native:deleteholes, native:removeduplicatesbyattribute, saga:deleteselectionfromfeatureslayer, saga:selectanddelete |
| script_56402 | EditScriptAction | unresolved_no_exact_match | no_exact_class_match | grass7:v.edit |
| script_56403 | OpenScriptFromFileAction | unresolved_no_exact_match | no_exact_class_match | saga:worldfilefromflightandcamerasettings, native:atlaslayouttopdf, native:categorizeusingstyle, native:cellstackpercentrankfromrasterlayer, native:cellstackpercentrankfromvalue |
| script_56404 | ScriptAlgorithmProvider | unresolved_no_exact_match | no_exact_class_match |  |
| script_56405 | ScriptEditorDialog | unresolved_no_exact_match | no_exact_class_match | saga:variogramdialog |
| script_56406 | ExampleProcessingAlgorithm | unresolved_no_exact_match | no_exact_class_match | saga:changeagridsnodatavaluebulkprocessing, saga:lapseratebasedtemperaturedownscalingbulkprocessing |
| script_56407 |  | unresolved_no_class_scope | no_class_scope_in_trace |  |
