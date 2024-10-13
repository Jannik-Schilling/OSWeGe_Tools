# dieses script Enthaelt die Funktionen fuer den Report
from datetime import datetime
import copy

from qgis.core import (
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
            report_dict[key] = {'name': layer.name()}
        else:
            list_remove.append(key)
    for k in list_remove:
        del(params['layer_dict'][k])
    return report_dict


def replace_lst_ids(lst, dict_repl):
    """
    Ersetzt alle einzelnen id-Nummern in der liste lst anhand von dict_repl;
    Funktioniert auch bei einer Liste von Listen
    :param list lst
    :param dict dict_repl
    :return: list
    """
    new_list = []
    for elem in lst:
        if (type(elem)==list) or (type(elem)==tuple):
            sublist = replace_lst_ids(elem, dict_repl)
            new_list.append(sublist)
        else:
            if elem in dict_repl.keys():
                new_list.append(dict_repl[elem])
            else:
                new_list.append(elem)
    return new_list




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
                if rep_section == 'geometrien':
                    # Spezialroutine fuer die Dicts
                    if 'geom_ereign_auf_gew' in report_dict[key]['geometrien'].keys():
                        report_dict[key]['geometrien']['geom_ereign_auf_gew'] = {
                            elem_id: clean_ereign_auf(
                                dict_i
                            ) for elem_id, dict_i in report_dict[key]['geometrien']['geom_ereign_auf_gew'].items() if clean_ereign_auf(dict_i)
                        }
                    if 'geom_schacht_auf_rldl' in report_dict[key]['geometrien'].keys():
                        report_dict[key]['geometrien']['geom_schacht_auf_rldl'] = {
                            elem_id: value for elem_id, value in report_dict[key]['geometrien']['geom_schacht_auf_rldl'].items() if value
                        }
                report_dict[key][rep_section] = {
                    sub_section: elem for sub_section, elem in report_dict[key][rep_section].items() if len(elem) != 0
                }
                if len(report_dict[key][rep_section]) == 0:
                    del report_dict[key][rep_section]

def clean_ereign_auf(dict_i):
    """
    Bereinigt die Unterabschnitte 'geom_ereign_auf_gew', 'geom_schacht_auf_rldl' im report_dict
    :param dict dict_i
    """
    del_log_list = [1,1,1]  # 0, wenn eines nicht geaendert wird
    dct_i_copy = copy.deepcopy(dict_i)
    if 'Lage' in dct_i_copy.keys():
        if dct_i_copy['Lage'] == 0:
            del dct_i_copy['Lage']
        else:
            del_log_list[0] = 0
    if 'Richtung' in dct_i_copy.keys():
        if dct_i_copy['Richtung'] == 0:
            del dct_i_copy['Richtung']
        else:
            del_log_list[1] = 0
    if 'Anzahl' in dct_i_copy.keys():
        if dct_i_copy['Anzahl'] == 0:
            del dct_i_copy['Anzahl']
        else: 
            del_log_list[2] =0
    if all(del_log_list):
        return
    else:
        if 'gew_id' in dct_i_copy.keys():
            del dct_i_copy['gew_id']
        if 'vtx_stat' in dct_i_copy.keys():
            del dct_i_copy['vtx_stat']
        return dct_i_copy



# Funktionen fuer die Layerausgabe
def write_report_layer(layer_typ):
    """
    :param str layer_typ
    :return: QgsVectorLayer
    """
    geom_type = 'NoGeometry'  # einfache Tabellen
    vector_layer = QgsVectorLayer(geom_type, layer_typ, 'memory')  # layer_typ wird der name
    vector_layer.startEditing()
    column_name = 'test'
    if not column_name in vector_layer.fields().names():
        field_type = field_types_dict[field_type_string]
        # QgsField is deprecated since QGIS 3.38 -> QMetaType
        vector_layer.addAttribute(QgsField(colum_name, QVariant.Int))
    vector_layer.updateFields()
    # Layer anlegen: 
        # wenn Spalte nicht vorhanden: anlegen

    # Objekt: 
    feature_list = []
    ft = QgsFeature()
    attrlist = [1]
    ft.setAttributes(attrlist)
    feature_list.append(ft)
    vector_layer.addFeatures(feature_list)
    vector_layer.updateExtents()
    vector_layer.commitChanges()
        # wenn nicht vorhanden: anlegen
        # Fehler als dict mit Spaltennamen:
            # wenn Liste, dann einfacher Eintrag
            # wenn dict, dann in default nachsehen
            
        
def add_rldl_to_layer(layer):
    """
    :param QgsVectorLayer layer
    :return: QgsVectorLayer
    """
    pass
    # einmal für rl einmal für dl
    # neue spalten anlegen
    # geom_crossing und geom_overlap: 
        # mit for ... wenn beider größer als id, continue
        # split bei ': ' -> layer, id
        # wenn schon da, dann crossing hinzu, sonst
        # 'Überschneidung mit'
    # geom_ereig_auf_gew:
        # wie oben mit dict
    
    
