"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from typing import Any, Optional

from qgis.core import (
    QgsGeometry,
    QgsFeatureSink,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsLineString,
    QgsPoint,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex
)
from qgis import processing

from qgis.PyQt.QtCore import QVariant
try:
    from qgis.PyQt.QtCore import QMetaType
except Exception:
    pass

class AddFgAeAlagorithm(QgsProcessingAlgorithm):
    FG = "FG"
    FG_1_ORDNUNG = "FG_1_ORDNUNG"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "FG_AE_Hinzufuegen"

    def displayName(self) -> str:
        return "FG_AE_Hinzufuegen"

    def group(self) -> str:
        return "Pruefroutinen"

    def groupId(self) -> str:
        return "Pruefroutinen"

    def shortHelpString(self) -> str:
        return "Example algorithm short description"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FG,
                'Gewässer-Layer: fg',
                [QgsProcessing.SourceType.TypeVectorLine]
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FG_1_ORDNUNG,
                'Gewässer-Layer: Fließgewässer 1. Ordnung',
                [QgsProcessing.SourceType.TypeVectorLine]
            )
        )


        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, "Output layer")
        )

    def processAlgorithm(
        self,
        parameters,
        context,
        feedback,
    ):
        """
        Here is where the processing itself takes place.
        """

        layer_fg = self.parameterAsVectorLayer(parameters, self.FG, context)
        if layer_fg is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.FG)
            )
        layer_fg_1ordnung = self.parameterAsVectorLayer(parameters, self.FG_1_ORDNUNG, context)
        
        # Festlegung fuer die Schrittweite (in m)
        dist_verl = 4
        # Festlegung fuer die maximale Anzahl an Suchen n*dist_verl -> max 40m
        n_max = 10
        
        # Spatial indices fuer die beiden Layer:
        spatial_index_fg =  QgsSpatialIndex(layer_fg.getFeatures())
        spatial_index_fg_1ordnung = QgsSpatialIndex(layer_fg_1ordnung.getFeatures())
        
        
        def get_line_candidates_ids(  #von pruefungsroutinen importieren
            geom,
            spatial_index_other,
            tolerance=0.05
        ):
            """
            Ermittelt mithilfe einer Boundingbox die ids von Linienobjekten aus dem other_layer, auf dem geom liegen könnte
            :param QgsGeometry geom
            :param QgsSpatialIndex spatial_index_other
            :param float tolerance: Suchraum bei Punkten: default 0.05
            :return: list
            """
            if geom.type() == 0:  # Point
                intersecting_ids = spatial_index_other.intersects(geom.boundingBox().buffered(tolerance))
            else:
                intersecting_ids = spatial_index_other.intersects(geom.boundingBox())
            return intersecting_ids
        
        ###hier 
        current_ft_fg = layer_fg.getFeature(1)
        
        def muendet_nicht_in_fg_2ordnung(
            current_ft_fg,
            spatial_index_fg,
            layer_fg
        ):
            current_ft_id = current_ft_fg.id()
            vtx_muendung = QgsGeometry(current_ft_fg.geometry().vertexAt(0))
            intersecting_candidates_1 = get_line_candidates_ids(vtx_muendung, spatial_index_fg)
            if current_ft_id in intersecting_candidates_1:
                # die eigene id() entfernen
                intersecting_candidates_1.remove(current_ft_id)
            intersecting_ids = [ft_id for ft_id in intersecting_candidates_1 if layer_fg.getFeature(ft_id).geometry().distance(vtx_muendung) < 1e-5]
            return len(intersecting_ids)==0  # True wenn keines schneidet
        
        fg_einmuendend = [
            current_ft.id() for current_ft in layer_fg.getFeatures() if muendet_nicht_in_fg_2ordnung(
                current_ft,
                spatial_index_fg,
                layer_fg
            ) 
        ]
        
        
        def linie_verlaengern(
            n,
            vtx_muendung,
            dist_verl,
            delta_x_laenge1,
            delta_y_laenge1,
            layer_fg_1ordnung,
            spatial_index_fg_1ordnung,
        ):
            x_muendung = vtx_muendung.asPoint().x()
            y_muendung = vtx_muendung.asPoint().y()
            x_neu = x_muendung - (n*dist_verl*delta_x_laenge1)
            y_neu = y_muendung - (n*dist_verl*delta_y_laenge1)
            line_neu = QgsGeometry(
                QgsLineString([
                    QgsPoint(x_neu, y_neu),
                    vtx_muendung.asPoint()
                ])
            )
            intersecting_candidates = get_line_candidates_ids(
                line_neu,
                spatial_index_fg_1ordnung
            )
            intersecting_ids = [
                ft_id for ft_id in intersecting_candidates if layer_fg_1ordnung.getFeature(ft_id).geometry().intersects(line_neu)
            ]
            if len(intersecting_ids) == 0:
                return (False, )
            elif len(intersecting_ids) == 1:
                geom_ft_1ordnung = layer_fg_1ordnung.getFeature(intersecting_ids[0]).geometry()
                schnittpunkt = geom_ft_1ordnung.intersection(line_neu)
                line_ae = QgsGeometry(
                    QgsLineString([
                        schnittpunkt.asPoint(),
                        vtx_muendung.asPoint()
                    ])
                )
                ft_ae = QgsFeature()
                ft_ae.setGeometry(line_ae)
                return (True, ft_ae)
            else:
                raise QgsProcessingException(f'zu viele Schnittpunkte beim Verlängern mit Gew. 2. Ordnung: {intersecting_ids}')
                return (False, )

        fg_ae_featurelist = []
        for current_ft_id in fg_einmuendend:
            current_ft_fg = layer_fg.getFeature(current_ft_id)
            
            # erster Stuetzpunkt
            vtx_muendung = QgsGeometry(current_ft_fg.geometry().vertexAt(0))
            
            # zweiter Stuetzpunkt
            vtx_1 = QgsGeometry(current_ft_fg.geometry().vertexAt(1))
            x_muendung = vtx_muendung.asPoint().x()
            y_muendung = vtx_muendung.asPoint().y()
            x_1 = vtx_1.asPoint().x()
            y_1 = vtx_1.asPoint().y()
            distance_vtx_0_1 = vtx_muendung.distance(vtx_1)
            
            # delta x fuer die laenge 1
            delta_x_laenge1 = (x_1-x_muendung) / distance_vtx_0_1
            delta_y_laenge1 = (y_1-y_muendung) / distance_vtx_0_1
            
            for n in range(1, n_max):
                ergebnis_verl = linie_verlaengern(
                    n,
                    vtx_muendung,
                    dist_verl,
                    delta_x_laenge1,
                    delta_y_laenge1,
                    layer_fg_1ordnung,
                    spatial_index_fg_1ordnung,
                )
                if ergebnis_verl[0]:
                    ft_ae = ergebnis_verl[1]
                    ft_ae.setAttributes(['ba_cd_temp'])
                    fg_ae_featurelist.append(ft_ae)
                    break
                else:
                    continue
            
        out_fields = QgsFields()
        try:
            out_fields.append(QgsField('ba_cd', QMetaType.QString))
        except Exception:  # for QGIS prior to version 3.38
            out_fields.append(QgsField('ba_cd', QVariant.String))
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            layer_fg.wkbType(),
            layer_fg.sourceCrs(),
        )
        
        for ft in fg_ae_featurelist:
            sink.addFeature(ft, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: dest_id}

    def createInstance(self):
        return AddFgAeAlagorithm()
