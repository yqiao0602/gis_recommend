from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLineEdit,   QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QTextEdit
from qgis.gui import QgsMapLayerComboBox, QgsExtentWidget
from qgis.core import QgsMapLayerProxyModel, QgsCoordinateReferenceSystem

import urllib.request
from io import BytesIO
import zipfile
from qgis.core import *
from pathlib import Path
import os
import re
import tempfile
import shutil

plugin_path = Path(__file__).resolve().parent.parent

class Ui_geol_DL(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Geol BRGM 1/50000")

        # lien de dl brgm
        base_url = "https://data.cquest.org/brgm/bd_charm_50/2019/"

        # fetch page content
        with urllib.request.urlopen(base_url) as response:
            html = response.read().decode("utf-8")

        pattern = r'href="([^"]+\.(?:zip|txt))"'
        links = re.findall(pattern, html, re.IGNORECASE)
        self.links = [base_url + link for link in links]
        
        self.departement_shp_p = os.path.join( plugin_path, "data_utils/limite_dep/departement.shp" )
        # print(os.path.exists(self.departement_shp_p))
        # Layout
        self.layout = QVBoxLayout(self)

        # extent
        self.extent_widget = QgsExtentWidget(self)
        self.extent_widget.setMapCanvas(self.iface.mapCanvas())
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
       
        default_extent = iface.mapCanvas().extent()
        self.extent_widget.setOriginalExtent( default_extent, iface.mapCanvas().mapSettings().destinationCrs() )
        self.extent_widget.setOutputCrs( target_crs )

        self.add_line('Extent', self.extent_widget)

        self.zone_calcul = QgsMapLayerComboBox()
        self.zone_calcul.setShowCrs(True)
        self.zone_calcul.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.zone_calcul.setAllowEmptyLayer(True) 
        self.zone_calcul.setCurrentIndex(-1)

        self.add_line('Zone de découpe [optionnel]', self.zone_calcul)

        self.add_save_option()

        self.add_line( '' )
        self.add_line( '>>> Log' )
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.layout.addWidget(self.log_text)


        self.create_footer_buttons()

        self.setLayout(self.layout)


    
    def add_save_option(self):
        # Path selection button and line edit
        save_layout = QVBoxLayout()

        self.save_path_edit = QLineEdit()
        self.save_path_edit.setPlaceholderText('path')
        self.save_path_button = QPushButton('...')
        self.save_path_button.clicked.connect(self.select_save_path)

        save_layout.addWidget(QLabel('Chemin de sauvegarde'))
        row_layout_bis = QHBoxLayout()
        row_layout_bis.addWidget(self.save_path_edit)
        row_layout_bis.addWidget(self.save_path_button)
        save_layout.addLayout(row_layout_bis)

        self.layout.addLayout(save_layout)

    def select_save_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", "")
        if folder:
            self.save_path_edit.setText(folder)


    def add_line(self, label=None, default_data=None):
        row_layout = QHBoxLayout()
        if label is not None:
            label_q = QLabel(label)
            row_layout.addWidget(label_q)
        if default_data is not None:
            row_layout.addWidget(default_data)
        self.layout.addLayout(row_layout)
        
    def create_footer_buttons(self):
        button_layout = QHBoxLayout()
        ok_button = QPushButton('OK')
        cancel_button = QPushButton('Cancel')
        # ok_button.clicked.connect( lambda: call_inference({'config': self.config_manager.current_config}))
        ok_button.clicked.connect( self.on_ok_button_clicked )
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)

    def on_ok_button_clicked(self):
        save_path = self.save_path_edit.text()
        if not save_path:
            QMessageBox.warning(self, "Nope !", "Chemin de sauvegarde manquant")
            return
        
        extent = self.extent_widget.outputExtent()
        aoi_layer = self.zone_calcul.currentLayer()
        # print(aoi_layer, aoi_layer is None)

        if aoi_layer is not None:
            extent = aoi_layer.extent()
        
        dep = QgsVectorLayer(self.departement_shp_p, "departements", "ogr")

        # Reproject extent to dep CRS
        extent_geom = QgsGeometry.fromRect(extent)
        transform = QgsCoordinateTransform(self.extent_widget.outputCrs() if aoi_layer is None else aoi_layer.crs(), dep.crs(), QgsProject.instance())
        extent_geom.transform(transform)

        # Filter and collect intersecting features
        request = QgsFeatureRequest().setFilterRect(extent_geom.boundingBox())
        # print(extent_geom.boundingBox())
        intersecting_features = [
            f for f in dep.getFeatures(request) if f.geometry().intersects(extent_geom)
        ]

        # print( list(intersecting_features[0].fields()))
        
        code_insee = [f['code_insee'] for f in intersecting_features]
        # print(code_insee)
        # print('LAAAAAAAA')


        if aoi_layer is None:
            cut_geom = extent_geom
            cut_geom_crs = dep.crs()
        else:
            cut_geom = [f.geometry() for f in aoi_layer.getFeatures()]
            cut_geom = QgsGeometry.unaryUnion( cut_geom ) # in case of multiple areas
            cut_geom_crs = aoi_layer.crs()

        self.worker = DownloadWorker( self.links, code_insee, cut_geom, cut_geom_crs, save_path)
        
        self.worker.log_signal.connect(self.log_text.append)

        self.worker.start()

        # self.log_text.append( f'--------------------------')

        

from PyQt5.QtCore import QThread, pyqtSignal
import traceback
import requests
import xml.etree.ElementTree as ET

