# --------------------------------------------------------
# Create Dubai + Abu Dhabi AOI GeoJSON from given polygon
# Run this in the QGIS Python Console
# --------------------------------------------------------

""" How to run
	1.	Open QGIS.
	2.	Plugins → Python Console.
	3.	Click “Show Editor”, paste this whole script.
	4.	Adjust output_path if needed.
	5.	Click Run. """
 
from qgis.core import (
    QgsVectorLayer,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsProject
)
from PyQt5.QtCore import QVariant

# 1. Define CRS (WGS84)
crs = QgsCoordinateReferenceSystem("EPSG:4326")

# 2. Create an in-memory polygon layer
layer = QgsVectorLayer(
    "Polygon?crs=epsg:4326",
    "Dubai_AbuDhabi_AOI",
    "memory"
)

provider = layer.dataProvider()

# 3. Add attributes
fields = QgsFields()
fields.append(QgsField("id", QVariant.Int))
fields.append(QgsField("name", QVariant.String))
provider.addAttributes(fields)
layer.updateFields()

# 4. Define your AOI polygon coordinates (lon, lat)
coords = [
    (51.00, 24.10),
    (51.80, 24.60),
    (54.20, 25.75),
    (55.70, 25.75),
    (56.10, 24.50),
    (55.40, 23.70),
    (54.00, 23.30),
    (52.30, 23.40),
    (51.00, 24.10)  # closing the polygon
]

points = [QgsPointXY(x, y) for (x, y) in coords]

geom = QgsGeometry.fromPolygonXY([points])

# 5. Create the feature
feat = QgsFeature()
feat.setFields(fields)
feat.setGeometry(geom)
feat["id"] = 1
feat["name"] = "Dubai_AbuDhabi_AOI"

provider.addFeatures([feat])
layer.updateExtents()

# 6. Add to current QGIS project (for visualization)
QgsProject.instance().addMapLayer(layer)

# 7. Save to GeoJSON
# Use your project folder; QGIS prefers absolute paths.
# If your QGIS project is in the repo root, this relative-like path will make sense.
output_path = "data/aoi/Dubai_AbuDhabi_AOI.geojson"

# If needed, you can also make it absolute, e.g.:
# output_path = "/Users/yourname/GlobeHolder/data/aoi/Dubai_AbuDhabi_AOI.geojson"

error = QgsVectorFileWriter.writeAsVectorFormat(
    layer,
    output_path,
    "UTF-8",
    crs,
    "GeoJSON"
)

if error == QgsVectorFileWriter.NoError:
    print(f"✅ GeoJSON successfully written to: {output_path}")
else:
    print(f"❌ Error writing GeoJSON (code: {error})")