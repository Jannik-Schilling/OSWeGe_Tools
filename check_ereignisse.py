# -*- coding: utf-8 -*-

"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Jannik Schilling'
__date__ = '2023-11-27'


import pandas as pd
import numpy as np
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (NULL,
                       QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsExpression,
                       QgsFeatureRequest,
                       QgsGeometry,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFeatureSink,
                       QgsSpatialIndex,
                       QgsFeature)
from qgis import processing

from .pruefungsroutinen import (
    check_spalte_vorhanden,
    check_wert_fehlend,
    check_geometrie_leer,
    check_geometrie_multi
)

from .defaults import (
    oswDataFeedback
)

from .meldungen import fehlermeldungen_generieren

class checkEreignisse(QgsProcessingAlgorithm):
    GEOM_TOLERANZ = 'GEOM_TOLERANZ'
    EREIGNIS_LAYER = 'EREIGN_LAYER'
    GEWAESSER_LAYER = 'GEWAESSER_LAYER'
    REPORT = 'REPORT'

    def name(self):
        return 'Pruefroutine_Ereignisse'

    def displayName(self):
        return '2_Pruefroutine_Ereignisse'

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Pruefroutinen'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return checkEreignisse()

    def shortHelpString(self):
        return self.tr(""" 
        Überprüft die Geometrien und Attribute des Ereignislayers anhand des Gewässerlayers
        \n
        Über den Parameter "Toleranz" kann eine mögliche Abweichung der Geometrie (in Meter) festgelegt werden. Standardmäßig ist diese auf 0 gesetzt
        """)
        
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.EREIGNIS_LAYER,
                self.tr('Ereignislayer'),
                [QgsProcessing.SourceType.TypeVectorLine, QgsProcessing.SourceType.TypeVectorPoint]
            )
        )
        
        # self.addParameter(
            # QgsProcessingParameterField(
                # self.FELD_ID,
                # self.tr("Eindeutiger Ereignis-Objektname / ID / fid"),
                # parentLayerParameterName = self.EREIGNIS_LAYER,
                # defaultValue = 'fid',
                # type = QgsProcessingParameterField.Any,
                # optional = True
            # )
        # )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.GEWAESSER_LAYER,
                self.tr('Gewässerlayer'),
                [QgsProcessing.SourceType.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.GEOM_TOLERANZ,
                self.tr('Toleranz'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.REPORT,
                self.tr('Reportdatei'),
                'Textdatei (*.txt)',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        layer_ereign = self.parameterAsVectorLayer(parameters, self.EREIGNIS_LAYER, context)
        total = layer_ereign.featureCount() if layer_ereign.featureCount() else 0
        total_steps = 100.0/total if total != 0 else 0
        layer_gew = self.parameterAsVectorLayer(parameters, self.GEWAESSER_LAYER, context)
        reportdatei = self.parameterAsString(parameters, self.REPORT, context)
        # feld_ereign_id = self.parameterAsString(parameters, self.FELD_ID, context)

        
        # Festlegungen
        params = {
            'layer_ereign': layer_ereign,
            'layer_gew': layer_gew,
            'feedback': feedback,
            'toleranz_abw': self.parameterAsDouble(parameters, self.GEOM_TOLERANZ, context)
        }

        # Layerauswahl und Felder
        # Ereignislayer
        feld_ereign_gewname = 'ba_cd'
        #feld_ereign_stat_punkt = 'STAT'
        #feld_ereign_stat_linie_von = 'STAT_VON'
        #feld_ereign_stat_linie_bis = 'STAT_BIS'
        #feld_ereign_art = 'ART'
        # Gewaesserlayer
        feld_gew_name = 'ba_cd'

        if layer_ereign.geometryType() == 1:  # Linie
            benoetige_felder = [
                feld_ereign_gewname,
                #feld_ereign_stat_linie_von,
                #feld_ereign_stat_linie_bis,
                #feld_ereign_art
            ]
        else:  # Punkt
            benoetige_felder = [
                feld_ereign_gewname,
                #feld_ereign_stat_punkt,
                #feld_ereign_art
            ]

        # dictionary fuer Feedback / Fehlermeldungen
        report_dict = {}
        """
        report_dict = {
            'Test1': {
                'Typ': 'allgemein',
                'Report': 0 / oswDataFeedback
            },
            'Test2':
                'Typ': 'Attribut',
                'Spalte': 'Spaltenname',
                'Report': oswDataFeedback,
                'Objekte': [id1, id2]
            'Test3':
                'Typ': 'Geometrie',
                'Report': oswDataFeedback,
                'Objekte': [id1, id2] (Einzelfehler) oder [[id1, id2][id3, id4]] (Ueberschneidungen etc.)
        }
        """

        # Alle benoetigten Spalten im Layer?
        for feld in benoetige_felder:
            test_spalte_vorh = 'Test_COL_'+feld+'_vorhanden'
            report_dict[test_spalte_vorh] = {
                'Typ': 'allgemein',
                'Report': check_spalte_vorhanden(
                    spaltenname=feld,
                    layer=layer_ereign,
                    **params
                )
            }

        # Pruefroutinen fuer Attribute
        feedback.setProgressText('Prüfe Attribute:')
        fehlende_spalten = []
        for feld in benoetige_felder:
            test_spalte_vorh = 'Test_COL_'+feld+'_vorhanden'
            if report_dict[test_spalte_vorh]['Report'] == 0:
                feedback.setProgressText(feld)
                datagen = (
                    [
                        ft.id(),
                        ft[feld],
                    ] for ft in layer_ereign.getFeatures()
                )
                df_ereign = pd.DataFrame.from_records(
                    data=datagen,
                    columns=[
                        'id',
                        feld
                    ]
                )
                del datagen
                
                # fehlende Werte
                val_list = []
                for i, val in enumerate(df_ereign[feld]):
                    if check_wert_fehlend(val) == 0:
                        pass
                    else:
                        val_list = val_list + [df_ereign.loc[i, 'id']]
                    feedback.setProgress(int(i * total_steps))
                test_fehlender_wert = 'Test_VAL_'+feld+'_MISSING'
                report_dict[test_fehlender_wert] = {
                    'Typ': 'Attribut',
                    'Spalte': feld,
                    'Report': oswDataFeedback.VAL_MISSING,
                    'Objekte': val_list
                }
            else:
                fehlende_spalten.append(feld)


        # Pruefroutinen fuer Geometrien
        if len(fehlende_spalten) != 0:  # keine fehlenden Spalten
            feedback.pushWarning(
                'Nicht alle benötigten Spalten vorhanden (siehe Report), Geometrietest wird übersprungen'
                + str(fehlende_spalten)
            )
        else:
            feedback.setProgressText('Prüfe Geometrien:')
            feedback.setProgressText('- leere Geometrien')
            for i, ft in enumerate(layer_ereign.getFeatures()):
                geom_i = ft.geometry()
                if check_geometrie_leer(geom_i) == 0:
                    pass
                else:
                    val_list = val_list + [ft.id()]
                feedback.setProgress(int(i * total_steps))
            report_dict['Test_GEOM_EMPTY'] = {
                'Typ': 'Geometrie',
                'Report': oswDataFeedback.GEOM_EMPTY,
                'Objekte': val_list
            }
            
            # Multigeometrien
            feedback.setProgressText('- Multigeometrien')
            val_list = []
            for i, ft in enumerate(layer_ereign.getFeatures()):
                geom_i = ft.geometry()
                if check_geometrie_multi(geom_i) == 0:
                    pass
                else:
                    val_list = val_list + [ft.id()]
                feedback.setProgress(int(i * total_steps))
            report_dict['Test_GEOM_MULTI'] = {
                'Typ': 'Geometrie',
                'Report': oswDataFeedback.GEOM_MULTI,
                'Objekte': val_list
            }
            
            # Übereinstimmung mit Gewässergeometrie
            feedback.setProgressText('- Übereinstimmung mit Gewässergeometrie')
            
            feedback.setProgressText('> Gewässername prüfen')
            ereign_joined_layer = processing.run(
                "native:joinbynearest",
                {
                    'INPUT': layer_ereign,
                    'INPUT_2': layer_gew,
                    'FIELDS_TO_COPY': ['ba_cd'],
                    'DISCARD_NONMATCHING': False,
                    'PREFIX':'gew_', 
                    'NEIGHBORS':1, 
                    'MAX_DISTANCE': None,
                    'OUTPUT':'memory:'
                },
                context=context,
                feedback=feedback
            )['OUTPUT']
            for i, ft in enumerate(ereign_joined_layer.getFeatures()):
                if ft['ba_cd'] == ft['gew_ba_cd']:
                    pass
                else:
                    print('Falscher Gewässername' + str(i))

            if layer_ereign.geometryType() == 1:
                feedback.setProgressText('> Geometrieübereinstimmung prüfen')
                val_list = []
                for i, ft in enumerate(ereign_joined_layer.getFeatures()):
                    geom_i = ft.geometry()
                    # check if null or multi
                    req_expression = QgsExpression("\"ba_cd\" = \'"+str(ft['gew_ba_cd'])+"\'")
                    gew_i = [f for f in layer_gew.getFeatures(QgsFeatureRequest(req_expression))][0]
                    gew_i_geom = gew_i.geometry()
                    vtx_df = pd.DataFrame({
                        'ereign_sp': [QgsGeometry.fromPoint(vtx) for vtx in geom_i.vertices()],
                        'naechster_gew_sp_idx': np.nan,
                        'distanz_sp': np.nan,
                        'distanz_gew': np.nan,
                    })
                    
                    vtx_df_maxIndex = vtx_df.index[-1]
                    ereign_vtx_start_geom = vtx_df['ereign_sp'][0]
                    ereign_vtx_ende_geom = vtx_df['ereign_sp'][vtx_df_maxIndex]
                    ereign_vtc_mittel_geom = vtx_df['ereign_sp'][1:vtx_df_maxIndex]

                    # naechster Punkt auf dem Gewässer
                    nearest_gew_point_start = gew_i_geom.nearestPoint(ereign_vtx_start_geom)
                    nearest_gew_xy_start = nearest_gew_point_start.asPoint()
                    nearest_gew_point_ende = gew_i_geom.nearestPoint(ereign_vtx_ende_geom)
                    nearest_gew_xy_ende = nearest_gew_point_ende.asPoint()

                    # naechster Stuetzpunkt danach
                    stp_start = gew_i_geom.closestSegmentWithContext(nearest_gew_xy_start)[2]
                    stp_stop = gew_i_geom.closestSegmentWithContext(nearest_gew_xy_ende)[2]
                    gew_idx_mittlere_vtc = list(range(stp_start, stp_stop))  # indices der mittleren Stuetzpunkte
                    
                    # Distanz zu den Stuetzpunkten
                    for ereign_vtx_idx in vtx_df.index:
                        ereign_vtx_geom = vtx_df['ereign_sp'][ereign_vtx_idx]
                        ereign_vtx_XY = ereign_vtx_geom.asPoint()  # XY-Geometrie des Ereignisstützpunkts
                        if ereign_vtx_idx == 0:
                            pass
                        elif ereign_vtx_idx == vtx_df_maxIndex:
                            pass
                        else:
                            gew_vtx_dist, gew_vtx_idx = gew_i_geom.closestVertexWithContext(ereign_vtx_XY)
                            vtx_df.loc[ereign_vtx_idx, 'distanz_sp'] = gew_vtx_dist
                            vtx_df.loc[ereign_vtx_idx, 'naechster_gew_sp_idx'] = gew_vtx_idx
                        vtx_df.loc[ereign_vtx_idx, 'distanz_gew'] = gew_i_geom.closestSegmentWithContext(ereign_vtx_XY)[0]
                    if all(x == 0 for x in vtx_df['distanz_gew']):
                        pass
                    else:
                        val_list = val_list + [ft.id()]
                    del vtx_df
                    feedback.setProgress(int(i * total_steps))
                report_dict['Test_GEOM_NOT_ON_GEWLINE'] = {
                    'Typ': 'Geometrie',
                    'Report': oswDataFeedback.GEOM_NOT_ON_GEWLINE,
                    'Objekte': val_list
                }
            else: # Punkte
                feedback.setProgressText('> Lage der Punktgeometrie prüfen')
                val_list = []

        with open(reportdatei, 'w') as f:
            f.write(
                '**************************************'
                + '\nÜberprüfung des (Ereignislayers)'
                + '\n\nLayer: ' + str(layer_ereign)
                + '\n**************************************\n\n'
            )
            for val in report_dict.values():
                f.write(fehlermeldungen_generieren(val))

        feedback.pushInfo('Report gespeichert in ' + str(reportdatei)+ '\n')

        return {}