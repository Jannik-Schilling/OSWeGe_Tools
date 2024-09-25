from qgis.core import (
    QgsProcessingFeedback,
    NULL,
    Qgis,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPoint,
    QgsProcessingFeatureSourceDefinition,
    QgsRectangle,
    QgsSpatialIndex
)

from qgis.gui import (
    QgsMessageBar,
    QgisInterface
)
from qgis import processing

import pandas as pd


def lst_replace(lst, dict_repl):
    new_list = []
    for elem in lst:
        if (type(elem)==list) or (type(elem)==tuple):
            sublist = lst_replace(elem, dict_repl)
            new_list.append(sublist)
        else:
            if elem in dict_repl.keys():
                new_list.append(dict_repl[elem])
            else:
                new_list.append(elem)
    return (new_list)

def get_line_to_check(geom, other_layer):
    """
    Ermittelt mithilfe einer Boundingbox ein Linienobjekt aus dem other_layer, auf dem geom liegen könnte
    :param geom
    :param other_layer
    """
    spatial_index_other = QgsSpatialIndex(other_layer.getFeatures())
    if geom.type() == 0:  # Point
        intersecting_ids = spatial_index_other.intersects(geom.boundingBox().buffered(0.2))
        list_vtx_geom = [geom]
    else:
        intersecting_ids = spatial_index_other.intersects(geom.boundingBox())
        list_vtx_geom = [QgsGeometry(vtx) for vtx in geom.vertices()]
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

def check_duplicates_crossings(
    layer,
    feedback,
    layer_steps,
):
    """
    :param QgsVectorLayer layer,
    :param QgsProcessingFeedbackfeedback,
    :param float layer_steps,
    :param str field_alternative_id: Feldname für eine andere id()
    """
    list_geom_duplicate = []
    list_geom_crossings = []
    visited_groups_crossings = set()
    visited_groups_equal = set()
    spatial_index = QgsSpatialIndex(layer.getFeatures())
    for i, feature in enumerate(layer.getFeatures()):
        feedback.setProgress(i+1*layer_steps)
        geom = feature.geometry()
        feature_id = feature.id()
        if geom.isEmpty():
            continue
        if geom.type() == 0:  # Point
            intersecting_ids = spatial_index.intersects(geom.boundingBox().buffered(0.2))
        else:
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
    return list_geom_crossings, list_geom_duplicate


def check_vtx_distance(vtx_geom, geom2, tolerance=1e-6):
    """
    Prüft, ob der vtx maximal die Toleranz x von einer zweiten Geometrie entferne ist
    :param QgsGeometry vtx_geom
    :param QgsGeometry geom
    :param float tolerance
    :return: bool
    """
    return geom2.distance(vtx_geom) <= tolerance


