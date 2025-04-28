import pandas as pd
from .hilfsfunktionen import log_time

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
    
def check_single_geometries(layer, layer_key, feedback, layer_steps, report_dict):
    """
    Diese Funktion prueft die Geometrien auf Leere, Multigeometrien und Selbstueberschneidungen
    :param QgsVectorLayer layer
    :param QgsProcessingFeedback feedback
    :param float layer_steps
    """
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
        if check_geometry_multi(geom, geom_empty):  # Multi?
            list_geom_is_multi.append(feature.id())
        if check_geometry_selfintersect(geom, geom_empty):  # Selbstueberschneidungen
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
    log_time((layer_key+'_geom_leer_etc_write'))