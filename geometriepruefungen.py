import pandas as pd
from qgis.core import (
    QgsGeometry,
    QgsPoint,
    QgsSpatialIndex,
    QgsWkbTypes
)
from .check_gew_report import (
    replace_lst_ids,
    join_list_items
)

from .hilfsfunktionen import (
    get_vtx,
    get_line_candidates_ids,
    get_line_to_check,
    ranges_overlap,
    setup_localparams_for_tests_with_comparisons,
    sub_line_by_stats
)


def check_geometry_empty_or_null(geom):
    """
    Diese Funktion prueft die Geometrien auf Leere, Multigeometrien und Selbstueberschneidungen
    :param QgsGeometry geom
    :return: bool
    """
    if geom.isEmpty() or geom.isNull():
        return True
    else:
        return False
    

def check_geometry_multi(geom, geom_empty):
    """
    Diese Funktion prueft auf Multigeometrien
    :param QgsGeometry geom
    :param bool geom_empty
    :return: bool
    """
    if geom_empty:
        return False
    else:
        if geom.isMultipart():
            polygeom = geom.asMultiPolyline() 
        else:
            polygeom = [f for f in geom.parts()]
        if len(polygeom) > 1:
            return True
        else:
            return False


def check_geometry_selfintersect(geom, geom_empty):
    """
    Diese Funktion prueft auf Selbstueberschneidungen
    :param QgsGeometry geom
    :param bool geom_empty
    :return: bool
    """
    if geom_empty:
        return False
    else:
        if not geom.isSimple():
            return True
        else:
            return False
    

def handle_tests_single_geometries(layer, layer_key, layer_steps, report_dict, feedback):
    """
    Diese Funktion prueft die Geometrien auf Leere, Multigeometrien und Selbstueberschneidungen
    :param QgsVectorLayer layer
    :param str layer_key
    :param float layer_steps
    :param dict report_dict
    :param QgsProcessingFeedback feedback
    """
    feedback.setProgressText(
        '--- Leere und Multigeometrien, Selbstüberschneidungen'
    )
    # Listen fuer das einmalige Durchlaufen der Funktion
    list_geom_is_empty = []
    list_geom_is_multi = []
    list_geom_sefintersect = []
    for i, feature in enumerate(layer.getFeatures()):
        feedback.setProgress(int((i+1) * layer_steps))
        if feedback.isCanceled():
            break
        geom = feature.geometry()
        geom_empty = check_geometry_empty_or_null(geom)
        if geom_empty:  # Leer?
            list_geom_is_empty.append(feature.id())
        if check_geometry_multi(geom, geom_empty):  # Multigeometrien?
            list_geom_is_multi.append(feature.id())
        if check_geometry_selfintersect(geom, geom_empty):  # Selbstueberschneidungen?
            list_geom_sefintersect.append(feature.id())
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
            report_dict[layer_key]['geometrien'][fehl_typ] = df_i


def check_vtx_distance(vtx_geom, geom2, tolerance=1e-6):
    """
    Prueft, ob der vtx maximal die Toleranz x von einer zweiten Geometrie entfernt ist
    :param QgsGeometry vtx_geom
    :param QgsGeometry geom
    :param float tolerance
    :return: bool
    """
    return geom2.distance(vtx_geom) <= tolerance

# Uebergeordnete Funktion, um Geometriepruefungen vorzubereiten und durchzuführen
def handle_tests_geoms_comparisons(  # perform check....
    layer_key,
    report_dict,
    params_processing
):
    """
    Prueft Geometrien durch den Vergleich mit anderen Geometrien
    :param str layer_key
    :param dict report_dict
    :param dict params_processing
    """
    # Setup
    (
        temp_key,
        temp_layer,
        temp_layer_steps,
        skip_dict,
        use_field_merged_id
    ) = setup_localparams_for_tests_with_comparisons(layer_key, params_processing)

    # Doppelte Geometrien und Überschneidungen innerhelb des Layers
    handle_tests_compare_in_own_layer(
        temp_key,
        temp_layer,
        temp_layer_steps,
        use_field_merged_id,
        skip_dict,
        report_dict,
        params_processing
    )

    # Lage bezueglich Gewässer und Schaechte auf RL oder DL
    handle_tests_compare_other_layer(
        temp_key,
        temp_layer,
        temp_layer_steps,
        use_field_merged_id,
        skip_dict,
        report_dict,
        params_processing
    )

    # Ueberlappung anhand der Stationierung
    handle_tests_overlap(
        temp_layer_steps,
        temp_key,
        skip_dict,
        report_dict,
        params_processing
    )


