# -*- coding: utf-8 -*-
"""
/***************************************************************************
 oswege_toolsDialog
                                 A QGIS plugin
 werkzeugsammlung
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-04-04
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Jannik Schilling
        email                : jannik.schilling@uni-rostock.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import pandas as pd


from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsPoint,
    QgsProject,
    QgsSnappingConfig,
    QgsTolerance,
    QgsVectorLayer,
    QgsWkbTypes
) 
from qgis.gui import (
    QgsMapTool,
    QgsMapToolEmitPoint,
    QgsSnapIndicator
)
from PyQt5.QtCore import (
    Qt
)
from PyQt5.QtWidgets import (
    QDialogButtonBox
)
from PyQt5.QtGui import QPalette, QColor

from .defaults import (
    findGew_tolerance_dist,
    file_config_user
)

from .config_tools import config_layer_if_in_project

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__),
    'userinterfaces',
    'stationierung_dialog_base.ui')
)

QgsInstance=QgsProject.instance()

class PrintSnappedPoint(QgsMapToolEmitPoint):
    """
    Klasse fuer das Abfragen der geklickten Koordinate
    """
    def __init__(
        self,
        init_canvas,
        layer_snaplist,
        parent
    ):
        QgsMapToolEmitPoint.__init__(self, init_canvas)
        self.setParent(parent)
        self.canvas = init_canvas
        self.snap_indicator = QgsSnapIndicator(self.canvas)
        self.snapping_utils = self.canvas.snappingUtils()
        self.config_save = self.snapping_utils.config()
        self.snapping_config = self.snapping_utils.config()
        self.snapping_config.setEnabled(True)
        self.snapping_config.setMode(
            QgsSnappingConfig.AdvancedConfiguration
        )
        """
        self.snapping_settings = QgsSnappingConfig.IndividualLayerSettings()
        self.snapping_settings.setEnabled(True)
        """
        self.layer_snaplist = layer_snaplist
        for ly in self.layer_snaplist:
            if ly is not None:
                self.snapping_settings = QgsSnappingConfig.IndividualLayerSettings()
                self.snapping_settings.setEnabled(True)
                if ly.geometryType() == QgsWkbTypes.LineGeometry:
                    self.snapping_settings.setTypeFlag(Qgis.SnappingTypes(Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment))
                else:
                    self.snapping_settings.setTypeFlag(Qgis.SnappingType.Vertex)
                self.snapping_settings.setTolerance(15)
                self.snapping_settings.setUnits(QgsTolerance.Pixels)
                self.snapping_config.setIndividualLayerSettings(
                    ly,
                    self.snapping_settings
                )
                self.snapping_utils.setConfig(self.snapping_config)
        self.reset()
    
    def reset(self):
        self.pointxy = None
        self.ft_id = None
        self.matched_layer = None

    def canvasMoveEvent(self, e):
        snapping_match = self.snapping_utils.snapToMap(e.pos())
        self.snap_indicator.setMatch(snapping_match)

    def deactivate(self):
        self.snapping_config.reset()
        self.snapping_utils.setConfig(
            self.config_save
        )
        self.snap_indicator.setVisible(False)
        self.canvas.unsetMapTool(self)

    def activateMe(self):
        self.canvas.setMapTool(self)

    def canvasPressEvent(self, e):
        if self.snap_indicator.match().type():
            self.matched_layer = self.snap_indicator.match().layer()
            self.ft_id = self.snap_indicator.match().featureId()
            self.pointxy = self.snap_indicator.match().point()
            self.parent().calc()

    def result(self):
        return [self.pointxy, self.ft_id, self.matched_layer]


class stationierungDialog(QtWidgets.QDialog, FORM_CLASS):
    """
    Dialog fuer das Abfragen der Stationierung
    """
    def __init__(self, canvas, parent=None):
        """
        Constructor
        """
        super(stationierungDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.gew_layer = self.mMapLayerComboBox.currentLayer()
        self.gew_FieldComboBox.setLayer(self.gew_layer)
        self.mMapLayerComboBox.layerChanged.connect(self.reset_gew_layer)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.map_tool = None
        self.QgsInstance = QgsInstance

        # mit config probieren
        #print('start')
        dict_layer_defaults = config_layer_if_in_project(file_config_user)
        if dict_layer_defaults['gewaesser']:
            self.mMapLayerComboBox.setCurrentText(dict_layer_defaults['gewaesser'])
            self.gew_layer = self.mMapLayerComboBox.currentLayer()
        
         # canvas und Maptool-Ueberwachung
        self.canvas = canvas
        self.canvas.mapToolSet.connect(self.on_map_tool_changed)
        self.connected_to_map_tool_changed = True 
        
        # weitere layer-combobox
        list_vlayers = [l for l in QgsInstance.mapLayers().values() if isinstance(l, QgsVectorLayer)]
        self.list_p_l_layer = [l for l in list_vlayers if l.geometryType() in [QgsWkbTypes.LineGeometry, QgsWkbTypes.PointGeometry]]
        self.list_p_l_layer_ohneGew = [l for l in self.list_p_l_layer if l != self.gew_layer]
        list_p_l_layer_ohneGew_names = [l.name() for l in self.list_p_l_layer_ohneGew]
        self.mComboBox.addItems(list_p_l_layer_ohneGew_names)

        # Textanzeige
        self.show_text = (
            'Klicken Sie auf \'Abfrage starten\' um das Werkzeug zu aktivieren'
        )
        self.textBrowser.setText(self.show_text)
        
        # buttons
        self.buttonBox.button(QDialogButtonBox.Close).setText("Fenster Schließen")
        self.pushButton_start.clicked.connect(self.set_green)
        self.pushButton_start.clicked.connect(self.run_action)
        self.pushButton_start.setStyleSheet('QPushButton {background-color: #95f088}')
        self.pushButton_stop.clicked.connect(self.set_grey)
        self.pushButton_stop.setEnabled(False)
        self.buttonBox.rejected.connect(self.set_grey)
        self.buttonBox.rejected.connect(self.closeHelper)
        self.buttonBox.rejected.connect(self.close)
        
    def set_green(self):
        pa_g = QPalette()
        role = QPalette.Background
        pa_g.setColor(role, QColor('#9ecba9'))
        self.setPalette(pa_g)
        self.mMapLayerComboBox.setEnabled(False)
        self.mComboBox.setEnabled(False)
        self.gew_FieldComboBox.setEnabled(False)
        self.pushButton_start.setEnabled(False)
        self.pushButton_stop.setDisabled(False)
        self.setWindowTitle("Stationierung Gewässer (Werkzeug aktiv)")

    def set_grey(self):
        pa_w = QPalette()
        role = QPalette.Background
        pa_w.setColor(role, QColor('#ffffff'))
        self.setPalette(pa_w)
        self.mMapLayerComboBox.setDisabled(False)
        self.mComboBox.setDisabled(False)
        self.gew_FieldComboBox.setDisabled(False)
        self.pushButton_start.setDisabled(False)
        self.pushButton_stop.setEnabled(False)
        self.setWindowTitle("Stationierung Gewässer") 
        if self.map_tool is not None:
            self.map_tool.deactivate()
        
    def reset_gew_layer(self):
        self.gew_layer = self.mMapLayerComboBox.currentLayer()
        self.gew_FieldComboBox.setLayer(self.gew_layer)
        list_vlayers = [l for l in QgsInstance.mapLayers().values() if isinstance(l, QgsVectorLayer)]
        self.list_p_l_layer = [l for l in list_vlayers if l.geometryType() in [QgsWkbTypes.LineGeometry, QgsWkbTypes.PointGeometry]]
        self.list_p_l_layer_ohneGew = [l for l in self.list_p_l_layer if l != self.gew_layer]
        list_p_l_layer_ohneGew_names = [l.name() for l in self.list_p_l_layer_ohneGew]
        self.mComboBox.clear()
        self.mComboBox.addItems(list_p_l_layer_ohneGew_names)

    def run_action(self):
        weitere_snaplayer_name = self.mComboBox.checkedItems()
        model = self.mComboBox.model()
        count = model.rowCount()
        weitere_snaplayer_index = [i for i in range(count) if model.item(i).checkState() == Qt.Checked]
        self.layer_snaplist = [self.gew_layer] + [self.list_p_l_layer_ohneGew[i] for i in weitere_snaplayer_index]
        self.textBrowser.setText(
            'Zur Anzeige der Stationierung klicken Sie auf einen Gewässerabschnitt'
        )
        self.map_tool = PrintSnappedPoint(self.canvas, self.layer_snaplist, self)
        self.map_tool.activateMe()

    def on_map_tool_changed(self, tool):
        """
        funktion um wieder auszuschalten, wenn ein anderes tool aktiv wird
        """
        if isinstance(tool, QgsMapTool):
            if self.canvas.mapTool().toolName() == 'Identify':
                self.set_grey() 
            if self.canvas.mapTool().parent() != self:
                self.set_grey()


    def closeEvent(self, evnt):
        self.set_grey()
        if self.connected_to_map_tool_changed:
            self.canvas.mapToolSet.disconnect(self.on_map_tool_changed)
            self.connected_to_map_tool_changed = False 
        if self.map_tool is not None:
            self.map_tool.deactivate()

    def closeHelper(self):
        self.set_grey()
        if self.connected_to_map_tool_changed:
            self.canvas.mapToolSet.disconnect(self.on_map_tool_changed)
            self.connected_to_map_tool_changed = False 
        if self.map_tool is not None:
            self.map_tool.deactivate()

    def calc(self):
        # temporäres Ergebnis
        clicked_result = self.map_tool.result()
        clicked_point = clicked_result[0]
        target_crs = self.gew_layer.crs()
        source_crs = self.QgsInstance.crs()
        if target_crs != source_crs:
            transform = QgsCoordinateTransform(source_crs, target_crs, self.QgsInstance)
            clicked_point = transform.transform(clicked_point)
        clicked_point_geom = QgsGeometry(QgsPoint(clicked_point.x(), clicked_point.y()))
        l = [(i.id(), clicked_point_geom.distance(i.geometry())) for i in self.gew_layer.getFeatures()]
        df = pd.DataFrame(l, columns=['id', 'dist'])
        df = df.sort_values('dist', ignore_index=True)
        df = df.loc[df['dist'] >= 0]  # -1 wird bei NULL-geometrien gesetzt
        droplist = [] # damit leere geometrien rausgeworfen werden
        for i in df.index:
            id_i = df.loc[i,'id']
            geom_i = self.gew_layer.getFeature(id_i).geometry()
            if geom_i.isEmpty():
                droplist.append(i)
            if geom_i.isNull():
                droplist.append(i)
        droplist = list(set(droplist))
        df = df.drop(droplist)
        df2 = df.loc[df['dist'] < findGew_tolerance_dist]
        if len(df2) > 0:
            pass  # ok
        else:
            # falls alle zu weit weg sind (weiter als findGew_tolerance_dist)
            df2 = df.head(1)
            #dist_show = True
        if len(df2) == 0:
            # falls alle leer oder NULL
            pass
        self.show_text = ''
        for i in df2.index:
            clicked_gew_ft_id = df2.loc[i,'id']
            clicked_line_ft = self.gew_layer.getFeature(clicked_gew_ft_id)
            result_tuple = clicked_line_ft.geometry().closestSegmentWithContext(clicked_point)
            if clicked_line_ft.geometry().isMultipart():
                clicked_line_geom = clicked_line_ft.geometry().asMultiPolyline()
                first_segment = clicked_line_geom[0][:result_tuple[2]]+[result_tuple[1]]
            else:
                clicked_line_geom = clicked_line_ft.geometry().asPolyline()
                first_segment = clicked_line_geom[:result_tuple[2]]+[result_tuple[1]]
            first_segment = [QgsPoint(p) for p in first_segment]
            first_segment_geom = QgsGeometry.fromPolyline(first_segment)
            stationierung = round(first_segment_geom.length(),2)
            gew_name = clicked_line_ft.attribute(self.gew_FieldComboBox.currentText())
            self.show_text = (
                self.show_text +
                'Gewässer: '
                + str(gew_name)
                +'; Stationierung: '
                + str(stationierung)
                + '\n\n'
            )
        self.textBrowser.setText(self.show_text)