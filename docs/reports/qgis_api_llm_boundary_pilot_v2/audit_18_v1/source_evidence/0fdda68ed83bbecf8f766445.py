# Source repo: Tanned-podcast/QGIS_ImageClip
# Source path: Python_Cropping/Console_UnfinishedCodes/RoadCenterLineFromEdge.py
# Source kind: python_file
# Code block id: whole_file
# Harvested at: 2026-06-05T18:25:16

"""
道路縁のXMLデータから道路中心線を生成するQGISスクリプト
Road Centerline Generation from Road Edge XML Data in QGIS

このスクリプトは以下の機能を提供します：
1. XMLファイルから道路縁のラインを読み込み
2. 道路縁のペアを特定
3. 各ペアから中心線を計算
4. 結果を新しいレイヤーとして保存
"""

import os
import sys

# QGISの環境設定
qgis_path = r"C:\Program Files\QGIS 3.36.2"
#qgis.coreに繋ぐパス
sys.path.append(r"C:\Program Files\QGIS 3.36.2\apps\qgis\python")
sys.path.append(r"C:\Program Files\QGIS 3.36.2\apps\qgis\python\plugins")

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsProject,
    QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsField
)
from PyQt5.QtCore import QVariant
import xml.etree.ElementTree as ET
import math
from typing import List, Tuple, Dict


 # 入力XMLファイルのパス
xml_file_path = r"C:\Users\kyohe\石川県基盤地図情報\道路縁\Road_Edge\FG-GML-553656-RdEdg-20230701-0001.xml"
    
# 出力ファイルのパス
output_path = r"C:\Users\kyohe\ishikawa_QGISimageclipPolygon\misc\CenterlinefromEdge.fgb"