def handle_tests_compare_in_own_layer(
    layer_key,
    layer,
    layer_steps,
    use_field_merged_id,
    skip_dict,
    report_dict,
    params_processing
):
    """
    Führt die Tests mit Geometrievergleichen innerhalb eines Layers durch
    :param str layer_key
    :param QgsVectorLayer layer
    :param float layer_steps
    :param bool use_field_merged_id
    :param dict skip_dict
    :param dict report_dict
    :param dict params_processing
    """
    feedback = params_processing['feedback']

    # Duplikate und Ueberschneidungen
    if not skip_dict['skip_geom_duplicates_crossings']:
        if layer_key == 'layer_rldl':
            feedback.setProgressText('--- Duplikate und Überschneidungen (RL und DL gemeinsam)')
        else:
            feedback.setProgressText('--- Duplikate und Überschneidungen')
        df_geom_crossings, df_geom_duplicate = check_duplicates_crossings(
            layer,
            feedback,
            layer_steps
        )
        if use_field_merged_id:
            dict_alternative_id = {
                feature.id(): feature[params_processing['field_merged_id']] for feature in layer.getFeatures()
            }
            df_geom_crossings = df_geom_crossings.apply(lambda x: replace_lst_ids(x, dict_alternative_id), axis=1)
            df_geom_duplicate = df_geom_duplicate.apply(lambda x: replace_lst_ids(x, dict_alternative_id), axis=1)
        if len(df_geom_crossings) > 0:
            report_dict[layer_key]['geometrien']['geom_crossings'] = df_geom_crossings
        if len(df_geom_duplicate) > 0:
            report_dict[layer_key]['geometrien']['geom_duplicate'] = df_geom_duplicate
    
    # Wasserscheiden und Senken
    if not skip_dict['skip_geom_wasserscheiden_senken']:
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
                        visited_features_wassersch = list(
                            set(visited_features_wassersch + wasserscheiden[0])  # die Geometrie wird nicht eingetragen
                        )
                        wasserscheiden[0] = join_list_items(wasserscheiden[0])
                        list_geom_wassersch.append(wasserscheiden)
                if not feature_id in visited_features_senken:
                    senken = check_geometrie_wasserscheide_senke(
                        geom,
                        feature_id,
                        layer,
                        spatial_index_other,
                        senke=True
                    )
                    if senken:
                        visited_features_senken = list(
                            set(visited_features_senken + senken[0])  # die Geometrie wird nicht eingetragen
                        )
                        senken[0] = join_list_items(senken[0])
                        list_geom_senken.append(senken)
        df_wasserscheiden = pd.DataFrame(
            list_geom_wassersch,
            columns = ['feature_id','geometry']
        )
        df_senken = pd.DataFrame(
            list_geom_senken,
            columns = ['feature_id','geometry']
        )
        if len(df_wasserscheiden) > 0:
            report_dict[layer_key]['geometrien']['wasserscheiden'] = df_wasserscheiden
        if len(list_geom_senken) > 0:
            report_dict[layer_key]['geometrien']['senken'] = df_senken

