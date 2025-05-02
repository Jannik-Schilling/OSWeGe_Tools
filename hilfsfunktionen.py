import time

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsProcessingException

)
from qgis import processing

from .defaults import (
    default_report_geoms,
    dict_report_texts
)


# Zeitlogger
class simpleTimeStepLogger:
    """
    Ein Zeitlogger für alle Schritte
    """
    def __init__(self):
        self.dict_log = {}
    def start_logging (self):
        self.dict_log['last_time'] = time.time()
        self.dict_log['Startzeitpunkt'] = self.dict_log['last_time']
    def log_time(self, stepname):
        """
        Schreibt die Zeiten der einzelnen Schritte mit
        :param str stepname
        :param bool is_start
        """
        if not 'last_time' in self.dict_log.keys():
            raise QgsProcessingException('Fehler im Logger: keine aktuelle Zeit (\'last_time\')')
        else:
            last_time = self.dict_log['last_time']
        if stepname:
            self.dict_log[stepname] = round(time.time() - last_time,2)
            self.dict_log['last_time'] = time.time()
    def clear_log(self):
        self.dict_log = {}
    def report_time_logs(self):
        timing_txt = [
            str(k)+': '+str(v) for k, v in self.dict_log.items() if k not in [
                'Startzeitpunkt',
                'last_time'
            ]
        ]
        self.clear_log()
        return timing_txt
    def __del__(self):
        self.clear_log()



# "Get"-Funktionen
def get_vtx(line_geom, vtx_index):
    """
    Gibt den Stuetzpunkt einer Liniengeometrie mit dem index vtx_index als QgsGeometry zurück
    :param QgsGeometry line_geom
    :param int vtx_index
    :return QgsGeometry
    """
    if line_geom.isMultipart():
        vtx_lst = [vtx for lst in line_geom.asMultiPolyline() for vtx in lst]
        pt = QgsPoint(vtx_lst[vtx_index])
    else: 
        pt = QgsPoint(line_geom.asPolyline()[vtx_index])
    return QgsGeometry(pt)


def get_line_to_check(
    geom,
    other_layer,
    spatial_index_other
):
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
    intersecting_ids = get_line_candidates_ids(geom, spatial_index_other)
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


def get_line_candidates_ids(
    geom,
    spatial_index_other,
    tolerance=0.2
):
    """
    Ermittelt mithilfe einer Boundingbox die ids von Linienobjekten aus dem other_layer, auf dem geom liegen könnte
    :param QgsGeometry geom
    :param QgsSpatialIndex spatial_index_other
    :param float tolerance: Suchraum bei Punkten: default 0.2
    :return: list
    """
    if geom.type() == 0:  # Point
        intersecting_ids = spatial_index_other.intersects(geom.boundingBox().buffered(tolerance))
    else:
        intersecting_ids = spatial_index_other.intersects(geom.boundingBox())
    return intersecting_ids



def get_geom_type(error_name_long, layer_key=None):
    """
    Ermittelt den passenden Geometrietyp (Point, Linstring, NoGeometry) fuer den Output-Layer
    :param str errror_type
    :param str layer_key
    :return str: Geometrietyp
    """
    error_name = [k for k, v in dict_report_texts.items() if error_name_long == v][0]
    geom_type = default_report_geoms[error_name]
    if isinstance(geom_type, dict):
        return geom_type[layer_key]
    else:
        return geom_type

# layerfunktionen
def handle_rl_and_dl( 
    layer_rohrleitungen,
    layer_durchlaesse,
    params_processing,
    report_dict,
    report_object=None
):
    """
    Falls rl und dl vorhanden sind werden sie zu einem Layer zusammengefuehrt
    Dazu wird ein Eintrag in params_processing und report_dict erstellt
    :param QgsVectorLayer layer_rohrleitungen
    :param QgsVectorLayer layer_durchlaesse
    :param dict params_processing: alle benannten Parameter
    :param dict report_dict
    :param layerReport report_object: Report-Objekt, falls vorhanden
    """
    if layer_rohrleitungen and layer_durchlaesse:
        layer_rldl = merge_rl_dl(
            params_processing
        )
    
        # Zu params_processing: Anzeige, ob die Pruefroutinen des Layers schon durchlaufen wurden
        params_processing['layer_rldl'] = {
            'layer': layer_rldl,
            'runs': {  
                'check_duplicates_crossings': False,  
                'check_geom_ereign_auf_gew': False,
                'check_overlap_by_stat': False
            },
        }
        report_object.add_rldl()
        report_dict['layer_rldl'] = {'geometrien':{}}

def merge_rl_dl(
    params
):
    """
    Fuehrt die Layer rl und dl zu einem neuen Layer zusammen
    :param dict params: alle benannten Parameter
    :return QgsVectorLayer
    """
    #log_time('Zusammenfassen')
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
    return layer_rldl


