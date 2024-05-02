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

class checkEreignisse(QgsProcessingAlgorithm):
    GEOM_TOLERANZ = 'GEOM_TOLERANZ'
    EREIGNIS_LAYER = 'EREIGN_LAYER'
    GEWAESSER_LAYER = 'GEWAESSER_LAYER'
    REPORT = 'REPORT'
    FELD_ID = 'FELD_ID'
    FELD_GEW_NAME = 'FELD_GEW_NAME'
    
    def name(self):
        return 'Pruefroutine_Ereignisse'

    def displayName(self):
        return 'Pruefroutine_Ereignisse'

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
        
        self.addParameter(
            QgsProcessingParameterField(
                self.FELD_ID,
                self.tr("Eindeutiger Ereignis-Objektname / ID / fid"),
                parentLayerParameterName = self.EREIGNIS_LAYER,
                defaultValue = 'fid',
                type = QgsProcessingParameterField.Any,
                optional = True
            )
        )

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
        ereign_layer = self.parameterAsVectorLayer(parameters, self.EREIGNIS_LAYER, context)
        gew_layer = self.parameterAsVectorLayer(parameters, self.GEWAESSER_LAYER, context)
        reportdatei = self.parameterAsString(parameters, self.REPORT, context)
        ereign_feld_id = self.parameterAsString(parameters, self.FELD_ID, context)

        
        # Festlegungen
        toleranz_abw = self.parameterAsDouble(parameters, self.GEOM_TOLERANZ, context)

        # Layerauswahl und Felder
        # Ereignislayer
        ereign_feld_gewname = 'BA_CD'
        ereign_feld_stat_punkt = 'STAT'
        ereign_feld_stat_linie_von = 'STAT_VON'
        ereign_feld_stat_linie_bis = 'STAT_BIS'
        ereign_feld_art = 'ART'

        # Gewaesserlayer
        gew_feld_name = 'BA_CD'
        gew_feld_stat_bis = 'BA_ST_BIS'

        # Prueffunktionen
        err_dict = {}
        def check_ereign_felder(ereign_layer, benoetigte_felder):
            '''
            Prüft, ob alle benoetigen Felder im Ereignslayer vorhanden sind
            :param QgsVectorLayer ereign_layer
            :param list benoetigte_felder
            :return: str
            '''
            err_felder = []
            report_err_felder = ''
            for f in benoetigte_felder:
                if f not in ereign_layer.fields().names():
                    err_felder = err_felder+[f]
            if len(err_felder) > 0:
                report_err_felder = (
                    'Fehlende Felder in Layer '
                    + str(ereign_layer.name())
                    +': '
                    +', '.join(err_felder)
                )
            return report_err_felder
            
        def check_ereign_gew_name(ereign_ft_i, gew_df, err_df=None):
            '''Prüft, ob das Feld des Gewässernamens richtig gefüllt sind'''
            report_ereign_start_stop_msg = {}
            gew_name = ereign_ft_i[ereign_feld_gewname]
            if gew_name == NULL:
                report_ereign_start_stop_msg.update({
                    'Feld '+ str(ereign_feld_gewname): 'Gewässername ist nicht angegeben.'
                })
            elif gew_name not in gew_df[gew_feld_name].to_list():
                report_ereign_start_stop_msg.update({
                    'Feld '+ str(ereign_feld_gewname): 'Gewässername \"'+gew_name+'\" nicht im Gewässerlayer vorhanden.'
                })
            else:
                pass
            if len(report_ereign_start_stop_msg) > 0:
                # naechstes Gewaesser finden
                sp_index = QgsSpatialIndex(
                    gew_layer.getFeatures(),
                    flags=QgsSpatialIndex.FlagStoreFeatureGeometries
                )
                if ereign_layer.geometryType() == 1: # Linie
                    if ereign_ft_i['geometry'].isMultipart():
                        gew_nearest_idx = sp_index.nearestNeighbor(
                            ereign_ft_i['geometry'].asMultiPolyline()[0][0]
                        )[0]
                    else:
                        gew_nearest_idx = sp_index.nearestNeighbor(
                            ereign_ft_i['geometry'].asPolyline()[0]
                        )[0]
                else: # Punkt
                    if ereign_ft_i['geometry'].isMultipart():
                        gew_nearest_idx = sp_index.nearestNeighbor(
                            ereign_ft_i['geometry'].asMultiPoint()[0]
                        )[0]
                    else:
                        gew_nearest_idx = sp_index.nearestNeighbor(
                            ereign_ft_i['geometry'].asPoint()
                        )[0]
                gew_nearest_ft = gew_df.loc[gew_df[ereign_feld_id]==gew_nearest_idx]
                gew_name = list(gew_nearest_ft[gew_feld_name])[0]
                
                # Report-Eintrag
                report_ereign_start_stop_msg['Feld '+ str(ereign_feld_gewname)] = (
                    report_ereign_start_stop_msg['Feld '+ str(ereign_feld_gewname)]
                    + ' Nächstgelegenes Gewässer: \"'
                    + str(gew_name)
                    + '\"'
                )
                if ereign_ft_i[ereign_feld_id] in err_dict.keys():
                    err_dict[ereign_ft_i[ereign_feld_id]].update(report_ereign_start_stop_msg)
                else:
                    err_dict[ereign_ft_i[ereign_feld_id]] = report_ereign_start_stop_msg
                del(report_ereign_start_stop_msg)
            return gew_name


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


        def check_ereign_auf_linie(
            ereign_ft_i,
            gew_df,
            ereign_benoetigte_felder,
            ereign_feld_id,
            err_df=None
        ):
            '''ueberprueft die Liniengeometrie eine Ereignisses'''
            ereign_ft_i_name = ereign_ft_i[ereign_feld_id]
            report_ereign_lage_dict = {}

            # Stuetzpunkte des Ereignisobjekts
            ereign_ft_i_vertices = [
                [
                    i,
                    vtx
                ] for i, vtx in enumerate(ereign_ft_i['geometry'].vertices())
            ]
            ereign_ft_i_vertices_df = pd.DataFrame(
                ereign_ft_i_vertices,
                columns = ['index', 'geometry']
            )

            # Stuetzpunkte des Gewaesserobjekts
            gew_ft_i = gew_df.loc[gew_df[gew_feld_name]==ereign_ft_i[ereign_feld_gewname]]
            gew_geom_i = gew_ft_i['geometry'].to_list() [0]
            if len([p for p in gew_geom_i.parts()]) > 1:
                feedback.reportError(
                    str(ereign_ft_i[ereign_feld_gewname])
                    +': Fehler - mehr als ein Gewässerteil (Multigeometrie)'
                )
            else:
                gew_ft_i_vertices = [
                    [
                        i,
                        vtx,
                        round(gew_geom_i.distanceToVertex(i),2)
                    ] for i, vtx in enumerate(gew_geom_i.vertices())
                ]
                gew_ft_i_vertices_df = pd.DataFrame(
                    gew_ft_i_vertices,
                    columns = ['index', 'geometry', 'station']
                )
                # Distanz zu Gewaesserstuetzpunkten
                vtx_diff_text = ''  # Fehlertext
                ereign_ft_i_vertices_df['index_of_gew_vtx'] = np.nan
                ereign_ft_i_vertices_df['distance_to_gew_vtx'] = np.nan
                for i, v_e in enumerate(ereign_ft_i_vertices_df['geometry']):
                    vtx_distances = [v_e.distance(v_s) for v_s in gew_ft_i_vertices_df['geometry']]
                    min_vtx_distance = min(vtx_distances)
                    ereign_ft_i_vertices_df.loc[i,'distance_to_gew_vtx'] = min_vtx_distance
                    ereign_ft_i_vertices_df.loc[i,'index_of_gew_vtx'] = vtx_distances.index(min_vtx_distance)
                ereign_ft_i_vertices_df = ereign_ft_i_vertices_df.join(
                    gew_ft_i_vertices_df['station'],
                    on='index_of_gew_vtx'
                )
                ereign_ft_i_vertices_df = ereign_ft_i_vertices_df.rename(
                    columns={'station': 'gew_station'}
                )
                if any (ereign_ft_i_vertices_df['distance_to_gew_vtx'] > toleranz_abw):
                    ereign_abweichende_vtx = ereign_ft_i_vertices_df.loc[
                        ereign_ft_i_vertices_df['distance_to_gew_vtx'] > toleranz_abw,
                        ['index', 'distance_to_gew_vtx']
                    ]
                    vtx_diff_list = ereign_abweichende_vtx.apply(
                        lambda x: '            '+str(int(x[0]))+': '+ str(x[1]), axis=1
                    ).tolist()
                    vtx_diff_text = (
                        vtx_diff_text
                        + '\n        Stützpunkt(e) des Ereignislayers nicht mit Gewässerstützpunkten übereinstimmend;'
                        + ' Stützpunktnummer und Distanz:\n'
                        + '\n'.join(vtx_diff_list)
                    )
                # Fehlende Stuetzpunkte
                ereign_ft_i_vertices_df['gew_index_diff'] = ereign_ft_i_vertices_df['index_of_gew_vtx'].diff().fillna(1)
                if any (ereign_ft_i_vertices_df['gew_index_diff'] > 1):
                    ereign_fehlende_vtx = ereign_ft_i_vertices_df.loc[
                        ereign_ft_i_vertices_df['gew_index_diff'] > 1,
                        ['index', 'gew_index_diff']
                    ]
                    vtx_fehlend_list = ereign_fehlende_vtx.apply(
                        lambda x: (
                            '            zwischen Ereignis-Stützpunkt '
                            + str(int(x[0] - 1)) 
                            + ' und '
                            + str(int(x[0]))
                            +': '
                            + str(int(x[1] - 1))
                            + ' Stützpunkt(e)'
                        ), axis=1
                    ).tolist()
                    vtx_diff_text = (
                        vtx_diff_text
                        + '\n        Fehlende Stützpunkte:\n'
                        + '\n'.join(vtx_fehlend_list)
                    )
                if vtx_diff_text != '':
                    report_ereign_lage_dict.update({
                        'Geometrie': vtx_diff_text
                    })

            # Stationierung angegeben?
            stationierung_fehler_text = ''
            ereign_benoetigte_felder_ohneName = ereign_benoetigte_felder[1:]
            for feld in ereign_benoetigte_felder_ohneName:
                if ereign_ft_i[feld] == NULL:
                    stationierung_fehler_text = stationierung_fehler_text + '    Fehlende Angabe für \"'+feld+'\" \n'
            
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
            if stationierung_fehler_text != '':
                report_ereign_lage_dict.update({
                    'Stationierung': stationierung_fehler_text
                })

            if len(report_ereign_lage_dict) > 0:
                if ereign_ft_i[ereign_feld_id] in err_dict.keys():
                    err_dict[ereign_ft_i_name].update(report_ereign_lage_dict)
                else:
                    err_dict[ereign_ft_i_name] = report_ereign_lage_dict


        # Ereignisdaten
        err_df = pd.DataFrame()
        
        # Spalten im Ereignislayer vorhanden?
        if ereign_layer.geometryType() == 1:  # Linie
            ereign_benoetigte_felder = [
                ereign_feld_gewname,
                ereign_feld_stat_linie_von,
                ereign_feld_stat_linie_bis
            ]
        else:  # Punkt
            ereign_benoetigte_felder = [
                    ereign_feld_gewname,
                    ereign_feld_stat_punkt
                ]
        report_err_felder = check_ereign_felder(ereign_layer, ereign_benoetigte_felder)

        # df erzeugen
        if report_err_felder == '':  # keine fehlenden Spalten
            # zuerst fuer den Ereignis-Layer
            if ereign_feld_id in ereign_layer.fields().names():
                datagen = (
                    [ft[ereign_feld_id]] 
                    + [ft[feld] for feld in ereign_benoetigte_felder] 
                    + [ft.geometry()] for ft in ereign_layer.getFeatures()
                )
            else:
                datagen = (
                    [ft.id()] 
                    + [ft[feld] for feld in ereign_df_felder] 
                    + [ft.geometry()] for ft in ereign_layer.getFeatures()
                )
                ereign_feld_id = 'fid'
            ereign_df_felder = [ereign_feld_id] + ereign_benoetigte_felder + ['geometry']

            ereign_df = pd.DataFrame.from_records(
                data=datagen,
                columns=ereign_df_felder
            )

            # Dann fuer den Gewaesser-Layer
            gew_spaltennamen = [
                'fid',
                gew_feld_name,
                'geometry'
            ]
            datagen = (
                [
                    ft.id(),
                    ft[gew_feld_name],
                    ft.geometry()
                ] for ft in gew_layer.getFeatures()
            )
            gew_df = pd.DataFrame.from_records(
                data=datagen,
                columns=gew_spaltennamen
            )
            
            # Gewaessername (ba_cd) pruefen
            ereign_df[ereign_feld_gewname] = ereign_df.apply(
                lambda x: check_ereign_gew_name(x, gew_df),
                axis=1
            )
        
        ereign_df.apply(
            lambda x: check_ereign_auf_linie(
                x,
                gew_df,
                ereign_benoetigte_felder,
                ereign_feld_id,
                err_df=None
            ),
            axis=1
        )

        with open(reportdatei, 'w') as f:
            f.write(
                '*******************************************************'
                + '\nÜberprüfung der Objekte (Ereignisse) auf einem Gewässer'
                + '\n\n- Ereignislayer: ' + str(ereign_layer)
                + '\n- Gewässerlayer: ' + str(gew_layer)
                + '\n*******************************************************\n\n'
            )
            
            if report_err_felder != '':
                f.write(report_err_felder)
            if len(err_dict) > 0:
                if ereign_feld_id in ereign_layer.fields().names(): 
                    f.write(
                        'Gefundene Fehler (Objekte sind anhand des Feldes \"'+ereign_feld_id+'\" bezeichnet):\n'
                        + '----------------\n'
                    )
                else:
                    f.write(
                        'Gefundene Fehler (Objekte sind mit ihrer id (Feldrechner: $id() ) bezeichnet):\n'
                        + '----------------\n'
                    )
                for key, value in err_dict.items():
                    if isinstance(value, dict):
                        if len(value) > 1:
                            f.write('- '+str(key)+': \n')
                        else:
                            f.write('- '+str(key)+':')
                        for k2, v2 in value.items():
                            f.write(
                                '    '+str(k2) +': '+ str(v2) + '\n'
                            )
                    else:
                        f.write(
                            '- '+str(key) +': '+ str(value) + '\n'
                        )
            if len(report_err_felder) == 0 and len(err_dict) == 0:
                f.write('keine Fehler gefunden')

        feedback.pushInfo('Report gespeichert in ' + str(reportdatei)+ '\n')
        err_felder = []
        report_err_felder = ''
        err_dict = {}
        return {}