def check_duplicates_crossings(
    layer,
    feedback,
    layer_steps,
):
    """
    Ueberprueft ob es im Layer Geometrie-Duplikate oder Ueberschneidungen gibt
    :param QgsVectorLayer layer
    :param QgsProcessingFeedbackfeedback
    :param float layer_steps
    :return tuple: (list_crossing = [], list_duplicates = [])
    """
    list_geom_duplicate = []
    list_geom_crossings = []
    visited_groups_crossings = set()
    visited_groups_equal = set()
    spatial_index = QgsSpatialIndex(layer.getFeatures())
    column_names = ['id1', 'id2', 'geometry']
    for i, feature in enumerate(layer.getFeatures()):
        feedback.setProgress(int((i+1) * layer_steps))
        if feedback.isCanceled():
            break
        geom = feature.geometry()
        feature_id = feature.id()
        if geom.isEmpty() or geom.isNull():
            continue
        if geom.type() == 0:  # Point
            intersecting_ids = spatial_index.intersects(geom.boundingBox().buffered(0.2))
        else:
            intersecting_ids = spatial_index.intersects(geom.boundingBox())
        for fid in intersecting_ids:
            if feedback.isCanceled():
                break
            if fid == feature_id:
                continue
            group_i = tuple(sorted([feature_id, fid]))
            other_feature = layer.getFeature(fid)
            other_geom = other_feature.geometry()
            if geom.equals(other_geom):
                if group_i in visited_groups_equal:
                    pass
                else:
                    list_geom_duplicate.append(list(group_i)+[geom])
                    visited_groups_equal.add(group_i)
            if geom.crosses(other_geom):
                if group_i in visited_groups_crossings:
                    pass
                else:
                    intersection_point = geom.intersection(other_geom)
                    list_geom_crossings.append(list(group_i)+[intersection_point])
                    visited_groups_crossings.add(group_i)
    df_geom_crossings = pd.DataFrame(list_geom_crossings, columns = column_names)
    df_geom_duplicate = pd.DataFrame(list_geom_duplicate, columns = column_names)
    return df_geom_crossings, df_geom_duplicate

def check_geometrie_wasserscheide_senke(
    geom,
    feature_id,
    layer_gew,
    spatial_index_other,
    senke=False
):
    '''
    Ueberprueft ob die Geometrie mit anderen Geometrien eine Wasserscheide oder Senke bildet
    :param QgsGeometry geom: Geometrie des aktuellen Gewaesserobjekts
    :param int feature_id: id() des aktuellen Gewaesserobjekts
    :param QgsVectorLayer (line) layer_gew
    :param QgsSpatialIndex spatial_index_other
    :param bool senke
    :return None or list [[feature_id, id2, ..., idn], vtx_geom]
    '''
    if senke:
        vtx_num = 0
    else:
        vtx_num = -1
    vtx = get_vtx(geom, vtx_num)  # QgsGeometry
    intersecting_lines = get_line_candidates_ids(
        vtx,
        spatial_index_other
    )
    if feature_id in intersecting_lines:
        # die eigene id() entfernen
        intersecting_lines.remove(feature_id)
    if len(intersecting_lines) == 0:
        return None# Quelle oder Muendung (korrekt)
    else:
        check_dupl_list = []
        for line_id in intersecting_lines:
            inters_line_geom = layer_gew.getFeature(line_id).geometry()
            check_vtx = get_vtx(inters_line_geom, vtx_num)  # der zu pruefende Stuetzpunkt
            if vtx.equals(check_vtx):
                check_dupl_list.append(1)
            else:
                check_dupl_list.append(0)
        if all([x == 1 for x in check_dupl_list]):
            return [sorted([feature_id] + intersecting_lines)]+[vtx]
        else:
            return None


# Vergleich mit anderen Layern
def handle_tests_compare_other_layer(
    layer_key,
    layer,
    layer_steps,
    use_field_merged_id,
    skip_dict,
    report_dict,
    params_processing
):
    """
    Pruef die Lage auf Objekten eines anderen Layers nur fuer Ereignisse
    :param str layer_key
    :param QgsVectorLayer layer
    :param float layer_steps
    :param bool use_field_merged_id
    :param dict skip_dict
    :param dict report_dict
    :param dict params_processing
    """
    feedback = params_processing['feedback']

    # Lage der Ereignisse auf den Gewässern
    if not skip_dict['skip_geom_ereign_auf_gew']:
        if layer_key == 'layer_rldl':
            feedback.setProgressText(
                '--- Korrekte Lage von Ereignissen '
                + 'auf Gewässern (RL und DL gemeinsam)'
            )
        else:
            feedback.setProgressText('--- Korrekte Lage von Ereignissen auf Gewässern')
        df_vtx_bericht = check_location_event_on_river(
            layer_key,
            layer,
            layer_steps,
            use_field_merged_id,
            params_processing
        )
        report_dict[layer_key]['geometrien']['geom_ereign_auf_gew'] = df_vtx_bericht

    # Liegen Schaechte korrekt auf RL oder DL?
    if skip_dict['skip_geom_schacht_auf_rldl'] and layer_key == 'schaechte':
        feedback.pushWarning(
            ' (Prüfung der Lage von Schächten an/auf '
            + 'Rohrleitungen und Durchlässen wird übersprungen: '
            + 'Kein(e) Layer für Rohrleitungen und Durchlässe)'
        )
    if not skip_dict['skip_geom_schacht_auf_rldl']:
        feedback.setProgressText(
            '--- Korrekte Lage von Schächten an/auf '
            + 'Rohrleitungen und Durchlässen'
        )
        df_schaechte_auf_rldl = check_schaechte_auf_rldl(
            layer_key,
            layer,
            layer_steps,
            report_dict,
            params_processing
        )
        report_dict[layer_key]['geometrien']['geom_schacht_auf_rldl'] = df_schaechte_auf_rldl


