def write_buffered_feature(feature, sink):
    geometry = feature.geometry()
    buffered = geometry.buffer(10, 8)
    feature.setGeometry(buffered)
    sink.addFeature(feature)
