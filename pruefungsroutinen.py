from qgis.core import (
    QgsGeometry,
    QgsPoint,
    QgsSpatialIndex
)

import pandas as pd

# get-Funktionen
def get_line_candidates_ids(geom, other_layer, spatial_index_other, tolerance=0.2):
    """
    Ermittelt mithilfe einer Boundingbox die ids von Linienobjekten aus dem other_layer, auf dem geom liegen könnte
    :param QgsGeometry geom
    :param other_layer
    :param QgsSpatialIndex spatial_index_other
    :param float tolerance: Suchraum bei Punkten: default 0.2
    :return: list
    """
    if geom.type() == 0:  # Point
        intersecting_ids = spatial_index_other.intersects(geom.boundingBox().buffered(tolerance))
    else:
        intersecting_ids = spatial_index_other.intersects(geom.boundingBox())
    return intersecting_ids

def get_line_to_check(geom, other_layer, spatial_index_other):
    """
    Ermittelt mithilfe einer Boundingbox EIN Linienobjekt aus dem other_layer, auf dem geom liegen könnte
    :param QgsGeometry geom
    :param other_layer
    :param QgsSpatialIndex spatial_index_other
    :return: QgsFeature
    """
    if geom.type() == 0:  # Point
        list_vtx_geom = [geom]
    else:
        list_vtx_geom = [QgsGeometry(vtx) for vtx in geom.vertices()]
    intersecting_ids = get_line_candidates_ids(geom, other_layer, spatial_index_other)
    if len(intersecting_ids)==0:
        return
    else:
        # eines oder mehrere Gewaesser gefunden
        list_sum = []
        for gew_id in intersecting_ids:
            # identifiziere das Gewaesser mit dem geringsten Abstand der Stützpunkte in Summe
            gew_ft_candidate = other_layer.getFeature(gew_id)
            list_sum.append(sum([gew_ft_candidate.geometry().distance(vtx) for vtx in list_vtx_geom]))
        position_in_list = list_sum.index(min(list_sum))
        line_feature = other_layer.getFeature(intersecting_ids[position_in_list])
        return line_feature

def get_vtx(line_geom, vtx_index):
    """
    Gibt den Stuetzpunkt einer Liniengeometrie mit dem index vtx_index als QgsGeometry zurück
    :param QgsGeometry line_geom
    :param int vtx_index
    :return QgsGeometry
    """
    if line_geom.isMultipart():
        pt = QgsPoint(line_geom.asMultiPolyline()[vtx_index][vtx_index])
    else: 
        pt = QgsPoint(line_geom.asPolyline()[vtx_index])
    return QgsGeometry(pt)

# fuer alle
def check_duplicates_crossings(
    layer,
    feedback,
    layer_steps,
):
    """
    Ueberprueft ob es im Layer Geometrie-Duplikate oder Ueberschneidungen gibt
    :param QgsVectorLayer layer,
    :param QgsProcessingFeedbackfeedback,
    :param float layer_steps,
    """
    list_geom_duplicate = []
    list_geom_crossings = []
    visited_groups_crossings = set()
    visited_groups_equal = set()
    spatial_index = QgsSpatialIndex(layer.getFeatures())
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
        column_names = ['id1', 'id2', 'geometry']
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
    print(list_geom_crossings)
    df_geom_crossings = pd.DataFrame(list_geom_crossings, columns = column_names)
    df_geom_duplicate = pd.DataFrame(list_geom_duplicate, columns = column_names)
    return df_geom_crossings, df_geom_duplicate


def check_vtx_distance(vtx_geom, geom2, tolerance=1e-6):
    """
    Prueft, ob der vtx maximal die Toleranz x von einer zweiten Geometrie entfernt ist
    :param QgsGeometry vtx_geom
    :param QgsGeometry geom
    :param float tolerance
    :return: bool
    """
    return geom2.distance(vtx_geom) <= tolerance


def check_geom_on_line(geom, gew_layer, spatial_index_other, with_stat=False):
    """
    Prueft ob sich eine eine Geometrie (geom) korrekt auf einem anderen Linienobjekt des layers gew_layer befindet
    :param QgsGeometry (Line) geom
    :param QgsVectorLayer (Line) gew_layer
    :param QgsSpatialIndex spatial_index_other
    :param bool with_stat: Rückgabe der Staionierung?; default: False
    :return: dict
    """
    dict_vtx_bericht = {}  
    sr_vtx_report = pd.Series()  # Fehlermeldungen siehe defaults.dict_ereign_fehler
    other_line_ft = get_line_to_check(geom, gew_layer, spatial_index_other)
    sr_vtx_report['gew_id'] = other_line_ft.id()
    gew_i_geom = other_line_ft.geometry()
    list_gew_stat = []
    list_vtx_geom = [QgsGeometry(vtx) for vtx in geom.vertices()]

    # Stationierung
    for vtx in list_vtx_geom:
        # naechster Punkt auf dem Gewässer, als Point XY
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
        stationierung = round(first_segment_geom.length(),5)
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
    for i, part in enumerate(gew_i_geom.parts()):
        if i > 0:
            pass
        else:
            sub_line = part.curveSubstring(list_gew_stat[0] , list_gew_stat[-1])
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
        list_point_on_line.append(check_vtx_distance(vtx_geom, vtx_subline))
    if not all(list_point_on_line):
        sr_vtx_report['Lage'] = 1  # Abweichung
    else:
        sr_vtx_report['Lage'] = 0  # Korrekt
    sr_vtx_report['geometry'] = geom
    return sr_vtx_report


def check_geometrie_wasserscheide_senke(
    geom,
    feature_id,
    layer_gew,
    spatial_index_other,
    senke=False
):
    '''
    :param QgsGeometry geom
    :param int feature_id
    :param QgsVectorLayer (line) layer_gew
    :param QgsSpatialIndex spatial_index_other
    :param bool senke
    :return list
    '''
    if senke:
        vtx_num = 0
    else:
        vtx_num = -1
    vtx = get_vtx(geom, vtx_num)  # QgsGeometry
    intersecting_lines = get_line_candidates_ids(
        vtx,
        layer_gew,
        spatial_index_other
    )
    if feature_id in intersecting_lines:
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

def check_overlap_by_stat(params, report_dict, layer_steps):
    """
    Ueberprueft die Ueberlappung von Linienereignissen anhand der Stationierung
    :param dict params
    :param dict report_dict
    :param float layer_steps
    """
    feedback = params['feedback']

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
            layer_steps = 1

    # Das Stationierungs-Dict je Gewässer aufbereiten
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

def ranges_overlap(range1, range2):
    """
    Check if two ranges (represented as [f0, f1]) overlap.
    :param list range1
    :param list range2
    """
    id1, f0_1, f1_1, geom1 = range1
    id2, f0_2, f1_2, geom2 = range2
    if f0_1 < f1_2 and f0_2 < f1_1:
        return [id1, id2, geom1]