def check_line_geom_on_line(
    geom,
    feature_id_temp,
    gew_layer,
    spatial_index_other,
    with_stat=False
):
    """
    Prueft ob sich eine eine Linieneometrie (geom) korrekt auf einem anderen Linienobjekt des layers gew_layer befindet
    :param QgsGeometry (Line) geom
    :param str feature_id_temp: Id des Objekts
    :param QgsVectorLayer (Line) gew_layer
    :param QgsSpatialIndex spatial_index_other
    :param bool with_stat: Rückgabe der Stationierung?; default: False
    :return: pd.Series
    """
    sr_vtx_report = pd.Series()  # Fehlermeldungen siehe defaults.dict_ereign_fehler
    other_line_ft = get_line_to_check(geom, gew_layer, spatial_index_other)
    sr_vtx_report['gew_id'] = other_line_ft.id()
    gew_i_geom = other_line_ft.geometry()
    list_gew_stat = []
    list_vtx_geom = [QgsGeometry(vtx) for vtx in geom.vertices()]

    # Stationierung
    for vtx in list_vtx_geom:
        # naechster Punkt auf dem Gewaesser, als Point XY
        nearest_gew_point = gew_i_geom.nearestPoint(vtx)
        nearest_gew_xy = nearest_gew_point.asPoint()
        # naechster Stuetzpunkt danach
        result_tuple = gew_i_geom.closestSegmentWithContext(nearest_gew_xy)
        # Linie bis zum Punkt -> Stationierung
        if gew_i_geom.isMultipart():
            gew_i_geom_polyline = gew_i_geom.asMultiPolyline()
            first_segment = gew_i_geom_polyline[0][:result_tuple[2]]+[result_tuple[1]]
        else:
            gew_i_geom_polyline = gew_i_geom.asPolyline()
            first_segment = gew_i_geom_polyline[:result_tuple[2]]+[result_tuple[1]]
        first_segment = [QgsPoint(p) for p in first_segment]
        first_segment_geom = QgsGeometry.fromPolyline(first_segment)
        stationierung = first_segment_geom.length()
        list_gew_stat.append(stationierung)

    # Richtung
    if with_stat:
        sr_vtx_report['vtx_stat'] = list_gew_stat
    if list_gew_stat == sorted(list_gew_stat):
        sr_vtx_report['Richtung'] = 0  # korrekt
    elif list_gew_stat == (sorted(list_gew_stat))[::-1]:
        sr_vtx_report['Richtung'] = 1  # entgegengesetzte Richtung 
    else:
        sr_vtx_report['Richtung'] = 2  # falsche Reihenfolge

    # Den Linienabschnitt zum Vergleich generieren
    sub_line = sub_line_by_stats(gew_i_geom, list_gew_stat[0] , list_gew_stat[-1])
    list_sub_line_vtx_geom = [QgsGeometry(vtx) for vtx in sub_line.vertices()]

    # Anzahl der Stützpunkte
    if len(list_vtx_geom) == len(list_sub_line_vtx_geom):
        sr_vtx_report['Anzahl'] = 0  # korrekt
    if len(list_vtx_geom) > len(list_sub_line_vtx_geom):
        sr_vtx_report['Anzahl'] = 1  # zu viele
    if len(list_vtx_geom) < len(list_sub_line_vtx_geom):
        sr_vtx_report['Anzahl'] = 2  # zu wenige

    # Lage
    list_point_on_line = []
    for vtx_geom, vtx_subline in zip(list_vtx_geom, list_sub_line_vtx_geom):
        list_point_on_line.append(
            check_vtx_distance(
                vtx_geom,
                vtx_subline
            )
        )
    if not all(list_point_on_line):
        sr_vtx_report['Lage'] = [1, [str(i) for i, b in enumerate(list_point_on_line) if not b]]  # Abweichung
    else:
        sr_vtx_report['Lage'] = 0 # Korrekt
    return sr_vtx_report



