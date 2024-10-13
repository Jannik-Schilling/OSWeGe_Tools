# dieses script Enthaelt die Funktionen fuer den Report
from datetime import datetime
import copy

from qgis.core import (
    NULL,
    QgsField,
    QgsFeature,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from .defaults import dict_report_texts


def create_report_dict(params, is_test_version=False):
    """
    Erstellt das Dictionary, dass alle Informationen fuer den Bericht enthaelt
    Aufbau:     
    report_dict = {
        'gewaesser': {
            'name': 'so heisst die Datei',
            'attribute': {
                'missing_fields': [],
                'primary_key_empty': [id1, id2],
                'primary_key_duplicat': [[id3, id4],[id5, id6, id7]]
            },
            'geometrien': {
                'fehler1': [],
                'fehler2': []
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
                'fehler1': [],
                'fehler2': []
            }
        }
    }
    :param dict params: ein Dictionary mit allen wichtigen Parametern fuer die Pruefungsroutine
    :param bool is_test_version: True, wenn die Funktion in einer Testversion laeuft und ein entsprechender Hinweis in die Datei geschrieben wird
    :return: dict
    """
    report_dict = {}
    if is_test_version:
        report_dict['Hinweis'] = (
            'Diese Datei wurde noch mit einer Testversion '
            + 'des Plugins erstellt und enthält daher bisher '
            + 'nur die Feature-Ids der fehlerhaften Objekte sowie einen '
            + 'Verweis auf die Fehlerart als (numerischer) Code'
        )
    for key, value in params['layer_dict'].items():
        layer = value['layer']
        list_remove = []
        if layer:
            # Anzahl Objekte fuer das Feedback
            ft_count = layer.featureCount() if layer.featureCount() else 0
            layer_steps = 100.0/ft_count if ft_count != 0 else 0
            params['layer_dict'][key].update({
                'count': ft_count,
                'steps': layer_steps
            })
            report_dict[key] = {
                'name': layer.name(),
                'attribute': {},
                'geometrien': {}
            }
        else:
            list_remove.append(key)
    for k in list_remove:
        del(params['layer_dict'][k])
    return report_dict


def replace_lst_ids(series_i, dict_repl):
    """
    Ersetzt alle einzelnen id-Nummern anhand von dict_repl;
    Funktioniert auch bei einer Liste von Listen
    :param pd.Series series_i
    :param dict dict_repl
    :return: pd.Series
    """
    for col_nam, id_val in series_i.items():
        if id_val in dict_repl.keys():
            series_i[col_name] = dict_repl[elem]
        else:
            pass
    return series_i




# Aufraeumfunktionen
def clean_report_dict(report_dict, feedback):
    """
    Loescht leere Listen und Dicts im report_dict
    :param dict report_dict
    :param QgsProcessingFeedback feedback
    """
    step_temp = 100/len(report_dict)
    for i, key in enumerate(report_dict.keys()):
        if feedback.isCanceled():
            break
        if key == 'Hinweis':
            continue
        feedback.setProgress(int((i+1) * step_temp))
        for rep_section in ['attribute','geometrien']:
            if not rep_section in report_dict[key].keys():
                pass
            else:
                report_dict[key][rep_section] = {
                    sub_section: elem for sub_section, elem in report_dict[key][rep_section].items() if len(elem) != 0
                }
                if len(report_dict[key][rep_section]) == 0:
                    del report_dict[key][rep_section]


def create_feature_from_attrlist(attrlist, geom_type, f_geometry=NULL):
    """
    creates a QgsFeature from with attributes in a list
    :param list attrlist
    :param str geom_type
    :param QgsGeometry geometry
    """
    f = QgsFeature()
    if geom_type != 'NoGeometry':
       f.setGeometry(f_geometry)
    f.setAttributes(attrlist)
    return f

def create_feature_from_row(df_i, geom_type):
    """
    creates a QgsFeature from data in df
    :param pd.DataFrame df_i
    :param str geom_type
    """
    if 'geometry' in df_i.keys():
        f_geometry = df_i['geometry']
        attrlist = df_i.drop('geometry').tolist()
        return create_feature_from_attrlist(attrlist, geom_type, f_geometry)
    else:
        attrlist = df.tolist()
        return create_feature_from_attrlist(attrlist, geom_type)


def create_layer_from_df(
    data_df,
    layer_name,
    geom_type,
    crs_result,
    feedback,
):
    """
    creates a QgsVectorLayer from data in geodata_dict
    :param pd.DataFrame data_df: [attr1, attr2,..., (geometry)]
    :param str layer_name
    :param str geom_type
    :param str crs_result: epsg code of the desired CRS
    :param QgsProcessingFeedback feedback
    """

    if 'geometry' in data_df.keys():
        layer_fields = data_df.keys()[:-1]
        geom_type = geom_type+'?crs='+crs_result
    else:  # No Geometry
        layer_fields = data_df.keys()
    vector_layer = QgsVectorLayer(geom_type, layer_name, 'memory')  # layer_typ wird der name
    vector_layer.startEditing()
    for  column_name in layer_fields:
        # QgsField is deprecated since QGIS 3.38 -> QMetaType
        vector_layer.addAttribute(QgsField(column_name, QVariant.String))
    vector_layer.updateFields()

    # Objekt: 
    feature_list = data_df.apply(lambda x: create_feature_from_row(x, geom_type), axis=1)
    vector_layer.addFeatures(feature_list)
    vector_layer.updateExtents()
    vector_layer.commitChanges()
    
    return vector_layer