def check_geom_on_line(geom, gew_layer, with_stat=False):
    """
    Prüft ob sich eine eine Geometrie (geom) korrekt auf einem anderen Linienobjekt des layers gew_layer befindet
    :param QgsGeometry (Line) geom
    :param QgsVectorLayer (Line) gew_layer
    :param bool with_stat: Rückgabe der Staionierung?; default: False
    :return: dict
    """
    dict_vtx_bericht = {}  # Fehlermeldungen siehe defaults.dict_ereign_fehler
    other_line_ft = get_line_to_check(geom, gew_layer)
    gew_i_geom = other_line_ft.geometry()
    list_gew_stat = []
    list_vtx_geom = [QgsGeometry(vtx) for vtx in geom.vertices()]
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
        stationierung = first_segment_geom.length()
        list_gew_stat.append(stationierung)
    if with_stat:
        dict_vtx_bericht['gew_id'] = other_line_ft.id()
        dict_vtx_bericht['vtx_stat'] = list_gew_stat
    # Den Linienabschnitt zum Vergleich generieren
    gew_layer.selectByIds([other_line_ft.id()])
    sub_line_layer = processing.run(
        "native:linesubstring",
            {
                'INPUT': QgsProcessingFeatureSourceDefinition(
                    gew_layer.id(),
                    selectedFeaturesOnly=True,
                    featureLimit=-1,
                    geometryCheck=QgsFeatureRequest.GeometryAbortOnInvalid
                 ),
                'START_DISTANCE': list_gew_stat[0],
                'END_DISTANCE': list_gew_stat[-1],
                'OUTPUT':'memory:'
            }
        )['OUTPUT']
    sub_line = [ft for ft in sub_line_layer.getFeatures()][0]
    gew_layer.selectByIds([])  # reset Selection
    list_sub_line_vtx_geom = [QgsGeometry(vtx) for vtx in sub_line.geometry().vertices()]
    if len(list_vtx_geom) > len(list_sub_line_vtx_geom):
        dict_vtx_bericht['Anzahl'] = 1
    if len(list_vtx_geom) < len(list_sub_line_vtx_geom):
        dict_vtx_bericht['Anzahl'] = 2
    if len(list_vtx_geom) == len(list_sub_line_vtx_geom):
        dict_vtx_bericht['Anzahl'] = 0
        list_point_on_line = []
        for vtx_geom, vtx_subline in zip(list_vtx_geom, list_sub_line_vtx_geom):
            list_point_on_line.append(check_vtx_distance(vtx_geom, vtx_subline))
        if not all(list_point_on_line):
            dict_vtx_bericht['Lage'] = 1
        else:
            dict_vtx_bericht['Lage'] = 0
    return dict_vtx_bericht

def check_geometrie_konnektivitaet(
    pt_geom,
    fid,
    index_gew,
    layer_gew,
    distanz_suchen=0
):
    """
    :param QgsGeometry (Point) geom
    :param int fid: feature id im layer_gew
    :param QgsSpatialIndex index_gew
    :param QgsVectorLayer (line) layer_gew
    :param int distanz_suchen
    """
    pt = pt_geom.asPoint()
    rectangle = QgsRectangle(
            pt.x() - distanz_suchen,
            pt.y() - distanz_suchen,
            pt.x() + distanz_suchen,
            pt.y() + distanz_suchen
        )
    intersections = index_gew.intersects(rectangle)
    if len(intersections) > 0:
        if fid in intersections:
            # selbst entfernen
            intersections.remove(fid)
        for line_id in intersections:
            # nicht schneidende entfernen
            line_geom = layer_gew.getFeature(line_id).geometry()
            if not pt_geom.intersects(line_geom):
                intersections.remove(line_id)
    return intersections

def check_geometrie_wasserscheide_senke(
    geom,
    fid,
    index_gew,
    layer_gew,
    senke=False,
    **kwargs
):
    '''
    :param QgsGeomertry geom
    :param int fid
    :param QgsSpatialIndex index_gew
    :param QgsVectorLayer (line) layer_gew
    :param bool senke
    '''
    if senke:
        vtx_num = 0
    else:
        vtx_num = -1
    vtx = get_vtx(geom, vtx_num)
    intersecting_lines = check_geometrie_konnektivitaet(
        vtx,
        fid,
        index_gew,
        layer_gew
    )
    if len(intersecting_lines) == 0:
        return 0 # Quelle oder Muendung
    else:
        check_dupl_list = []
        for line_id in intersecting_lines:
            inters_line_geom = layer_gew.getFeature(line_id).geometry()
            check_vtx = get_vtx(inters_line_geom, vtx_num)  # der zu pruefende Stuetzpunkt
            check_dupl_list = check_dupl_list + [check_geometrie_duplikat(
                vtx,
                0,
                [vtx, check_vtx]
            )]
        if all([x == 1 for x in check_dupl_list]):
            if senke:
                return 1, [fid]+intersecting_lines
            else:
                return 2, [fid]+intersecting_lines
        else:
            return 0


def get_vtx(line_geom, vtx_index):
    if line_geom.isMultipart():
        pt = QgsPoint(line_geom.asMultiPolyline()[vtx_index][vtx_index])
    else: 
        pt = QgsPoint(line_geom.asPolyline()[vtx_index])
    return QgsGeometry(pt)