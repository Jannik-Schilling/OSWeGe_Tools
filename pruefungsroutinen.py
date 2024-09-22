from qgis.core import (
    QgsProcessingFeedback,
    NULL,
    Qgis,
    QgsPoint,
    QgsGeometry,
    QgsRectangle
)

from qgis.gui import (
    QgsMessageBar,
    QgisInterface
)

import pandas as pd

oswDataFeedback = None
def check_vtx_distance(vtx_geom, geom2, tolerance=1e-6):
    """
    Prüft, ob der vtx maximal die Toleranz x von einer zweiten Geometrie entferne ist
    :param QgsGeometry vtx_geom
    :param QgsGeometry geom
    :return: bool
    """
    return geom2.distance(vtx_geom) <= tolerance

def check_vtx_on_line(list_vtx_geom, gew_i_geom):
    """
    :param list vtx_geom_list: list of QgsGeometry
    :param QgsGeometry gew_i_geom
    """
    list_point_on_line = []
    list_gew_vtx_id = []
    list_gew_stat = []
    for vtx in list_vtx_geom:
        # naechster Punkt auf dem Gewässer, als Point XY
        nearest_gew_point = gew_i_geom.nearestPoint(vtx)
        nearest_gew_xy = nearest_gew_point.asPoint()
        # Distanz zur Linie
        list_point_on_line.append(check_vtx_distance(vtx, gew_i_geom))
        # naechster Stuetzpunkt danach
        result_tuple = gew_i_geom.closestSegmentWithContext(nearest_gew_xy)
        list_gew_vtx_id.append(result_tuple[2])
        if gew_i_geom.isMultipart():
            gew_i_geom_polyline = gew_i_geom.asMultiPolyline()
            first_segment = gew_i_geom_polyline[0][:result_tuple[2]]+[result_tuple[1]]
        else:
            gew_i_geom_polyline = gew_i_geom.asPolyline()
            first_segment = gew_i_geom_polyline[:result_tuple[2]]+[result_tuple[1]]
        first_segment = [QgsPoint(p) for p in first_segment]
        first_segment_geom = QgsGeometry.fromPolyline(first_segment)
        stationierung = round(first_segment_geom.length(),2)
        list_gew_stat.append(stationierung)
    print(list_point_on_line)
    print(list_gew_vtx_id)
    print(list_gew_stat)

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