class RoadCenterlineGenerator:
    """道路中心線生成クラス"""
    
    def __init__(self):
        self.edge_features = []
        self.centerline_features = []
        
    def load_xml_roadedges(self, xml_file_path: str) -> bool:
        """
        XMLファイルから道路縁データを読み込み（GML名前空間対応）
        """
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            ns = {
                'gml': 'http://www.opengis.net/gml/3.2',
                'fgd': 'http://fgd.gsi.go.jp/spec/2008/FGD_GMLSchema'
            }

            # <RdEdg>タグをすべて取得
            for edge_elem in root.findall('.//fgd:RdEdg', ns):
                coordinates = []
                # <gml:posList>をすべて取得
                for poslist_elem in edge_elem.findall('.//gml:posList', ns):
                    pos_text = poslist_elem.text.strip()
                    pos_values = [float(v) for v in pos_text.split()]
                    # 2つずつ取り出して座標にする（緯度 経度の順）
                    for i in range(0, len(pos_values), 2):
                        lat = pos_values[i]
                        lon = pos_values[i+1]
                        coordinates.append(QgsPointXY(lon, lat))  # QGISは(x, y)=(経度, 緯度)
                if len(coordinates) >= 2:
                    line_geom = QgsGeometry.fromPolylineXY(coordinates)
                    feature = QgsFeature()
                    feature.setGeometry(line_geom)
                    self.edge_features.append(feature)

            print(f"道路縁データを {len(self.edge_features)} 件読み込みました")
            return True

        except Exception as e:
            print(f"XMLファイルの読み込みエラー: {e}")
            return False
    
    def find_parallel_edges(self, tolerance: float = 10.0) -> List[Tuple[QgsFeature, QgsFeature]]:
        """
        並行する道路縁のペアを特定
        
        Args:
            tolerance: 並行判定の許容距離（メートル）
            
        Returns:
            List[Tuple]: 並行する道路縁のペアのリスト
        """
        parallel_pairs = []
        
        for i, edge1 in enumerate(self.edge_features):
            for j, edge2 in enumerate(self.edge_features[i+1:], i+1):
                if self._are_parallel_edges(edge1, edge2, tolerance):
                    parallel_pairs.append((edge1, edge2))
        
        print(f"並行する道路縁のペアを {len(parallel_pairs)} 組見つけました")
        return parallel_pairs
    
    def _are_parallel_edges(self, edge1: QgsFeature, edge2: QgsFeature, tolerance: float) -> bool:
        """
        2つの道路縁が並行しているか判定
        
        Args:
            edge1: 道路縁1
            edge2: 道路縁2
            tolerance: 許容距離
            
        Returns:
            bool: 並行している場合True
        """
        geom1 = edge1.geometry()
        geom2 = edge2.geometry()
        
        if not geom1 or not geom2:
            return False
        
        # 2つのラインの距離を計算
        distance = geom1.distance(geom2)
        
        # 距離が許容範囲内で、かつ方向が類似している場合に並行と判定
        if distance <= tolerance:
            # 方向の類似性をチェック（簡易版）
            return self._check_direction_similarity(geom1, geom2)
        
        return False
    
    def _check_direction_similarity(self, geom1: QgsGeometry, geom2: QgsGeometry) -> bool:
        """
        2つのラインの方向の類似性をチェック
        
        Args:
            geom1: ジオメトリ1
            geom2: ジオメトリ2
            
        Returns:
            bool: 方向が類似している場合True
        """
        try:
            # ラインの開始点と終了点を取得
            points1 = geom1.asPolyline()
            points2 = geom2.asPolyline()
            
            if len(points1) < 2 or len(points2) < 2:
                return False
            
            # 方向ベクトルを計算
            dir1 = QgsPointXY(points1[-1].x() - points1[0].x(), 
                             points1[-1].y() - points1[0].y())
            dir2 = QgsPointXY(points2[-1].x() - points2[0].x(), 
                             points2[-1].y() - points2[0].y())
            
            # 角度を計算
            angle1 = math.atan2(dir1.y(), dir1.x())
            angle2 = math.atan2(dir2.y(), dir2.x())
            
            # 角度差を計算（絶対値）
            angle_diff = abs(angle1 - angle2)
            angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
            
            # 30度以内の角度差を類似と判定
            return angle_diff <= math.radians(30)
            
        except Exception:
            return False
    
    def generate_centerlines(self, parallel_pairs: List[Tuple[QgsFeature, QgsFeature]]) -> None:
        """
        並行する道路縁のペアから中心線を生成
        
        Args:
            parallel_pairs: 並行する道路縁のペアのリスト
        """
        for edge1, edge2 in parallel_pairs:
            centerline = self._calculate_centerline(edge1, edge2)
            if centerline:
                self.centerline_features.append(centerline)
        
        print(f"中心線を {len(self.centerline_features)} 本生成しました")
    
    def _calculate_centerline(self, edge1: QgsFeature, edge2: QgsFeature) -> QgsFeature:
        """
        2つの道路縁から中心線を計算
        
        Args:
            edge1: 道路縁1
            edge2: 道路縁2
            
        Returns:
            QgsFeature: 中心線のフィーチャ
        """
        try:
            geom1 = edge1.geometry()
            geom2 = edge2.geometry()
            
            if not geom1 or not geom2:
                return None
            
            # 各ラインの点を取得
            points1 = geom1.asPolyline()
            points2 = geom2.asPolyline()
            
            # 中心線の点を計算
            center_points = []
            
            # 短い方のラインに合わせて中心点を計算
            min_length = min(len(points1), len(points2))
            
            for i in range(min_length):
                # 対応する点の中心を計算
                center_x = (points1[i].x() + points2[i].x()) / 2
                center_y = (points1[i].y() + points2[i].y()) / 2
                center_points.append(QgsPointXY(center_x, center_y))
            
            # 中心線のジオメトリを作成
            centerline_geom = QgsGeometry.fromPolylineXY(center_points)
            
            # フィーチャを作成
            feature = QgsFeature()
            feature.setGeometry(centerline_geom)
            
            return feature
            
        except Exception as e:
            print(f"中心線計算エラー: {e}")
            return None
    
    def save_centerlines(self, output_path: str) -> bool:
        """
        生成した中心線をFGBファイルに保存（QGIS 3.36.2対応）
        """
        try:
            # 中心線レイヤーを作成
            centerline_layer = QgsVectorLayer("LineString?crs=EPSG:6668", "Road_Centerlines", "memory")

            # フィールドを追加
            provider = centerline_layer.dataProvider()
            provider.addAttributes([
                QgsField("id", QVariant.Int),
                QgsField("length", QVariant.Double)
            ])
            centerline_layer.updateFields()

            # フィーチャを追加
            provider.addFeatures(self.centerline_features)

            # 新しい推奨APIでFGB形式で保存
            from qgis.core import QgsVectorFileWriter, QgsProject
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "FlatGeobuf"
            options.fileEncoding = "UTF-8"
            errorcode, error, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                centerline_layer,
                output_path,
                QgsProject.instance().transformContext(),
                options
            )

            if errorcode == QgsVectorFileWriter.NoError:
                print(f"中心線を {output_path} に保存しました")
                return True
            else:
                print(f"中心線保存エラー: {error}")
                return False

        except Exception as e:
            print(f"中心線保存エラー: {e}")
            return False


def main():
    """メイン処理"""
    # QGISアプリケーションの初期化（QGIS環境で実行する場合）
    # qgs = QgsApplication([], True)
    # QgsApplication.setPrefixPath("/path/to/qgis", True)
    # qgs.initQgis()
    
   
    if not os.path.exists(xml_file_path):
        print("指定されたXMLファイルが見つかりません。")
        return
    
    
    # 道路中心線生成器を作成
    generator = RoadCenterlineGenerator()
    
    # XMLファイルから道路縁データを読み込み
    if not generator.load_xml_roadedges(xml_file_path):
        print("XMLファイルの読み込みに失敗しました。")
        return
    
    # 並行する道路縁のペアを特定
    parallel_pairs = generator.find_parallel_edges(tolerance=10.0)
    
    if not parallel_pairs:
        print("並行する道路縁のペアが見つかりませんでした。")
        return
    
    # 中心線を生成
    generator.generate_centerlines(parallel_pairs)
    
    # 結果を保存
    if generator.save_centerlines(output_path):
        print("道路中心線の生成が完了しました。")
    else:
        print("中心線の保存に失敗しました。")


if __name__ == "__main__":
    main()