# geometriefunktionen
def linie_verlaengern(
    n,
    vtx_muendung,
    dist_verl,
    delta_x_laenge1,
    delta_y_laenge1,
    layer_fg_1ordnung,
    spatial_index_fg_1ordnung,
):
    x_muendung = vtx_muendung.asPoint().x()
    y_muendung = vtx_muendung.asPoint().y()
    x_neu = x_muendung - (n*dist_verl*delta_x_laenge1)
    y_neu = y_muendung - (n*dist_verl*delta_y_laenge1)
    line_neu = QgsGeometry(
        QgsLineString([
            QgsPoint(x_neu, y_neu),
            vtx_muendung.asPoint()
        ])
    )
    intersecting_candidates = get_line_candidates_ids(
        line_neu,
        spatial_index_fg_1ordnung
    )
    intersecting_ids = [
        ft_id for ft_id in intersecting_candidates if layer_fg_1ordnung.getFeature(ft_id).geometry().intersects(line_neu)
    ]
    if len(intersecting_ids) == 0:
        return (False, )
    elif len(intersecting_ids) == 1:
        geom_ft_1ordnung = layer_fg_1ordnung.getFeature(intersecting_ids[0]).geometry()
        schnittpunkt = geom_ft_1ordnung.intersection(line_neu)
        line_ae = QgsGeometry(
            QgsLineString([
                schnittpunkt.asPoint(),
                vtx_muendung.asPoint()
            ])
        )
        ft_ae = QgsFeature()
        ft_ae.setGeometry(line_ae)
        return (True, ft_ae)
    else:
        raise QgsProcessingException(f'zu viele Schnittpunkte beim Verlängern mit Gew. 2. Ordnung: {intersecting_ids}')
        return (False, )

def ranges_overlap(range1, range2):
    """
    Ueberprueft, ob sich zwei Ranges ueberschneiden (f0, f1).
    :param list range1
    :param list range2
    """
    id1, f0_1, f1_1, geom1 = range1
    id2, f0_2, f1_2, geom2 = range2
    if f0_1 < f1_2 and f0_2 < f1_1:
        return [id1, id2, geom1]
    
def sub_line_by_stats(
    line_geom,
    stat_start,
    stat_end
):
    """
    Erstellt einen Linienteil anhand zweier Stationierungen (Start, Ende)
    :param QgsGeometry line_geom
    :param float stat_start
    :param float stat_end
    :return: QgsGeometry or None if line_geom is mulitpart
    """
    line_parts = [f for f in line_geom.parts()]
    if len(line_parts) > 1:
        print(line_parts)  # TODO: create warning or raise error
    line_part_0 = line_parts[0]
    #if line_part_0.length() < stat_end:
    #    pass  # create warnong or raise error
    sub_line = line_part_0.curveSubstring(stat_start , stat_end)
    return sub_line


# Setup fuer Tests
def setup_localparams_for_tests_with_comparisons(
    layer_key,
    params_processing
):
    """
    Bereitet die Tests fuer Vergleiche mit anderen Geometrie-Objekten vor
    :param str layer_key
    :param dict params_processing
    :return: dict
    """
    temp_key = layer_key
    temp_layer = params_processing['layer_dict'][temp_key]['layer']
    temp_layer_steps = params_processing['layer_dict'][layer_key]['steps']
    use_field_merged_id = False
    skip_dict = {
        # Vergleiche innerhalb eines Layers
        'skip_geom_duplicates_crossings': False,
        'skip_geom_overlap': True,
        'skip_geom_wasserscheiden_senken': True,
        # Vergleiche mit anderen Layern
        'skip_geom_ereign_auf_gew': False,
        'skip_geom_schacht_auf_rldl': True
    }
    if layer_key == 'gewaesser':
        skip_dict['skip_geom_wasserscheiden_senken'] = False
        skip_dict['skip_geom_ereign_auf_gew'] = True
    if layer_key in ['rohrleitungen', 'durchlaesse']:
        skip_dict['skip_geom_overlap'] = False
        if 'layer_rldl' in params_processing.keys():  # beide vorhanden
            temp_key = 'layer_rldl'
            temp_layer = params_processing[temp_key]['layer']
            temp_layer_steps = 100/temp_layer.featureCount()
            use_field_merged_id = True
            if params_processing['layer_rldl']['runs']['check_duplicates_crossings']:
                # falls der Test schon einmal mit rldl durchlaufen wurde
                skip_dict['skip_geom_duplicates_crossings'] = True
            else:
                # Setze den Parameter auf True, damit der Test nicht noch einmal mit rldl durchlaufen wird
                params_processing['layer_rldl']['runs']['check_duplicates_crossings'] = True
            if params_processing['layer_rldl']['runs']['check_overlap_by_stat']:
                # falls der Test schon einmal mit rldl durchlaufen wurde
                skip_dict['skip_geom_overlap'] = True
            else:
                # Setze den Parameter auf True, damit der Test nicht noch einmal mit rldl durchlaufen wird
                params_processing['layer_rldl']['runs']['check_overlap_by_stat'] = True
            if params_processing['layer_rldl']['runs']['check_geom_ereign_auf_gew']:
                skip_dict['skip_geom_ereign_auf_gew'] = True
            else:
                params_processing['layer_rldl']['runs']['check_geom_ereign_auf_gew'] = True
    if layer_key == 'schaechte':
        skip_dict['skip_geom_schacht_auf_rldl'] = False
        if not (('rohrleitungen' in params_processing['layer_dict'].keys()) or ('durchlaesse' in params_processing['layer_dict'].keys())):
            skip_dict['skip_geom_schacht_auf_rldl'] = True
    if layer_key == 'wehre':
        pass
    return temp_key, temp_layer, temp_layer_steps, skip_dict, use_field_merged_id


def check_path_in_dict(dict_to_check, key_list):
    """
    Ueberprueft, ob der Pfad key_list in dict_to_check existiert
    :param dict dict_to_check
    :param list key_list: Liste mit den Schluesseln des Pfades
    :return: bool
    """
    key = key_list[0]
    if key in dict_to_check.keys():
        return check_path_in_dict(dict_to_check[key], key_list[1:])
    else:
        return False