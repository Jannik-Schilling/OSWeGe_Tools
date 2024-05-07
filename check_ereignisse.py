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
    check_wert_fehlend
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
        feld_ereign_gewname = 'BA_CD'
        feld_ereign_stat_punkt = 'STAT'
        feld_ereign_stat_linie_von = 'STAT_VON'
        feld_ereign_stat_linie_bis = 'STAT_BIS'
        feld_ereign_art = 'ART'
        # Gewaesserlayer
        feld_gew_name = 'BA_CD'

        if layer_ereign.geometryType() == 1:  # Linie
            benoetige_felder = [
                feld_ereign_gewname,
                feld_ereign_stat_linie_von,
                feld_ereign_stat_linie_bis,
                feld_ereign_art
            ]
        else:  # Punkt
            benoetige_felder = [
                feld_ereign_gewname,
                feld_ereign_stat_punkt,
                feld_ereign_art
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
                'Obj': [id1, id2]
            'Test3':
                'Typ': 'Geometrie',
                'Report': oswDataFeedback,
                'Obj': [id1, id2] oder [[id1, id2][id3, id4]]
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

        # Pruefroutinen fuer Geometrien
        spalten_fuer_geomtest_vorhanden = 0
        for feld in benoetige_felder:
            test_spalte_vorh = 'Test_COL_'+feld+'_vorhanden'
            if report_dict[test_spalte_vorh]['Report'] == 0:
                pass
            else:
                spalten_fuer_geomtest_vorhanden = oswDataFeedback.COL_MISSING

        if spalten_fuer_geomtest_vorhanden != 0:  # keine fehlenden Spalten
            feedback.pushWarning(
                'Nicht alle benötigten Spalten vorhanden (siehe Report), Geometrietest wird übersprungen'
            )
        else:
            # Ereignis-Layer
            datagen = (
                [ft.id()] 
                + [ft[feld] for feld in benoetige_felder] 
                + [ft.geometry()] for ft in layer_ereign.getFeatures()
            )
            df_ereign_felder = ['fid'] + benoetige_felder + ['geometry']

            df_ereign = pd.DataFrame.from_records(
                data=datagen,
                columns=df_ereign_felder
            )
            del datagen
            
            # Gewaesser-Layer
            df_gew_felder = [
                'fid',
                feld_gew_name,
                'geometry'
            ]
            datagen = (
                [
                    ft.id(),
                    ft[feld_gew_name],
                    ft.geometry()
                ] for ft in layer_gew.getFeatures()
            )
            df_gew = pd.DataFrame.from_records(
                data=datagen,
                columns=df_gew_felder
            )
            del datagen
            
            print(report_dict)

            
            # gew_name vorhanden?
            # geometrie 
        
        
        
        
        
        
        
        
        
        
        
        # def check_punkt_auf_linie(ereign_ft_i, err_df=None):
            # '''ueberprueft die Punktgeometrie'''
            # report_ereign_start_stop_msg = {}
            # gew_geom_i = ereign_ft_i['geometry_gew']
            # ereign_geom_i = ereign_ft_i['geometry']
            # # Stationierung vorhanden?
            # pointStation = ereign_ft_i[ereign_feld_stat_punkt]
            # if (pointStation == NULL):
                # report_ereign_start_stop_msg.update({('Feld '+ereign_feld_stat_punkt): ('Fehlender Wert. Konnte Geometrie nicht überprüfen.')})
            # # dann Geometrie überprüfen
            # else:
                # point_on_line = gew_geom_i.interpolate(pointStation)
                # check_vtx = [ereign_geom_i.distance(point_on_line)]
                # if any ([d > toleranz_abw for d in check_vtx]):
                    # report_ereign_start_stop_msg.update({'Geometrie': 'Geometrie nicht mit Gewässer übereinstimmend'})
            # if len(report_ereign_start_stop_msg) > 0:
                # if ereign_ft_i[ereign_feld_id] in err_dict.keys():
                    # err_dict[ereign_ft_i[ereign_feld_id]].update(report_ereign_start_stop_msg)
                # else:
                    # err_dict[ereign_ft_i[ereign_feld_id]] = report_ereign_start_stop_msg
            # del report_ereign_start_stop_msg


        # def check_ereign_auf_linie(
            # ereign_ft_i,
            # gew_df,
            # ereign_benoetigte_felder,
            # ereign_feld_id,
            # err_df=None
        # ):
            # '''ueberprueft die Liniengeometrie eine Ereignisses'''
            # ereign_ft_i_name = ereign_ft_i[ereign_feld_id]
            # report_ereign_lage_dict = {}

            # # Stuetzpunkte des Ereignisobjekts
            # ereign_ft_i_vertices = [
                # [
                    # i,
                    # vtx
                # ] for i, vtx in enumerate(ereign_ft_i['geometry'].vertices())
            # ]
            # ereign_ft_i_vertices_df = pd.DataFrame(
                # ereign_ft_i_vertices,
                # columns = ['index', 'geometry']
            # )

            # # Stuetzpunkte des Gewaesserobjekts
            # gew_ft_i = gew_df.loc[gew_df[gew_feld_name]==ereign_ft_i[ereign_feld_gewname]]
            # gew_geom_i = gew_ft_i['geometry'].to_list() [0]
            # if len([p for p in gew_geom_i.parts()]) > 1:
                # feedback.reportError(
                    # str(ereign_ft_i[ereign_feld_gewname])
                    # +': Fehler - mehr als ein Gewässerteil (Multigeometrie)'
                # )
            # else:
                # gew_ft_i_vertices = [
                    # [
                        # i,
                        # vtx,
                        # round(gew_geom_i.distanceToVertex(i),2)
                    # ] for i, vtx in enumerate(gew_geom_i.vertices())
                # ]
                # gew_ft_i_vertices_df = pd.DataFrame(
                    # gew_ft_i_vertices,
                    # columns = ['index', 'geometry', 'station']
                # )
                # # Distanz zu Gewaesserstuetzpunkten
                # vtx_diff_text = ''  # Fehlertext
                # ereign_ft_i_vertices_df['index_of_gew_vtx'] = np.nan
                # ereign_ft_i_vertices_df['distance_to_gew_vtx'] = np.nan
                # for i, v_e in enumerate(ereign_ft_i_vertices_df['geometry']):
                    # vtx_distances = [v_e.distance(v_s) for v_s in gew_ft_i_vertices_df['geometry']]
                    # min_vtx_distance = min(vtx_distances)
                    # ereign_ft_i_vertices_df.loc[i,'distance_to_gew_vtx'] = min_vtx_distance
                    # ereign_ft_i_vertices_df.loc[i,'index_of_gew_vtx'] = vtx_distances.index(min_vtx_distance)
                # ereign_ft_i_vertices_df = ereign_ft_i_vertices_df.join(
                    # gew_ft_i_vertices_df['station'],
                    # on='index_of_gew_vtx'
                # )
                # ereign_ft_i_vertices_df = ereign_ft_i_vertices_df.rename(
                    # columns={'station': 'gew_station'}
                # )
                # if any (ereign_ft_i_vertices_df['distance_to_gew_vtx'] > toleranz_abw):
                    # ereign_abweichende_vtx = ereign_ft_i_vertices_df.loc[
                        # ereign_ft_i_vertices_df['distance_to_gew_vtx'] > toleranz_abw,
                        # ['index', 'distance_to_gew_vtx']
                    # ]
                    # vtx_diff_list = ereign_abweichende_vtx.apply(
                        # lambda x: '            '+str(int(x[0]))+': '+ str(x[1]), axis=1
                    # ).tolist()
                    # vtx_diff_text = (
                        # vtx_diff_text
                        # + '\n        Stützpunkt(e) des Ereignislayers nicht mit Gewässerstützpunkten übereinstimmend;'
                        # + ' Stützpunktnummer und Distanz:\n'
                        # + '\n'.join(vtx_diff_list)
                    # )
                # # Fehlende Stuetzpunkte
                # ereign_ft_i_vertices_df['gew_index_diff'] = ereign_ft_i_vertices_df['index_of_gew_vtx'].diff().fillna(1)
                # if any (ereign_ft_i_vertices_df['gew_index_diff'] > 1):
                    # ereign_fehlende_vtx = ereign_ft_i_vertices_df.loc[
                        # ereign_ft_i_vertices_df['gew_index_diff'] > 1,
                        # ['index', 'gew_index_diff']
                    # ]
                    # vtx_fehlend_list = ereign_fehlende_vtx.apply(
                        # lambda x: (
                            # '            zwischen Ereignis-Stützpunkt '
                            # + str(int(x[0] - 1)) 
                            # + ' und '
                            # + str(int(x[0]))
                            # +': '
                            # + str(int(x[1] - 1))
                            # + ' Stützpunkt(e)'
                        # ), axis=1
                    # ).tolist()
                    # vtx_diff_text = (
                        # vtx_diff_text
                        # + '\n        Fehlende Stützpunkte:\n'
                        # + '\n'.join(vtx_fehlend_list)
                    # )
                # if vtx_diff_text != '':
                    # report_ereign_lage_dict.update({
                        # 'Geometrie': vtx_diff_text
                    # })

            
            # # Stationierung korrekt?
            # if 'index_of_gew_vtx' in ereign_ft_i_vertices_df.columns:
                # if ereign_ft_i.geometry.type() == 1:  # Linie
                    # stat_von = ereign_ft_i[ereign_benoetigte_felder_ohneName[0]]
                    # stat_bis = ereign_ft_i[ereign_benoetigte_felder_ohneName[1]]
                    # if not stat_von == ereign_ft_i_vertices_df['gew_station'].to_list()[0]:
                        # stationierung_fehler_text = (
                            # stationierung_fehler_text 
                            # + '\n        Stationierung (von = '
                            # + str(stat_von)
                            # + ') nicht mit Stationierung am Stützpunkt des Gewässers übereinstimmend ('
                            # + str(ereign_ft_i_vertices_df['gew_station'].to_list()[0])
                            # + ')'
                        # )
                    # if not stat_bis == ereign_ft_i_vertices_df['gew_station'].to_list()[-1]:
                        # stationierung_fehler_text = (
                            # stationierung_fehler_text 
                            # + '\n        Stationierung (bis = '
                            # + str(stat_bis)
                            # + ') nicht mit Stationierung am Stützpunkt des Gewässers übereinstimmend ('
                            # + str(ereign_ft_i_vertices_df['gew_station'].to_list()[-1])
                            # + ')'
                        # )
                # else:  # Punkt
                    # pass


        # ereign_df.apply(
            # lambda x: check_ereign_auf_linie(
                # x,
                # gew_df,
                # ereign_benoetigte_felder,
                # ereign_feld_id,
                # err_df=None
            # ),
            # axis=1
        # )
        
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