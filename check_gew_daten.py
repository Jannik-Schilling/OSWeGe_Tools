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

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    NULL,
    QgsExpression,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex
)
from qgis import processing

from .defaults import (
    distanz_suchen,
    pflichtfelder,
    list_ereign_gew_id_fields,
    minimallaenge_gew,
    oswScriptType
)
from .pruefungsroutinen import (
    check_geometrie_wasserscheide_senke,
    check_vtx_on_line
)
from .meldungen import fehlermeldungen_generieren

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
        Here we define the inputs and output of the algorithm, along
        with some other properties.
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

        # Zusammenfassendes dictionary fuer Prozessparameter
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
            'emptystrdef': [NULL, ''],
        }

        # dictionary fuer Feedback / Fehlermeldungen
        report_dict = {}
        """
        report_dict = {
            'gewaesser': {
                'name': 'so heisst die Datei",
                'attribute': {
                    'missing_fields': [],
                    'primary_key_empty': [id1, id2],
                    'primary_key_duplicat': [[id3, id4],[id5, id6, id7]]
                },
                'geometrien': {
                    fehler1: [],
                    fehler2: []
                }
            },
            'rohrleitungen': {
                'name': 'so heisst die Datei",
                'attribute': {
                    'missing_fields': [],
                    #'primary_key_empty': [id1, id2],
                    #'primary_key_duplicat': [[id3, id4],[id5, id6, id7]],
                    'gew_key_empty': [id1, id2],
                    'gew_key_invalid': [id4, id5] /  # nicht im layer_gew
                },
                'geometrien': {
                    fehler1: [],
                    fehler2: []
                }
            }
        }
        """

        feedback.setProgressText('Prüfe Attribute:')
        for key, value in params['layer_dict'].items():
            layer = value['layer']
            if layer:
                # Anzahl Objekte fuer das Feedback
                ft_count = layer.featureCount() if layer.featureCount() else 0
                layer_steps = 100.0/ft_count if ft_count != 0 else 0
                params['layer_dict'][key].update({
                    'count': ft_count,
                    'steps': layer_steps
                })
                report_dict[key] = {'name': layer.name()}

        def main_check(key, report_dict, params):
            """
            Diese Hauptfunktion wird durchlaufen, um alle Layer zu pruefen
            :param str key
            :param dict report_dict
            :param dict params
            """
            layer = params['layer_dict'][key]['layer']
            # pflichtfelder vorhanden?
            pflichtfelder_i = pflichtfelder[key]
            layer_i_felder = layer.fields().names()
            missing_fields = [feld for feld in pflichtfelder_i if not feld in layer_i_felder]

            # Attribute
            emptystrdef = params['emptystrdef']
            ereign_gew_id_field = params['ereign_gew_id_field']
            if ereign_gew_id_field in missing_fields:
                report_dict[key]['attribute'] = {
                    'missing_fields': missing_fields
                }
                """hier noch den layer einbauen"""
                feedback.setProgressText('Primärschlüssel fehlt; Attributtest wird übersprungen')
            else:
                if key == 'gewaesser':
                    list_primary_key_empty = []
                    prim_key_dict = {}
                    for feature in layer.getFeatures():
                        ft_key = feature.attribute(ereign_gew_id_field)
                        if ft_key in emptystrdef:  # fehlender Primaerschluessel?
                            list_primary_key_empty.append(feature.id())
                        else:
                            # mehrfache Primaerschluessel
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
                else:  # alle Ereignisse
                    list_gew_key_empty = []
                    list_gew_key_invalid = []
                    gew_layer = params['layer_dict']['gewaesser']['layer']
                    if ereign_gew_id_field in report_dict['gewaesser']['attribute']['missing_fields']:
                        # Uebereinstimmtung kann nicht geprueft werden, weil der Primaerschluessel beim Gewaesser fehlt
                        report_dict[key]['attribute'] = {
                            'missing_fields': missing_fields
                        }
                    else:
                        list_gew_keys = [gew_ft.attribute(ereign_gew_id_field) for gew_ft in gew_layer.getFeatures()]
                        for feature in layer.getFeatures():
                            ft_key = feature.attribute(ereign_gew_id_field)
                            if ft_key in emptystrdef:  # fehlender Gewaesserschluessel?
                                list_gew_key_empty.append(feature.id())
                            else:
                                if not ft_key in list_gew_keys:
                                    list_gew_key_invalid.append(feature.id())
                        report_dict[key]['attribute'] = {
                            'missing_fields': missing_fields,
                            'gew_key_empty': list_gew_key_empty,
                            'gew_key_invalid': list_gew_key_invalid
                        }


            # Geometrien
            layer_steps = params['layer_dict'][key]['steps']
            list_geom_is_empty = []
            list_geom_is_multi = []
            list_geom_sefintersect = []
            for i, feature in enumerate(layer.getFeatures()):
                """Diese pruefungsroutinen ggf als Funktion, um tests zu schreiben"""
                geom = feature.geometry()
                # Leer?
                geom_is_empty = geom.isEmpty()
                # Multi?
                if geom_is_empty:
                    list_geom_is_empty.append(feature.id())
                else:
                    if geom.isMultipart():
                        polygeom = geom.asMultiPolyline() 
                    else:
                        polygeom = [f for f in geom.parts()]
                    if len(polygeom) > 1:
                        list_geom_is_multi.append(feature.id())
                # Selbstueberschneidungen
                if not geom.isSimple() and not geom_is_empty:
                    list_geom_sefintersect.append(feature.id())
                feedback.setProgress(i+1*layer_steps)
                report_dict[key]['geometrien'] = {
                    'geom_is_empty': list_geom_is_empty,
                    'geom_is_multi': list_geom_is_multi,
                    'geom_sefintersect': list_geom_sefintersect
                }

            feedback.setProgressText('Duplikate und Überschneidungen prüfen')
            list_geom_duplicate = []
            list_geom_crossings = []
            visited_groups_crossings = set()
            visited_groups_equal = set()
            spatial_index = QgsSpatialIndex(layer.getFeatures())
            for feature in layer.getFeatures():
                feature_id = feature.id()
                if feature_id in list_geom_is_empty:
                    continue
                if feature_id in list_geom_is_multi:  # das vielleicht rauswerfen
                    continue
                geom = feature.geometry()
                intersecting_ids = spatial_index.intersects(geom.boundingBox())
                for fid in intersecting_ids:
                    if fid == feature_id:
                        continue
                    group_i = tuple(sorted([feature_id, fid]))
                    other_feature = layer.getFeature(fid)
                    other_geom = other_feature.geometry()
                    if geom.equals(other_geom):
                        if group_i in visited_groups_equal:
                            pass
                        else:
                            list_geom_duplicate.append(group_i)
                            visited_groups_equal.add(group_i)
                    if geom.crosses(other_geom):
                        if group_i in visited_groups_crossings:
                            pass
                        else:
                            list_geom_crossings.append(group_i)
                            visited_groups_crossings.add(group_i)
            report_dict[key]['geometrien']['geom_crossings'] = list_geom_crossings
            report_dict[key]['geometrien']['geom_duplicate'] = list_geom_duplicate

            if key == 'gewaesser':
                pass
                # wasserscheiden, senken
            else:  # Ereignisse
                list_geom_ereign_auf_gew = []
                gew_layer = params['layer_dict']['gewaesser']['layer']
                spatial_index_gew = QgsSpatialIndex(gew_layer.getFeatures())
                if key in ['rohrleitungen', 'durchlaesse']:  # Linienereignisse (rl und dl)
                    # gewaesser finden
                    for feature in layer.getFeatures():
                        feature_id = feature.id()
                        if feature_id in list_geom_is_empty:
                            pass
                        elif feature_id in list_geom_is_multi: 
                            pass
                        else:
                            geom = feature.geometry()
                            intersecting_ids = spatial_index_gew.intersects(geom.boundingBox())
                            '''
                            ggf. gew-duplikate rauswerfen
                            hier lieber ein request, wie vorher
                            '''
                            
                            if len(intersecting_ids)==1:
                                gew_ft = gew_layer.getFeature(intersecting_ids[0])
                            else:
                                """was, wenn da meherere in der Nähe sind?"""
                                gew_ft = gew_layer.getFeature(intersecting_ids[-1])
                            #Linie auf Gewaesserlinie
                            list_vtx_geom = [QgsGeometry(vtx) for vtx in geom.vertices()]
                            list_geom_ereign_auf_gew.append(check_vtx_on_line(list_vtx_geom, gew_ft, gew_layer))
                            report_dict[key]['geometrien']['geom_ereign_auf_gew'] = list_geom_ereign_auf_gew

        """
                else:
                    pass
                    # Punkt auf Gewaesserlinie
                    if key == 'schaechte':
                        pass
                        # ggf. Lage auf RL prüfen
        """
        # run test
        for key in params['layer_dict'].keys():
            if key in report_dict.keys():
                feedback.setProgressText('layer: '+key)
                main_check(key, report_dict, params)
        #print(report_dict)
        
        import json
        import json
        with open(reportdatei, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=4)

        """
        # Geometrieprüfungen hier nur fuer Ereignisse
        layer_typ = ''
        if layer_typ == 'Ereignis':
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


        # Bericht zusammenstellen
        with open(reportdatei, 'w') as f:
            f.write(
                '**************************************'
                + '\nÜberprüfung des (Basis-)Gewässerlayers'
                + '\n\nLayer: ' + str(layer_gew)
                + '\n**************************************\n\n'
            )
            for val in report_dict.values():
                f.write(fehlermeldungen_generieren(val))

        feedback.pushInfo('Report gespeichert in ' + str(reportdatei)+ '\n')
        """
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