def check_overlap_by_stat(params_processing, report_dict, layer_steps):
    """
    Ueberprueft die Ueberlappung von Linienereignissen anhand der Stationierung
    :param dict params_processing
    :param dict report_dict
    :param float layer_steps
    """
    feedback = params_processing['feedback']

    # Auswahl des Layers
    if 'layer_rldl' in report_dict.keys():
        df_vorher = report_dict['layer_rldl']['geometrien']['geom_ereign_auf_gew']
    else:
        if 'rohrleitungen' in report_dict.keys():
            df_vorher = report_dict['rohrleitungen']['geometrien']['geom_ereign_auf_gew']
        elif 'durchlaesse' in report_dict.keys():
            df_vorher = report_dict['durchlaesse']['geometrien']['geom_ereign_auf_gew']
        else:
            df_vorher = pd.DataFrame()

    # Das Stationierungs-Dict je Gewaesser aufbereiten
    dict_stat = {}
    df_vorher['start'] = [min(lst) if isinstance(lst, list) else -1 for lst in df_vorher['vtx_stat']]
    df_vorher['stop'] = [max(lst) if isinstance(lst, list) else -1 for lst in df_vorher['vtx_stat']]
    for i in df_vorher.index:
        if feedback.isCanceled():
            break
        elem = df_vorher.loc[i,:]
        gew_id = elem['gew_id']
        feature_id = elem['feature_id']
        start = elem['start']
        stop = elem['stop']
        geom = elem['geometry']
        lst_i = [feature_id, start, stop, geom]
        if gew_id in dict_stat.keys():
            dict_stat[gew_id].append(lst_i)
        else:
            dict_stat[gew_id] = [lst_i]

    # nun fuer jedes gewaesser einmal pruefen
    lst_overlap = []
    for key, lst in dict_stat.items():
        if len(lst) > 1:
            lst_overlap_i = [ranges_overlap(lst[i], lst[j])
                for i in range(len(lst))
                for j in range(i + 1, len(lst))
            ]
            lst_overlap_i = [k for k in lst_overlap_i if k]
            lst_overlap = lst_overlap+lst_overlap_i
    return lst_overlap

