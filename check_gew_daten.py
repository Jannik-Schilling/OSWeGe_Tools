# -*- coding: utf-8 -*-

"""
/***************************************************************************
 OSWeGe-Tools - a QGIS plugin
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-04-09
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

__author__ = 'Jannik Schilling'
__date__ = '2024-04-09'
__copyright__ = '(C) 2024 by Jannik Schilling'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import pandas as pd
import os

from qgis.PyQt.QtCore import (
    QCoreApplication
)
from qgis.core import (
    NULL,
    Qgis,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex,
    QgsWkbTypes,
)
from qgis import processing

from .defaults import (
    list_ereign_gew_id_fields,
    output_layer_prefixes,
    pflichtfelder,
)
from .pruefungsroutinen import (
    check_duplicates_crossings,
    check_geometrie_wasserscheide_senke,
    check_geom_on_line,
    check_overlap_by_stat,
    check_vtx_distance,
)

from .check_gew_report import (
    clean_report_dict,
    create_report_dict,
    create_layers_from_report_dict,
    replace_lst_ids,
    save_layer_to_file
)

from .hilfsfunktionen import (
    dict_log,
    get_line_to_check,
    log_time
)

class checkGewaesserDaten(QgsProcessingAlgorithm):
    """
    Prueft Gewaesserdaten
    """
    LAYER_GEWAESSER = 'LAYER_GEWAESSER'
    LAYER_ROHLEITUNGEN = 'LAYER_ROHLEITUNGEN'
    LAYER_DURCHLAESSE = 'LAYER_DURCHLAESSE'
    LAYER_WEHRE = 'LAYER_WEHRE'
    LAYER_SCHAECHTE = 'LAYER_SCHAECHTE'
    REPORT = 'REPORT'
    REPORT_OUT = 'REPORT_OUT'
    
    if (int(Qgis.version().split('.')[1]) >= 36) or (int(Qgis.version().split('.')[0]) > 3):
        newer_qgis_version = True
    else:
        newer_qgis_version = False
 
    def initAlgorithm(self, config):
        """
        Definition von Input und Output des Werkzeugs
        """
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.LAYER_GEWAESSER,
                self.tr('Gewässer-Layer'),
                [QgsProcessing.SourceType.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.LAYER_ROHLEITUNGEN,
                self.tr('Rohrleitungs-Layer'),
                [QgsProcessing.SourceType.TypeVectorLine],
                optional = True
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.LAYER_DURCHLAESSE,
                self.tr('Durchlässe-Layer'),
                [QgsProcessing.SourceType.TypeVectorLine],
                optional = True
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.LAYER_WEHRE,
                self.tr('Wehre-Layer'),
                [QgsProcessing.SourceType.TypeVectorPoint],
                optional = True
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.LAYER_SCHAECHTE,
                self.tr('Schächte-Layer'),
                [QgsProcessing.SourceType.TypeVectorPoint],
                optional = True
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.REPORT,
                self.tr('Reportdatei'),
                'Geopackage (*.gpkg)'                #'Textdatei (*.txt)',
            )
        )
        if not self.newer_qgis_version:
            self.addOutput(
                QgsProcessingOutputFile(
                    self.REPORT_OUT,
                    self.tr('Reportdatei: Geopackage File(*.gpkg)')
                )
            ) 

    def processAlgorithm(self, parameters, context, feedback):
        """
        Hier findet die Verarbeitung statt
        """
        # Festlegung für Tests 
        test_output_all = False  # Ueberspringt das bereinigen des report_dict, wenn True
        is_test_version = False  # Hinweis zum Output, Ausgabe der Zeiten, wenn True

        # Layerdefinitionen
        layer_gew = self.parameterAsVectorLayer(parameters, self.LAYER_GEWAESSER, context)
        layer_rohrleitungen = self.parameterAsVectorLayer(parameters, self.LAYER_ROHLEITUNGEN, context)
        layer_durchlaesse = self.parameterAsVectorLayer(parameters, self.LAYER_DURCHLAESSE, context)
        layer_wehre = self.parameterAsVectorLayer(parameters, self.LAYER_WEHRE, context)
        layer_schaechte = self.parameterAsVectorLayer(parameters, self.LAYER_SCHAECHTE, context)
        reportdatei = self.parameterAsString(parameters, self.REPORT, context)
        
        if os.path.isfile(reportdatei):
            raise QgsProcessingException('Die Datei '+reportdatei
            + ' existiert bereits. Bitte einen anderen Dateinamen wählen.')

        # Zusammenfassendes dictionary fuer Prozessparameter, die an Funktionen uebergeben werden
        feedback.setProgressText('Vorbereitung der Tests')
        log_time('Vorbereitung der Tests', is_start=True)
        layer_dict = {}
        list_crs = []
        list_layer_types = [
            'gewaesser',
            'rohrleitungen',
            'durchlaesse',
            'wehre',
            'schaechte'
        ]  # wichtig für die Reihenfolge der Tests; in dictionaries kann diese variieren (!)
        for layer_typ, layer in zip(
            list_layer_types ,
            [
                layer_gew,
                layer_rohrleitungen,
                layer_durchlaesse,
                layer_wehre,
                layer_schaechte,
            ]
        ):
            if layer:
                list_crs.append(layer.crs().authid())
                layer_dict[layer_typ] = {'layer': layer}
        if len(set(list_crs)) == 1:
            crs_out = list_crs[0]  # fuer die Ergebnisausgabe
        else:
            raise QgsProcessingException(
                'Alle Layer müssen im gleichen Koordinatenbezugssystem gespeichert sein!'
            )

        # Dictionary fuer immer wiederkehrende Parameter
        params = {
            'layer_dict': layer_dict,  # zu pruefende Parameter
            'feedback': feedback,  # QgsProcessingFeedback fuer Statusinfos waehrend des Durchlaufs
            'ereign_gew_id_field': list_ereign_gew_id_fields[1],  # Name des Felds mit dem Primaerschluessel: "gu_cd" oder "ba_cd"
            'gew_primary_key_missing': False,
            'field_merged_id': 'merged_id',  # Feldname fuer neue ID, wenn rl und dl vorhanden
            'emptystrdef': [NULL, ''],  # moegliche "Leer"-Definitionen für Zeichenketten
            'n_layer': len(layer_dict) # Anzahl der zu bearbeitenden Layer
        }

        # dictionary fuer Feedback / Fehlermeldungen
        report_dict = create_report_dict(params)


        # rl und dl zusammenfassen fuer gemeinsame Auswertung, wenn beide vorhanden
        if layer_rohrleitungen and layer_durchlaesse:
            log_time('Zusammenfassen')
            # neues Feld "merged_id" mit dem Layername und der id() des Objekts,
            # weil sich die id() beim Vereinigen der Layer aendert
            rl_mit_id = processing.run(
                "native:fieldcalculator", {
                    'INPUT': params['layer_dict']['rohrleitungen']['layer'],
                    'FIELD_NAME': params['field_merged_id'],
                    'FIELD_TYPE': 2,
                    'FORMULA': "concat(@layer_name,': ',$id)",
                    'OUTPUT': 'memory:'
                }
            )['OUTPUT']
            dl_mit_id = processing.run(
                "native:fieldcalculator", {
                    'INPUT': params['layer_dict']['durchlaesse']['layer'],
                    'FIELD_NAME': params['field_merged_id'],
                    'FIELD_TYPE': 2,
                    'FORMULA': "concat(@layer_name,': ',$id)",
                    'OUTPUT': 'memory:'
                }
            )['OUTPUT']

            # Vereinigen der layer rl und dl für Überschneidungsanalyse
            layer_rldl = processing.run(
                "native:mergevectorlayers",
                {
                    'LAYERS': [rl_mit_id, dl_mit_id],
                    'OUTPUT':'memory:'
                }
            )['OUTPUT']

            # Zu Params: Anzeige, ob die Pruefroutinen des Layers schon durchlaufen wurden
            params['layer_rldl'] = {
                'layer': layer_rldl,
                'runs': {  
                    'check_duplicates_crossings': False,  
                    'check_geom_ereign_auf_gew': False,
                    'check_overlap_by_stat': False
                },
            }
            report_dict['layer_rldl'] = {'geometrien':{}}
        feedback.setProgressText('Abgeschlossen \n ')
        log_time('Vorbereitung')


        # Hauptfunktion
        def main_check(
            key,
            report_dict,
            params,
            feedback,
            i_run
        ):
            """
            Diese Hauptfunktion wird durchlaufen, um die Vektorobjekte alle Layer zu pruefen (Attribute + Geometrien)
            :param str key
            :param dict report_dict
            :param dict params
            :param QgsProcessingFeedback feedback
            :param int i_run: Zaehler fuers feedback
            """
            layer = params['layer_dict'][key]['layer']
            feedback.setProgressText(
                output_layer_prefixes[key] + '-Layer \"'
                + layer.name() + '\" (' + str(i_run+1) + '/'
                + str(params['n_layer'])
                + '):')
            layer_steps = params['layer_dict'][key]['steps']

            # Sind die pflichtfelder vorhanden?
            feedback.setProgressText('> Prüfe benötigte Attributfelder...')
            pflichtfelder_i = pflichtfelder[key]
            layer_i_felder = layer.fields().names()
            missing_fields = [
                feld for feld in pflichtfelder_i if not feld in layer_i_felder
            ]
            ereign_gew_id_field = params['ereign_gew_id_field']
            if len(missing_fields) > 0:
                report_dict[key]['attribute']['missing_fields'] = missing_fields
                if key == 'gewaesser' and ereign_gew_id_field in missing_fields:
                    params['gew_primary_key_missing'] = True

            # Pruefroutinen fuer Attribute
            feedback.setProgressText('> Prüfe alle Einzelobjekte...')
            if ereign_gew_id_field in missing_fields:
                prim_text = 'Primärschlüssel' if key == 'gewaesser' else 'Fremdschlüssel'
                feedback.pushWarning(
                   'Feld \"' + ereign_gew_id_field + '\" ('
                   + prim_text +' des Gewässers) fehlt. '
                   + 'Der Attributtest für dieses Feld wird übersprungen'
                )
            else:
                feedback.setProgressText('-- Attribute')
                log_time((key+'_Attr'))
                if key == 'gewaesser':
                    list_primary_key_empty = []
                    prim_key_dict = {}
                    for i, feature in enumerate(layer.getFeatures()):
                        feedback.setProgress(int((i+1) * layer_steps))
                        if feedback.isCanceled():
                            break
                        ft_key = feature.attribute(ereign_gew_id_field)
                        if ft_key in params['emptystrdef']:
                            # fehlender Primaerschluessel
                            list_primary_key_empty.append(feature.id())
                        else:
                            # mehrfache Primaerschluessel ? -> Liste an eindeutigen keys
                            if ft_key in prim_key_dict.keys():
                                prim_key_dict[ft_key].append(feature.id())
                            else:
                                prim_key_dict[ft_key] = [feature.id()]
                    list_primary_key_duplicat = [
                        lst for lst in prim_key_dict.values() if len(lst) > 1
                    ]
                    if len(list_primary_key_empty) > 0:
                        report_dict[key]['attribute']['primary_key_empty'] = list_primary_key_empty
                    if len(list_primary_key_duplicat) > 0:
                        report_dict[key]['attribute']['primary_key_duplicat'] = list_primary_key_duplicat

                else:  # Attributtest für Ereignisse
                    list_gew_key_empty = []
                    list_gew_key_invalid = []
                    layer_gew = params['layer_dict']['gewaesser']['layer']
                    if params['gew_primary_key_missing']:
                        feedback.pushWarning(
                            'Die Zuordnung der Ereignisse über den Gewässernamen kann '
                            + 'nicht geprüft werden, weil das Feld \"'
                            + ereign_gew_id_field
                            + '\" im Gewässerlayer fehlt.'
                        )
                    else:
                        list_gew_keys = [
                            gew_ft.attribute(ereign_gew_id_field) for gew_ft in layer_gew.getFeatures()
                        ]
                        for i, feature in enumerate(layer.getFeatures()):
                            feedback.setProgress(int((i+1) * layer_steps))
                            if feedback.isCanceled():
                                break
                            ft_key = feature.attribute(ereign_gew_id_field)
                            if ft_key in params['emptystrdef']:
                                # fehlender Gewaesserschluessel
                                list_gew_key_empty.append(feature.id())
                            else:
                                if not ft_key in list_gew_keys:
                                    # Der angegebene Gewaesserschluessel(=Gewaessername)
                                    # ist nicht im Gewaesserlayer vergeben
                                    list_gew_key_invalid.append(feature.id())
                        if len(list_gew_key_empty) > 0:
                            report_dict[key]['attribute']['gew_key_empty'] = list_gew_key_empty
                        if len(list_gew_key_invalid) > 0:
                            report_dict[key]['attribute']['gew_key_invalid'] = list_gew_key_invalid
                log_time((key+'_Attr_write'))

            # Pruefroutinen fuer Geometrien
            feedback.setProgressText('-- Geometrien')
            layer_steps = params['layer_dict'][key]['steps']

            # fuer alle Layer: 
            """Diese pruefungsroutinen ggf als Funktion, um Tests zu schreiben"""
            list_geom_is_empty = []
            list_geom_is_multi = []
            list_geom_sefintersect = []
            feedback.setProgressText(
                '--- Leere und Multigeometrien, Selbstüberschneidungen'
            )
            for i, feature in enumerate(layer.getFeatures()):
                feedback.setProgress(int((i+1) * layer_steps))
                if feedback.isCanceled():
                    break
                geom = feature.geometry()
                if geom.isEmpty() or geom.isNull():
                    # Leer?
                    list_geom_is_empty.append(feature.id())
                else:
                    # Multi?
                    if geom.isMultipart():
                        polygeom = geom.asMultiPolyline() 
                    else:
                        polygeom = [f for f in geom.parts()]
                    if len(polygeom) > 1:
                        list_geom_is_multi.append(feature.id())
                # Selbstueberschneidungen
                    if not geom.isSimple():
                        list_geom_sefintersect.append(feature.id())
            log_time((key+'_geom_leer_etc'))
            # write to report dict
            for fehl_typ, fehl_lst in zip([
                'geom_is_empty',
                'geom_is_multi',
                'geom_selfintersect'
            ],[
                list_geom_is_empty,
                list_geom_is_multi,
                list_geom_sefintersect
            ]):
                if len(fehl_lst)>0:
                    df_i = pd.DataFrame({fehl_typ: fehl_lst})
                    report_dict[key]['geometrien'][fehl_typ] = df_i 
            log_time((key+'_geom_leer_etc_write'))


            feedback.setProgressText('--- Duplikate und Überschneidungen')
            if not ((key in ['rohrleitungen', 'durchlaesse']) and ('layer_rldl' in params.keys())):
                # Normalfall
                df_geom_crossings, df_geom_duplicate = check_duplicates_crossings(
                    layer,
                    feedback,
                    layer_steps
                )
                log_time((key+'_geom_dup_cro'))
                if len(df_geom_crossings) > 0:
                    report_dict[key]['geometrien']['geom_crossings'] = df_geom_crossings
                if len(df_geom_duplicate) > 0:
                    report_dict[key]['geometrien']['geom_duplicate'] = df_geom_duplicate
                log_time((key+'_geom_dup_cro_write'))
            else:
                if not params['layer_rldl']['runs']['check_duplicates_crossings']:  # falls es nicht schon einmal durchlaufen wurde
                    layer_rldl = params['layer_rldl']['layer']
                    layer_steps_rldl = 100/layer_rldl.featureCount()
                    df_geom_crossings, df_geom_duplicate = check_duplicates_crossings(
                        layer_rldl,
                        feedback,
                        layer_steps_rldl
                    )
                    log_time((key+'_geom_dup_cro_rldl'))
                    dict_alternative_id = {
                        feature.id(): feature[params['field_merged_id']] for feature in layer_rldl.getFeatures()
                    }
                    
                    # Ersetzen der IDs des Layers rl_dl durch die urspruenglichen (layer RL und layer DL) 
                    df_geom_crossings_adjusted = df_geom_crossings.apply(lambda x: replace_lst_ids(x, dict_alternative_id), axis=1)
                    df_geom_duplicate_adjusted = df_geom_duplicate.apply(lambda x: replace_lst_ids(x, dict_alternative_id), axis=1)

                    if len(df_geom_crossings_adjusted) > 0:
                        report_dict['layer_rldl']['geometrien']['geom_crossings'] = df_geom_crossings_adjusted
                    if len(df_geom_duplicate_adjusted) > 0:
                        report_dict['layer_rldl']['geometrien']['geom_duplicate'] = df_geom_duplicate_adjusted
                    params['layer_rldl']['runs']['check_duplicates_crossings'] = True
                    log_time((key+'_geom_dup_cro_rldl_write'))


            if key == 'gewaesser':
                feedback.setProgressText('--- Wasserscheiden, Senken')
                # Listen fuer das einmalige Durchlaufen der Funktion
                visited_features_wassersch = []
                visited_features_senken = []
                # Listen fuer die Ergebnisse
                list_geom_wassersch = []
                list_geom_senken = []
                # Da Objekte im Gew.-Layer gesucht werden, ist der andere 
                # Spatial Index auch der des Gewaesserlayers
                spatial_index_other = QgsSpatialIndex(layer.getFeatures())
                for i, feature in enumerate(layer.getFeatures()):
                    feedback.setProgress(int((i+1) * layer_steps))
                    if feedback.isCanceled():
                        break
                    geom = feature.geometry()
                    feature_id = feature.id()
                    if geom:
                        if not feature_id in visited_features_wassersch:
                            wasserscheiden = check_geometrie_wasserscheide_senke(
                                geom,
                                feature_id,
                                layer,
                                spatial_index_other
                            )
                            if wasserscheiden:
                                list_geom_wassersch.append(wasserscheiden)
                                visited_features_wassersch = list(
                                    set(visited_features_wassersch + wasserscheiden[:-1][0])  # die Geometrie wird nicht eingetragen
                                )
                        if not feature_id in visited_features_senken:
                            senken = check_geometrie_wasserscheide_senke(
                                geom,
                                feature_id,
                                layer,
                                spatial_index_other,
                                senke=True
                            )
                            if senken:
                                list_geom_senken.append(senken)
                                visited_features_senken = list(
                                    set(visited_features_senken + senken[:-1][0])  # die Geometrie wird nicht eingetragen
                                )
                log_time((key+'_geom_wassersc'))
                if len(list_geom_wassersch) > 0:
                    report_dict[key]['geometrien']['wasserscheiden'] = pd.DataFrame(list_geom_wassersch, columns = ['feature_id','geometry'])
                if len(list_geom_wassersch) > 0:
                    report_dict[key]['geometrien']['senken'] = pd.DataFrame(list_geom_senken, columns = ['feature_id','geometry'])
                log_time((key+'_geom_wassersc_write'))

            else:  # Ereignisse
                layer_gew = params['layer_dict']['gewaesser']['layer']
                spatial_index_other = QgsSpatialIndex(layer_gew.getFeatures())
                if not ((key in ['rohrleitungen', 'durchlaesse']) and ('layer_rldl' in params.keys())):
                    # Normalfall
                    key_temp = key
                    layer_temp = layer
                    layer_step_temp = layer_steps
                    normal_case = True
                else:
                    # Durchlauf mit rldl
                    key_temp = 'layer_rldl'
                    layer_temp = params['layer_rldl']['layer']
                    layer_step_temp = 100/layer_temp.featureCount()
                    normal_case = False
                if normal_case or (not params['layer_rldl']['runs']['check_geom_ereign_auf_gew']):  # Falls normal oder noch nicht durchlaufen
                    feedback.setProgressText('--- Korrekte Lage von Ereignissen auf Gewässern')
                    list_vtx_bericht = []
                    if not normal_case:
                        # Setze den Parameter auf True, damit der Test 
                        # nicht noch einmal mit rldl durchlaufen wird:
                        params['layer_rldl']['runs']['check_geom_ereign_auf_gew'] = True
                    for i, feature in enumerate(layer_temp.getFeatures()):
                        if feedback.isCanceled():
                            break
                        feedback.setProgress(int((i+1) * layer_step_temp))
                        if normal_case:
                            feature_id_temp = feature.id()
                        else:
                            feature_id_temp = feature[params['field_merged_id']]  # id + layername
                        geom = feature.geometry()
                        if not geom:
                            pass
                        elif feature_id_temp in list_geom_is_multi: 
                            pass
                        else:
                            series_vtx_bericht = pd.Series()
                            #Linie / Punkt auf Gewaesserlinie ?
                            if layer_temp.geometryType() == QgsWkbTypes.PointGeometry:  # Point
                                series_vtx_bericht['feature_id'] = feature_id_temp
                                line_feature = get_line_to_check(geom, layer_gew, spatial_index_other)
                                if line_feature:
                                    if not check_vtx_distance(geom, line_feature.geometry()):
                                        # Distanz zum naechsten Gewaesser zu gross
                                        series_vtx_bericht['Lage'] = 1
                                    else:
                                        # korrekt
                                        series_vtx_bericht['Lage'] = 0  # hier spaeter noch die Stationierung
                                else:
                                    # kein Gewaesser in der Naehe gefunden
                                    series_vtx_bericht['Lage'] = 1
                            else:  # Line
                                series_vtx_bericht = check_geom_on_line(
                                    geom,
                                    feature_id_temp,
                                    layer_gew,
                                    spatial_index_other,
                                    with_stat=True
                                )
                                series_vtx_bericht['feature_id'] = feature_id_temp
                            series_vtx_bericht['geometry'] = geom
                        list_vtx_bericht = list_vtx_bericht + [series_vtx_bericht]
                    #### TODO sort, so dass geometry hinten ist
                    report_dict[key_temp]['geometrien']['geom_ereign_auf_gew'] = pd.DataFrame(list_vtx_bericht)
                log_time((key+'_geom_auf_gew'))

                # Ueberlappungsanalyse (nur bei Linien)
                if not layer_temp.geometryType() == QgsWkbTypes.PointGeometry:  
                    if normal_case or (not params['layer_rldl']['runs']['check_overlap_by_stat']):
                        feedback.setProgressText('--- Überlappungen')
                        if not normal_case:
                            # Setze den Parameter auf True, damit der Test 
                            # nicht noch einmal mit rldl durchlaufen wird:
                            params['layer_rldl']['runs']['check_overlap_by_stat'] = True
                        list_overlap = check_overlap_by_stat(params, report_dict, layer_step_temp)
                        if len(list_overlap) > 0:
                            df_overlap = pd.DataFrame(list_overlap, columns = ['id1', 'id2', 'geometry'])    
                            report_dict[key_temp]['geometrien']['geom_overlap'] = df_overlap
                log_time((key+'_geom_ueberlappungen'))

                # Liegen Schaechte korrekt auf RL oder DL?
                if key == 'schaechte':
                    if 'layer_rldl' in params.keys():
                        other_layer = params['layer_rldl']['layer']
                    elif 'rohrleitungen' in report_dict.keys():
                        other_layer = params['layer_dict']['rohrleitungen']['layer']
                    elif 'durchlaesse' in report_dict.keys():
                        other_layer = params['layer_dict']['durchlaesse']['layer']
                    else:
                        other_layer = None
                    if not other_layer:
                        feedback.pushWarning(
                            ' (Prüfung der Lage von Schächten an/auf '
                            + 'Rohrleitungen und Durchlässen wird übersprungen: '
                            + 'Kein(e) Layer für Rohrleitungen und Durchlässe)'
                        )
                    else:
                        spatial_index_other =  QgsSpatialIndex(other_layer.getFeatures())
                        feedback.setProgressText(
                            '--- Korrekte Lage von Schächten an/auf '
                            + 'Rohrleitungen und Durchlässen'
                        )
                        list_schacht_rldl = []
                        
                        # Der DataFrame mit der Lageueberpruefung der Schaechte auf dem Gewaesser
                        df_schacht_auf_gw = (
                            report_dict
                                [key]
                                ['geometrien']
                                ['geom_ereign_auf_gew']
                        )

                        # Nun fuer jeden Schacht pruefen
                        for i, feature in enumerate(layer.getFeatures()):
                            # Feedback
                            feedback.setProgress(int((i+1) * layer_steps))
                            if feedback.isCanceled():
                                break
                            
                            # Objektgeometrie und ID:
                            geom = feature.geometry()
                            feature_id = feature.id()
                            
                            # Multi- oder Leetre Geometrien koennen nicht ueberprueft werden
                            if (not geom) or feature_id in list_geom_is_multi:
                                continue
                                
                            # Die Rohrleitung oder der Durchlass, auf dem der Schacht liegen soll:
                            line_feature = get_line_to_check(geom, other_layer, spatial_index_other)
                            if line_feature:
                                schacht_auf_rldl = check_vtx_distance(
                                    geom,
                                    line_feature.geometry()
                                )
                            else:
                                schacht_auf_rldl = False
                                
                            
                            fehler_auf_gew = df_schacht_auf_gw.loc[
                                df_schacht_auf_gw[
                                    'feature_id']==feature_id,
                                    'Lage'
                            ].values[0]
                            if schacht_auf_rldl and (not fehler_auf_gew):
                                # korrekt
                                pass
                            elif (not fehler_auf_gew) and (not schacht_auf_rldl):
                                # Fehler: schacht auf offenem gewaesser
                                list_schacht_rldl = list_schacht_rldl + [[feature_id, 1, geom]]
                            elif fehler_auf_gew and schacht_auf_rldl:
                                # Fehler: rldl verschoben
                                list_schacht_rldl = list_schacht_rldl + [[feature_id, 2, geom]]
                            else:
                                # Fehler: schacht weder auf gewaesser noch auf rldl
                                list_schacht_rldl = list_schacht_rldl + [[feature_id, 3, geom]]
                        log_time((key+'_geom_sch_auf_rldl'))
                        
                        # Das Ergebnis als DataFrame in report_dict ablegen
                        report_dict[key]['geometrien']['geom_schacht_auf_rldl'] = pd.DataFrame(
                            list_schacht_rldl, columns = [
                                'feature_id',
                                'Lage_rldl',
                                'geometry'
                            ]
                        )
                        log_time((key+'_geom_sch_auf_rldl_write'))
            feedback.setProgressText('Abgeschlossen \n ')

        # run test
        feedback.setProgressText('Tests fuer einzelne Layer')
        feedback.setProgressText('-------------------------')
        i = 0
        for key in list_layer_types:
            if key in report_dict.keys():
                main_check(
                    key,
                    report_dict,
                    params,
                    feedback,
                    i
                )
                i = i+1


        # Ausgabe:
        # 1 report_dict bereinigen
        if not test_output_all:
            feedback.setProgressText('Bereinige Fehlerliste...')
            clean_report_dict(report_dict, feedback)
            feedback.setProgressText('Abgeschlossen \n ')


        # 2 Ausgabe schreiben
        feedback.setProgressText('Generiere Layer / Ausgabe...')
        vector_layer_list, list_messages = create_layers_from_report_dict(
            report_dict,
            crs_out, feedback
        )
        feedback.setProgressText('Abgeschlossen \n ')
        
        if len(vector_layer_list) > 0:
            feedback.setProgressText('Speichere Layer in Datei...')
            save_layer_to_file(vector_layer_list, reportdatei)   
            feedback.setProgressText('Abgeschlossen \n ')     
            log_time('WriteLayer')
        
        
        if is_test_version:
            feedback.setProgressText(' \nDauer der Schritte:')
            timing_txt = [str(k)+': '+str(v) for k, v in dict_log.items() if k != 'current']
            feedback.setProgressText('\n'.join(timing_txt))
        
        # 3 Feedback
        if self.newer_qgis_version:
            feedback.pushFormattedMessage(
                html=(
                    '<p><b>Ergebnis der Datenprüfung</b>'
                    + '<br>-----------------------</p>'
                ),
                text='Ergebnis der Datenprüfung'
            )
            # Fehlende Spalten
            if len(list_messages) > 0:
                feedback_txt = 'weiteren '
                for msg in list_messages:
                    feedback.pushWarning(msg)
            else:
                feedback_txt = ''
            if len(vector_layer_list) == 0:
                feedback.setProgressText(f'Keine {feedback_txt}Fehler im Datensatz; es wird keine Reportdatei erzeugt.')
            else:
                res_file_name = os.path.split(reportdatei)[1]
                feedback.pushFormattedMessage(
                html=(
                    f'<a href=\"file:///{reportdatei}\">Link zur Datei mit Geometrie-/Datenfehlern ({res_file_name})</a>'
                ),
                text=f'Ergebnis in {reportdatei}'
            )
            feedback.setProgressText('-----------------------')
            return {}
        else:  # for older QGIS Versions
            feedback.setProgressText('\nErgebnis der Datenprüfung\n-----------------------')
            # Fehlende Spalten
            if len(list_messages) > 0:
                feedback_txt = 'weiteren '
                for msg in list_messages:
                    feedback.pushWarning(msg)
            else:
                feedback_txt = ''
            if len(vector_layer_list) == 0:
                feedback.setProgressText(f'Keine {feedback_txt}Fehler im Datensatz; es wird keine Reportdatei erzeugt\n---------------------')
            else:
                return {self.REPORT_OUT: reportdatei} 

    def name(self):
        return '1_Pruefroutine_Gewaesserdaten'

    def displayName(self):
        return '1_Pruefroutine_Gewaesserdaten'

    def group(self):
        return self.tr(self.groupId())

    def shortHelpString(self) -> str:
        return (
            'Mit diesem Werkzeug werden Geodaten für den Export ins '
            + 'FIS-Gewässer geprüft. \n'
            + 'Die Ergebnisse der Prüfroutine werden als '
            + 'einzelne Layer in einer Geopackage-Datei (\"Reportdatei\") gespeichert'
        )

    def groupId(self):
        return 'Datenexport'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return checkGewaesserDaten()
