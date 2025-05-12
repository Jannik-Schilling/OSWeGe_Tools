from qgis.core import (
    QgsGeometry
)

from .hilfsfunktionen import (
    get_line_candidates_ids,
    get_line_to_check
)

from .geometriepruefungen import check_vtx_distance

# fuer alle
def muendet_nicht_in_fg_2ordnung(
    current_ft_fg,
    spatial_index_fg,
    layer_fg
):
    """
    Ueberprueft, ob ein Objekt des Layers fg in ein anderes objekt des selben Layers muendet.
    :param QgsFeature current_ft_fg
    :param QgsSpatialIndex spatial_index_fg
    :param QgsVectorLayer layer_fg
    :return bool
    """
    current_ft_id = current_ft_fg.id()
    vtx_muendung = QgsGeometry(current_ft_fg.geometry().vertexAt(0))
    intersecting_candidates_1 = get_line_candidates_ids(vtx_muendung, spatial_index_fg)
    if current_ft_id in intersecting_candidates_1:
        # die eigene id() entfernen
        intersecting_candidates_1.remove(current_ft_id)
    intersecting_ids = [
        ft_id for ft_id in intersecting_candidates_1 if check_vtx_distance(
            layer_fg.getFeature(ft_id).geometry(),
            vtx_muendung,
            1e-5
        )
    ]
    return len(intersecting_ids)==0  # True wenn keines schneidet