def check_location_event_on_river(
    layer_key,
    layer,
    layer_steps,
    use_field_merged_id,
    params_processing
):
    """
    Prueft die Lage der Ereignisse auf den Gewaessern
    :param str layer_key
    :param QgsVectorLayer layer
    :param float layer_steps
    :param bool use_field_merged_id
    :param dict params_processing
    :return: pd.DataFrame
    """
    feedback = params_processing['feedback']
    layer_gew = params_processing['layer_dict']['gewaesser']['layer']
    spatial_index_gew = QgsSpatialIndex(layer_gew.getFeatures())
    list_vtx_bericht = []
    for i, feature in enumerate(layer.getFeatures()):
        if feedback.isCanceled():
            break
        feedback.setProgress(int((i+1) * layer_steps))
        if not use_field_merged_id:
            feature_id_temp = feature.id()
        else:
            feature_id_temp = feature[params_processing['field_merged_id']]  # id + layername
        geom = feature.geometry()
        if check_geometry_empty_or_null(geom):
            pass
        elif check_geometry_multi(geom, geom_empty=False): 
            pass
        else:
            series_vtx_bericht = pd.Series()
            #Linie / Punkt auf Gewaesserlinie ?
            if layer.geometryType() == QgsWkbTypes.PointGeometry:  # Point
                series_vtx_bericht['feature_id'] = feature_id_temp
                line_feature = get_line_to_check(geom, layer_gew, spatial_index_gew)
                if line_feature:
                    if not check_vtx_distance(geom, line_feature.geometry()):
                        # Distanz zum naechsten Gewaesser zu gross
                        series_vtx_bericht['Lage'] = 1
                    else:
                        continue
                else:
                    # kein Gewaesser in der Naehe gefunden
                    series_vtx_bericht['Lage'] = 1
            else:  # Line
                series_vtx_bericht = check_line_geom_on_line(
                    geom,
                    feature_id_temp,
                    layer_gew,
                    spatial_index_gew,
                    with_stat=True
                )
                if (series_vtx_bericht[['Lage', 'Richtung', 'Anzahl']] == 0).all():
                    continue
                series_vtx_bericht['feature_id'] = feature_id_temp
            series_vtx_bericht['geometry'] = geom
            list_vtx_bericht = list_vtx_bericht + [series_vtx_bericht]
    return pd.DataFrame(list_vtx_bericht)


def check_schaechte_auf_rldl(
    layer_key,
    layer,
    layer_steps,
    report_dict,
    params_processing
):
    feedback = params_processing['feedback']
    if 'layer_rldl' in params_processing.keys():
        other_layer = params_processing['layer_rldl']['layer']
    elif 'rohrleitungen' in report_dict.keys():
        other_layer = params_processing['layer_dict']['rohrleitungen']['layer']
    elif 'durchlaesse' in report_dict.keys():
        other_layer = params_processing['layer_dict']['durchlaesse']['layer']
    else:
        other_layer = None
    if not other_layer:
        return pd.DataFrame()
    else:
        spatial_index_other =  QgsSpatialIndex(other_layer.getFeatures())
        list_schacht_rldl = []
        
        # Der DataFrame mit der Lageueberpruefung der Schaechte auf dem Gewaesser
        df_schacht_auf_gw = (
            report_dict
                [layer_key]
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
            if not geom:
                continue
            if check_geometry_multi(geom, geom_empty=False):
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
            # Fehler auf Gewaesser: wenn nicht in df_schacht_auf_gw, dann auch kein Fehler
            fehler_auf_gew = feature_id in list(df_schacht_auf_gw['feature_id'])
            if schacht_auf_rldl and (not fehler_auf_gew):
                # korrekt
                continue
            elif (not fehler_auf_gew) and (not schacht_auf_rldl):
                # Fehler: schacht auf offenem gewaesser
                list_schacht_rldl = list_schacht_rldl + [[feature_id, 1, geom]]
            elif fehler_auf_gew and schacht_auf_rldl:
                # Fehler: rldl verschoben
                list_schacht_rldl = list_schacht_rldl + [[feature_id, 2, geom]]
            else:
                # Fehler: schacht weder auf gewaesser noch auf rldl
                list_schacht_rldl = list_schacht_rldl + [[feature_id, 3, geom]]

        return pd.DataFrame(
            list_schacht_rldl, columns = [
                'feature_id',
                'Lage_rldl',
                'geometry'
            ]
        )


# Ueberlappungsanalyse anhand der Stationierung
def handle_tests_overlap(
    layer_steps,
    layer_key,
    skip_dict,
    report_dict,
    params_processing
):
    """
    :param str layer_key
    :param float layer_steps
    :param dict skip_dict
    :param dict report_dict
    :param dict params_processing
    """
    feedback = params_processing['feedback']
    if not skip_dict['skip_geom_overlap']:
        if layer_key == 'layer_rldl':
            feedback.setProgressText('--- Überlappungen (RL und DL gemeinsam)')
        else:
            feedback.setProgressText('--- Überlappungen')
        list_overlap = check_overlap_by_stat(params_processing, report_dict, layer_steps)
        if len(list_overlap) > 0:
            df_overlap = pd.DataFrame(list_overlap, columns = ['id1', 'id2', 'geometry'])
            report_dict[layer_key]['geometrien']['geom_overlap'] = df_overlap