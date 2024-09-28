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

from qgis.PyQt.QtCore import (
    QCoreApplication
)
from qgis.core import (
    NULL,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterVectorLayer,
    QgsWkbTypes
)
from qgis import processing

from .defaults import (
    list_ereign_gew_id_fields,
    pflichtfelder,
)
from .pruefungsroutinen import (
    check_duplicates_crossings,
    check_geometrie_wasserscheide_senke,
    check_geom_on_line,
    check_vtx_distance,
    get_line_to_check
)

from .check_gew_report import (
    create_report_dict,
    replace_lst_ids
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
                'Json File (*.json)'                #'Textdatei (*.txt)',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Hier findet die Verarbeitung statt
        """
        layer_gew = self.parameterAsVectorLayer(parameters, self.LAYER_GEWAESSER, context)
        layer_rohrleitungen = self.parameterAsVectorLayer(parameters, self.LAYER_ROHLEITUNGEN, context)
        layer_durchlaesse = self.parameterAsVectorLayer(parameters, self.LAYER_DURCHLAESSE, context)
        layer_wehre = self.parameterAsVectorLayer(parameters, self.LAYER_WEHRE, context)
        layer_schaechte = self.parameterAsVectorLayer(parameters, self.LAYER_SCHAECHTE, context)
        reportdatei = self.parameterAsString(parameters, self.REPORT, context)

        # Zusammenfassendes dictionary fuer Prozessparameter, die an Funktionen uebergeben werden
        params = {
            'layer_dict': {
                'gewaesser': {'layer': layer_gew},
                'rohrleitungen': {'layer': layer_rohrleitungen},
                'durchlaesse': {'layer': layer_durchlaesse},
                'wehre': {'layer': layer_wehre},
                'schaechte': {'layer': layer_schaechte},
            },
            'feedback': feedback,
            'ereign_gew_id_field': list_ereign_gew_id_fields[1],  # gu_cd, ba_cd
            'field_merged_id': 'merged_id',
            'emptystrdef': [NULL, ''],  # mögliche "Leer"-Definitionen für Zeichketten
        }

        # dictionary fuer Feedback / Fehlermeldungen
        report_dict = create_report_dict(params, is_test_version=True)

        # rl und dl zusammenfassen, fuer gemeinsame Auswertung (falls beide Layer vorhanden)
        if layer_rohrleitungen and layer_durchlaesse:
            # neues Feld "rldl_id" mit dem Layername und der id() des Objekts, weil sich die id() beim Vereinigen der Layer aendert
            rl_mit_id = processing.run("native:fieldcalculator", {
                'INPUT': params['layer_dict']['rohrleitungen']['layer'],
                'FIELD_NAME': params['field_merged_id'],
                'FIELD_TYPE': 2,
                'FORMULA': "concat(@layer_name,': ',$id)",
                'OUTPUT': 'memory:'
            }) ['OUTPUT']
            dl_mit_id = processing.run("native:fieldcalculator", {
                'INPUT': params['layer_dict']['durchlaesse']['layer'],
                'FIELD_NAME': params['field_merged_id'],
                'FIELD_TYPE': 2,
                'FORMULA': "concat(@layer_name,': ',$id)",
                'OUTPUT': 'memory:'
            })['OUTPUT']
            list_r_layer = [rl_mit_id, dl_mit_id]
            # Vereinigen der layer rl und dl für Überschneidungsanalyse
            layer_rldl = processing.run(
                "native:mergevectorlayers",
                {
                    'LAYERS':list_r_layer,
                    'OUTPUT':'memory:'
                }
            )['OUTPUT']
            params['layer_rldl'] = layer_rldl


        def main_check(key, report_dict, params, feedback):
            """
            Diese Hauptfunktion wird durchlaufen, um die Vektorobjekte alle Layer zu pruefen (Attribute + Geometrien)
            :param str key
            :param dict report_dict
            :param dict params
            :param QgsProcessingFeedback feedback
            """
            feedback.setProgressText('Layer \"'+key+'\":')
            layer = params['layer_dict'][key]['layer']
            layer_steps = params['layer_dict'][key]['steps']

            # pflichtfelder vorhanden?
            feedback.setProgressText('> Prüfe benötigte Attributfelder...')
            pflichtfelder_i = pflichtfelder[key]
            layer_i_felder = layer.fields().names()
            missing_fields = [feld for feld in pflichtfelder_i if not feld in layer_i_felder]

            # Attribute
            feedback.setProgressText('> Prüfe alle Einzelobjekte...')
            ereign_gew_id_field = params['ereign_gew_id_field']
            if ereign_gew_id_field in missing_fields:
                report_dict[key]['attribute'] = {
                    'missing_fields': missing_fields
                }
                feedback.setProgressText(
                   'Feld \"'
                   + ereign_gew_id_field
                   + '\"(Primärschlüssel) fehlt. Attributtest wird übersprungen'
                )
            else:
                feedback.setProgressText('-- Attribute')
                if key == 'gewaesser':
                    list_primary_key_empty = []
                    prim_key_dict = {}
                    for i, feature in enumerate(layer.getFeatures()):
                        feedback.setProgress(int(i * layer_steps))
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
                    list_primary_key_duplicat = [lst for lst in prim_key_dict.values() if len(lst) > 1]
                    report_dict[key]['attribute'] = {
                        'missing_fields': missing_fields,
                        'primary_key_empty': list_primary_key_empty,
                        'primary_key_duplicat': list_primary_key_duplicat
                    }
                else:  # Attributtest für Ereignisse
                    list_gew_key_empty = []
                    list_gew_key_invalid = []
                    layer_gew = params['layer_dict']['gewaesser']['layer']
                    if ereign_gew_id_field in (
                        report_dict['gewaesser']
                            ['attribute']
                            ['missing_fields']
                        ):
                        feedback.setProgressText(
                            'Die Zuordnung zum Gewässer kann '
                            + 'nicht geprueft werden, weil das Feld \"'
                            + ereign_gew_id_field
                            + '\" im Gewaesserlayer fehlt.'
                        )
                        report_dict[key]['attribute'] = {
                            'missing_fields': missing_fields
                        }
                    else:
                        list_gew_keys = [gew_ft.attribute(ereign_gew_id_field) for gew_ft in layer_gew.getFeatures()]
                        for i, feature in enumerate(layer.getFeatures()):
                            feedback.setProgress(int(i * layer_steps))
                            ft_key = feature.attribute(ereign_gew_id_field)
                            if ft_key in params['emptystrdef']:
                                # fehlender Gewaesserschluessel
                                list_gew_key_empty.append(feature.id())
                            else:
                                if not ft_key in list_gew_keys:
                                    # Der angegebene Gewaesserschluessel(=Gewaessername) ist nicht im Gewaesserlayer vergeben
                                    list_gew_key_invalid.append(feature.id())
                        report_dict[key]['attribute'] = {
                            'missing_fields': missing_fields,
                            'gew_key_empty': list_gew_key_empty,
                            'gew_key_invalid': list_gew_key_invalid
                        }

            # Geometrien
            feedback.setProgressText('-- Geometrien')
            layer_steps = params['layer_dict'][key]['steps']
            """Diese pruefungsroutinen ggf als Funktion, um tests zu schreiben"""
            list_geom_is_empty = []
            list_geom_is_multi = []
            list_geom_sefintersect = []
            feedback.setProgressText('--- Leere und Multigeometrien, Selbstüberschneidungen')
            for i, feature in enumerate(layer.getFeatures()):
                feedback.setProgress(i+1*layer_steps)
                geom = feature.geometry()
                if geom.isEmpty():
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
            report_dict[key]['geometrien'] = {
                    'geom_is_empty': list_geom_is_empty,
                    'geom_is_multi': list_geom_is_multi,
                    'geom_sefintersect': list_geom_sefintersect
                }

            feedback.setProgressText('--- Duplikate und Überschneidungen')
            if not ((key in ['rohrleitungen', 'durchlaesse']) and ('layer_rldl' in params.keys())):
                # Normalfall
                list_geom_crossings, list_geom_duplicate = check_duplicates_crossings(
                    layer,
                    feedback,
                    layer_steps
                )
                report_dict[key]['geometrien']['geom_crossings'] = list_geom_crossings
                report_dict[key]['geometrien']['geom_duplicate'] = list_geom_duplicate
            else:
                if not 'rldl' in report_dict.keys():  # falls es nicht schon einmal durchlaufen wurde
                    layer_rldl = params['layer_rldl']
                    layer_steps = 100/layer_rldl.featureCount()
                    list_geom_crossings, list_geom_duplicate = check_duplicates_crossings(
                        layer_rldl,
                        feedback,
                        layer_steps
                    )
                    dict_alternative_id = {feature.id(): feature[params['field_merged_id']] for feature in layer_rldl.getFeatures()}
                    list_geom_crossings_adjusted = replace_lst_ids(list_geom_crossings, dict_alternative_id)
                    list_geom_duplicate_adjusted = replace_lst_ids(list_geom_duplicate, dict_alternative_id)
                    report_dict['rldl'] = {
                        'geometrien': {
                            'geom_crossings': list_geom_crossings_adjusted,
                            'geom_duplicate': list_geom_duplicate_adjusted
                        }
                    }

            if key == 'gewaesser':
                feedback.setProgressText('--- Wasserscheiden, Senken')
                visited_features_wassersch = set()
                visited_features_senken = set()
                list_geom_wassersch = []
                list_geom_senken = []
                for i, feature in enumerate(layer.getFeatures()):
                    geom = feature.geometry()
                    feature_id = feature.id()
                    if geom:
                        wasserscheiden = check_geometrie_wasserscheide_senke(
                            geom,
                            feature_id,
                            layer
                        )
                        if wasserscheiden:
                            if not wasserscheiden in visited_features_wassersch:
                                list_geom_wassersch.append(wasserscheiden)
                                visited_features_wassersch.add(wasserscheiden)
                        senken = check_geometrie_wasserscheide_senke(
                            geom,
                            feature_id,
                            layer,
                            senke=True
                        )
                        if senken:
                            if not senken in visited_features_senken:
                                list_geom_senken.append(senken)
                                visited_features_senken.add(senken)
                report_dict[key]['geometrien']['wasserscheiden'] = list_geom_wassersch
                report_dict[key]['geometrien']['senken'] = list_geom_senken

            else:  # Ereignisse
                feedback.setProgressText('--- Korrekte Lage von Ereignissen auf Gewässern')
                layer_gew = params['layer_dict']['gewaesser']['layer']
                # gewaesser finden
                report_dict[key]['geometrien']['geom_ereign_auf_gew'] = {}
                for i, feature in enumerate(layer.getFeatures()):
                    feedback.setProgress(i+1*layer_steps)
                    feature_id = feature.id()
                    if feature_id in list_geom_is_empty:
                        pass
                    elif feature_id in list_geom_is_multi: 
                        pass
                    else:
                        #Linie / Punkt auf Gewaesserlinie ?
                        geom = feature.geometry()
                        if (layer.geometryType() == QgsWkbTypes.PointGeometry) and geom:  # Point and not None
                            line_feature = get_line_to_check(geom, layer_gew)
                            if line_feature:
                                if not check_vtx_distance(geom, line_feature.geometry()):
                                    # Distanz zum naechsten Gewaesser zu gross
                                    dict_vtx_bericht = {feature_id: {'Lage': 1}}
                                else:
                                    # korrekt
                                    dict_vtx_bericht = {feature_id: {'Lage': 0}}  # hier später noch die Stationierung
                            else:
                                # kein Gewaesser in der Naehe gefunden
                                dict_vtx_bericht = {feature_id: {'Lage': 1}}
                        else:
                            dict_vtx_bericht = {feature_id: check_geom_on_line(geom, layer_gew, with_stat=True)}
                    report_dict[key]['geometrien']['geom_ereign_auf_gew'].update(dict_vtx_bericht)
                if key == 'schaechte':
                    if 'layer_rldl' in params.keys():
                        other_layer = params['layer_rldl']
                    # Oder nur einer von rl oder dl:
                    elif 'rohrleitungen' in report_dict.keys():
                        other_layer = params['layer_dict']['rohrleitungen']['layer']
                    elif 'durchlaesse' in report_dict.keys():
                        other_layer = params['layer_dict']['durchlaesse']['layer']
                    else:
                        # Wenn nur das Gewaesser verfügbar ist
                        other_layer = None
                    if not other_layer:
                        feedback.setProgressText(
                            ' (Prüfung der Lage von Schächten an/auf '
                            + 'Rohrleitungen und Durchlässen wird übersprungen: '
                            + 'Kein(e) Layer für Rohrleitungen und Durchlässe)'
                        )
                    else:
                        feedback.setProgressText(
                            '--- Korrekte Lage von Schächten an/auf '
                            + 'Rohrleitungen und Durchlässen'
                        )
                        dict_schacht_rldl = dict()
                        for i, feature in enumerate(layer.getFeatures()):
                            feedback.setProgress(i+1*layer_steps)
                            geom = feature.geometry()
                            if (not geom) or feature_id in list_geom_is_multi:
                                continue
                            feature_id = feature.id()
                            line_feature = get_line_to_check(geom, other_layer)
                            if line_feature:
                                schacht_auf_rldl = check_vtx_distance(
                                    geom,
                                    line_feature.geometry()
                                )
                            else:
                                schacht_auf_rldl = False
                            fehler_auf_gew = (
                                report_dict[key]
                                    ['geometrien']
                                    ['geom_ereign_auf_gew']
                                    [feature_id]
                                    ['Lage']
                                )
                            if schacht_auf_rldl and (not fehler_auf_gew):
                                dict_schacht_rldl[feature_id] = 0
                            elif (not fehler_auf_gew) and (not schacht_auf_rldl):
                                # fehler: schacht auf offenem gewaesser
                                dict_schacht_rldl[feature_id] = 1
                            elif (fehler_auf_gew) and schacht_auf_rldl:
                                # fehler: rldl verschoben
                                dict_schacht_rldl[feature_id] = 2
                            else:
                                # fehler: schacht weder auf gewaesser noch auf rldl
                                dict_schacht_rldl[feature_id] = 3
                        report_dict[key]['geometrien']['geom_schacht_auf_rldl'] = dict_schacht_rldl
            feedback.setProgressText('Abgeschlossen \n ')

        # run test
        for key in params['layer_dict'].keys():
            if key in report_dict.keys():
                main_check(key, report_dict, params, feedback)


        import json
        # dict_ereign_fehler
        with open(reportdatei, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=4)
        feedback.setProgressText('Bericht gespeichert unter: \n'+str(reportdatei))
        return {}

    def name(self):
        return 'Pruefroutine_Gewaesserdaten'

    def displayName(self):
        return 'Pruefroutine_Gewaesserdaten'

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Pruefroutinen'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return checkGewaesserDaten()
