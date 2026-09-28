def write_transformed_feature(feature, sink, use_buffer):
    geometry = feature.geometry()
    if use_buffer:
        transformed = geometry.buffer(10, 8)
    else:
        transformed = geometry.centroid()
    feature.setGeometry(transformed)
    sink.addFeature(feature)
