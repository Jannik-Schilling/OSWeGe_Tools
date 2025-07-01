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

from qgis.core import (
    Qgis,
    QgsGeometry,
    QgsFeatureSink,
    QgsFields,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex
)

# Exception for deprecated QVariant if QGIS version is older than 3.38

if (int(Qgis.version().split('.')[0]) == 3 and int(Qgis.version().split('.')[1]) > 36) or (int(Qgis.version().split('.')[0]) > 3):
    qgis_version_newer_3_38 = True
    from qgis.PyQt.QtCore import QMetaType
else:
    qgis_version_newer_3_38 = False
    from qgis.PyQt.QtCore import QVariant


from .hilfsfunktionen import (
    linie_verlaengern
)

from .config_tools import (
    get_config_from_json,
    config_layer_if_in_project
)
from .pruefungsroutinen import muendet_nicht_in_fg_2ordnung
from .defaults import file_config_user

class AddFgAeAlagorithm(QgsProcessingAlgorithm):
    FG = "FG"
    FG_1_ORDNUNG = "FG_1_ORDNUNG"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "2_fg_ae_hinzufuegen"

    def displayName(self) -> str:
        return "2_fg_ae_hinzufuegen"

    def group(self) -> str:
        return "Datenexport"

    def groupId(self) -> str:
        return "Datenexport"

    def shortHelpString(self) -> str:
        return (
            'Mit diesem Werkzeug werden Einleitungs- und Ausleitungsabschnitte '
            + 'zu Gewässern 1. Ordnunung erstellt. \n\n'
            + 'Eingaben:\n'
            + '- Der Gewässer-Layer (fg) mit den Verbandsgewässern (2. Ordnung)\n'
            + '- Ein Linienlayer der Fließgewässer 1. Ordnung. '
            + 'Dieser kann bespielsweise aus den Daten des Umweltkartenportals mit dem Werkzeug '
            + '\'Nach Ausdruck extrahieren\' mit  \' \"wmd\" in (1501, 1502) \'  erstellt werden'
        )

    def initAlgorithm(self, config=None):
        # User config laden
        dict_layer_defaults = config_layer_if_in_project(file_config_user)

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.FG,
                'Gewässer-Layer: fg',
                [QgsProcessing.SourceType.TypeVectorLine],
                defaultValue=dict_layer_defaults['gewaesser']
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
        # Layer laden
        layer_fg = self.parameterAsVectorLayer(parameters, self.FG, context)
        if layer_fg is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.FG)
            )


        layer_fg_1ordnung = self.parameterAsVectorLayer(parameters, self.FG_1_ORDNUNG, context)
        
        # Gleichheit der Koordinatensysteme pruefen
        if not layer_fg.crs().authid()) == layer_fg_1ordnung.crs().authid():
            raise QgsProcessingException(
                'Alle Layer müssen im gleichen Koordinatenbezugssystem gespeichert sein!'
            )

        # Festlegung fuer die Schrittweite (in m)
        dist_verl = 1
        # Festlegung fuer die maximale Anzahl an Suchen n*dist_verl
        user_config_dict = get_config_from_json(file_config_user)
        dist_max = int(user_config_dict['max_suchraum_fg_ae_in_m'])
        n_max = round(dist_max / dist_verl)
        
        # ist das Feld mit dem Gewaessercode verfuegbar?
        gew_key_field = user_config_dict['check_layer_defaults']['primaerschluessel_gew']
        if gew_key_field in layer_fg.fields().names():
            gew_key_available = True
        else:
            gew_key_available = False
            feedback.pushWarning(
                'Gewässernummer (Feld \"'
                + gew_key_field
                +'\") nicht verfügbar im Layer '
                + layer_fg.name()
                + '. Stattdessen wird die Objekt-ID eingetragen'
                )
        
        # Spatial indices fuer die beiden Layer:
        spatial_index_fg =  QgsSpatialIndex(layer_fg.getFeatures())
        spatial_index_fg_1ordnung = QgsSpatialIndex(layer_fg_1ordnung.getFeatures())


        # Objekte, die in ein Gew. 1. Ordnung muenden (und nicht in ein Gew. 2. Ordnung)
        fg_einmuendend = [
            current_ft.id() for current_ft in layer_fg.getFeatures() if muendet_nicht_in_fg_2ordnung(
                current_ft,
                spatial_index_fg,
                layer_fg
            ) 
        ]

        # Linien verlaengern
        fg_ae_featurelist = []
        feedback.setProgressText(
            f'Erstelle an {len(fg_einmuendend)} Gewässermündungen fg_ae-Abschnitte, Suchraum: {dist_max}m'
        )
        for current_ft_id in fg_einmuendend:
            current_ft_fg = layer_fg.getFeature(current_ft_id)
            if gew_key_available:
                gew_key_i = current_ft_fg.attributeMap()[gew_key_field]
            else:
                gew_key_i = current_ft_fg.id()
                gew_key_field = 'Objekt-ID'
            
            # erster Stuetzpunkt
            vtx_muendung = QgsGeometry(current_ft_fg.geometry().vertexAt(0))
            
            # zweiter Stuetzpunkt
            vtx_1 = QgsGeometry(current_ft_fg.geometry().vertexAt(1))
            x_muendung = vtx_muendung.asPoint().x()
            y_muendung = vtx_muendung.asPoint().y()
            x_1 = vtx_1.asPoint().x()
            y_1 = vtx_1.asPoint().y()
            distance_vtx_0_1 = vtx_muendung.distance(vtx_1)
            
            # delta x fuer die Laenge 1
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
                    ft_ae.setAttributes([gew_key_i])
                    fg_ae_featurelist.append(ft_ae)
                    break
                else:
                    continue

        # Ausgabe
        out_fields = QgsFields()
        if qgis_version_newer_3_38:
            out_fields.append(QgsField(gew_key_field, QMetaType.QString))
        else:  # for QGIS vor Version 3.38
            out_fields.append(QgsField(gew_key_field, QVariant.String))
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
