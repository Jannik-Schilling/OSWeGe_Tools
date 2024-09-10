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


def check_geometrie_leer(geom):
    '''
    :param QgsGeomertry geom
    '''
    if geom.isEmpty():
        return oswDataFeedback.GEOM_EMPTY
    else:
        return 0

def check_geometrie_multi(geom):
    '''
    :param QgsGeomertry geom
    '''
    if geom.isEmpty():
        return 0
    else:
        if geom.isMultipart():
            geom_poly = geom.asMultiPolyline() 
        else:
            geom_poly = [f for f in geom.parts()]
        if len(geom_poly) > 1:
            return oswDataFeedback.GEOM_MULTI
        else:
            return 0

def check_geometrie_selbstueberschneidung(geom):
    '''
    :param QgsGeomertry geom
    '''
    if not geom.isSimple() and (not geom.isEmpty()):
        return oswDataFeedback.GEOM_SELFINTERSECT
    else:
        return 0
    
def check_geometrie_ueberschneidung_mit_anderen(geom, fid, df_gew):
    '''
    :param QgsGeomertry geom
    :param int fid
    :param pd.df df_gew
    '''
    geomlist = df_gew['geometrie']
    lst = [i for i, g in enumerate(geomlist) if geom.crosses(g)]
    if len(lst) > 0:
        inters_fids = [df_gew.loc[i, 'id'] for i in lst]
        return oswDataFeedback.GEOM_INTERSECT, [fid]+inters_fids
    else:
        return 0

def check_geometrie_duplikat(
    geom,
    i,
    geomlist,
    with_id = False,
    df_gew = None,
):
    '''
    :param QgsGeometry geom
    :param int fid
    :param list geomlist
    '''
    lst = [j for j, g in enumerate(geomlist) if geom.equals(g)]
    if i in lst:
        lst.remove(i)
    if len(lst) > 0:
        if with_id:
            if not isinstance(df_gew, pd.DataFrame):
                raise TypeError("NoneType!")
            else:
                fid = df_gew.loc[i, 'id']
                dupl_fids = df_gew.loc[lst, 'id'].tolist()
                return oswDataFeedback.GEOM_DUPLICAT, [fid]+dupl_fids
        else:
            return oswDataFeedback.GEOM_DUPLICAT
    else:
        return 0


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
        if all([x == oswDataFeedback.GEOM_DUPLICAT for x in check_dupl_list]):
            if senke:
                return oswDataFeedback.GEOM_SENKE, [fid]+intersecting_lines
            else:
                return oswDataFeedback.GEOM_WASSERSCHEIDE, [fid]+intersecting_lines
        else:
            return 0


def get_vtx(line_geom, vtx_index):
    if line_geom.isMultipart():
        pt = QgsPoint(line_geom.asMultiPolyline()[vtx_index][vtx_index])
    else: 
        pt = QgsPoint(line_geom.asPolyline()[vtx_index])
    return QgsGeometry(pt)