class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)

    def __init__(self, dl_url, code_insee, cut_geom, cut_geom_crs, save_path):
        super().__init__()
        self.dl_url = dl_url
        self.code_insee = code_insee
        self.cut_geom = cut_geom
        self.cut_geom_crs = cut_geom_crs
        self.save_path = save_path

        # the files that have been DL by thematic
        # in it we will store the features that will be saved
        self.keep_features = {
            'L_DIVERS':[],
            'L_FGEOL':[],
            'L_STRUCT':[],
            'P_DIVERS':[],
            'P_STRUCT':[],
            'S_FGEOL':[],
            'S_SURCH':[]
        }
        # qml files
        self.keep_style = {
            'L_DIVERS':[],
            'L_FGEOL':[],
            'L_STRUCT':[],
            'P_DIVERS':[],
            'P_STRUCT':[],
            'S_FGEOL':[],
            'S_SURCH':[]
        }

    def run(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            # tmpdir =r'C:\Users\Alex_Styx\Documents\workdir\projet\2025 - Qgis Styx Plugin\test\temp'
            # tmpdir : temp dir that will be erase when run() finish
            try:
                self.log_signal.emit('Début du téléchargement\n')

                for ci in self.code_insee:
                    self.log_signal.emit(f">> téléchargement de {ci}\n")

                    for link in self.dl_url:
                        if ci in link:
                            url = link
                            break

                    extracted_path = self.download_and_extract( url, tmpdir )
                    # extracted_path = [os.path.join(tmpdir, ftemp) for ftemp in os.listdir(tmpdir) if ci in ftemp]

                    for f in extracted_path:
                        fname = os.path.basename(f)

                        if '.shp' in fname:
                            for key in self.keep_features.keys():
                                if key in fname:

                                    layer = QgsVectorLayer( f, 'lay', "ogr")

                                    self.cut_geom, self.cut_geom_crs = self.repoj_cut_geom( self.cut_geom, self.cut_geom_crs, layer.crs())

                                    intersects_features = self.make_intersection( layer, self.cut_geom )
                                    self.keep_features[key].extend( intersects_features )
                                    self.keep_style[key].append( f.replace('.shp','.qml'))


                                    self.log_signal.emit(f"{key}>> decoupe de {len(intersects_features)}\n")
                                    break 

                # save
                prefix = 'GEO050K_HARM_' + '_'.join(self.code_insee)

                for k in self.keep_features.keys():
                    save_p_layer = os.path.join( self.save_path, prefix ) + '_' + k + '.shp'
                    save_p_layer_style = os.path.join( self.save_path, prefix ) + '_' + k + '.qml'

                    #♦ save style
                    if not os.path.exists( save_p_layer_style ):
                        # avoir multiple rewrite as we only need 1
                        # pass
                        style_p = None
                        for p_ in self.keep_style[k]:
                            if os.path.exists(p_):
                                style_p = p_
                                break
                        if style_p is not None:
                            shutil.copy( style_p, save_p_layer_style )
                    
                    self.write_p_layer( self.keep_features[k], save_p_layer, self.cut_geom_crs)
                    QgsProject.instance().addMapLayer( QgsVectorLayer(save_p_layer, f"geol{k}", "ogr") )




            except Exception:
                err = traceback.format_exc()
                self.log_signal.emit(f"[ERROR]\n{err}")
        
        self.log_signal.emit(" Done ! ")

    
    def write_p_layer(self, features, save_path, crs):

        # self.log_signal.emit(f"> ON WRITE \n")
        if not features:
            return False  # nothing to save

        # Determine geometry type from first feature
        geom_type_map = {
            0: "Point",
            1: "LineString",
            2: "Polygon"
        }

        geom_type_qgis = features[0].geometry().type()
        geom_type_str = geom_type_map.get(geom_type_qgis, "Unknown")
        qgis_geom_type = geom_type_str
        self.log_signal.emit(f"> save_path {save_path} \n")
        self.log_signal.emit(f"> qgis_geom_type {qgis_geom_type} \n")

        # Create memory layer
        mem_layer = QgsVectorLayer(f"{qgis_geom_type}?crs={crs.authid()}", "temp", "memory")
        # self.log_signal.emit(f"> layer {mem_layer.is_valid()} \n")
        pr = mem_layer.dataProvider()

        # Copy fields from first feature
        if features[0].fields().count():
            pr.addAttributes(features[0].fields())
            mem_layer.updateFields()

        # for f_list in features:
        pr.addFeatures(features)
        mem_layer.updateExtents()

        # Save to shapefile
        error = QgsVectorFileWriter.writeAsVectorFormat(
            mem_layer,
            save_path,
            "UTF-8",
            crs,
            "ESRI Shapefile"
        )
        return error == QgsVectorFileWriter.NoError

    def repoj_cut_geom(self, geom, input_crs, output_crs):
        transform = QgsCoordinateTransform(input_crs, output_crs, QgsProject.instance())
        geom.transform(transform)
        return geom, output_crs

    def make_intersection(self, layer, geom_c):
        intersecting_features = []
        for f in layer.getFeatures():
            geom = f.geometry()
            if geom.intersects(geom_c):
                new_f = QgsFeature(f)
                new_f.setGeometry(geom.intersection(geom_c))
                intersecting_features.append(new_f)
        return intersecting_features
        
    def download_and_extract(self, url, save_path):
        with urllib.request.urlopen(url) as response:
            data = response.read()

        extracted_files = []

        with BytesIO(data) as zipdata:
            with zipfile.ZipFile(zipdata) as z:
                for name in z.namelist():
                    dest = os.path.join(save_path, name)
                    extracted_files.append(dest)
                z.extractall(save_path)

        return extracted_files
    