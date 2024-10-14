# dieses script Enthaelt die Funktionen fuer den Report
from datetime import datetime
import copy
import os

from qgis.core import (
    NULL,
    QgsField,
    QgsFeature,
    QgsProcessingException,
    QgsProject,
    QgsSpatialIndex,
    QgsWkbTypes,
    QgsVectorFileWriter,
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
    list_remove = []
    for key, value in params['layer_dict'].items():
        layer = value['layer']
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
    for col_name, id_val in series_i.items():
        if id_val in dict_repl.keys():
            series_i[col_name] = dict_repl[id_val]
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
        # Ausnahmen und feedback
        if feedback.isCanceled():
            break
        if key == 'Hinweis':
            continue
        feedback.setProgress(int((i+1) * step_temp))
        
        for rep_section in ['attribute','geometrien']:
            if not rep_section in report_dict[key].keys():
                pass
            else:
                # Spalten bearbeiten TODO
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
        layer_fields = [f for f in data_df.keys() if not f=='geometry']
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
    
    
def create_layers_from_report_dict(report_dict, feedback):
    '''
    Generiert für alle Geometrie-Einträge einen Layer
    :param dict report dict
    :return: list
    '''
    vector_layer_list = []
    for layer_key in report_dict.keys():
        if layer_key == 'Hinweis':
            continue
        for rep_section in ['attribute','geometrien']:
            if not rep_section in report_dict[layer_key].keys():
                pass
            else:
                for error_name, error_df in report_dict[layer_key][rep_section].items():
                    if error_name == 'missing_fields':
                        feedback.pushWarning(
                            'Fehlende Felder im '
                            + layer_key.capitalize()
                            +'-Layer: '
                            + ', '.join(error_df)
                        )
                    else:
                        for col in error_df.keys():
                            if col != 'geometry':
                                error_df[col] = [str(f) for f in error_df[col]]
                        if rep_section == 'attribute':
                            geom_type = 'NoGeometry'
                        else:
                            feature1_geom = error_df.loc[0, 'geometry']
                            geom_type = feature1_geom.type().name
                            if geom_type == 'Line':
                                 geom_type = 'LineString'
                            layer_name = layer_key+'_'+error_name
                            layer_neu = create_layer_from_df( 
                                report_dict[layer_key][rep_section][error_name],
                                layer_name,
                                geom_type,
                                'epsg:5650',
                                feedback
                            )
                            vector_layer_list = vector_layer_list+[layer_neu]
    return vector_layer_list
    
    
    
def save_layer_to_file(
    vector_layer_list,
    fname
):
    """
    Schreibt alle Layer in der list in ein Geopackage
    :param list vector_layer_list: Layerliste
    :param str fname: Speicherpfad
    """
    # set driver
    geodata_driver_name = 'GPKG'

    # schreiben layer
    if os.path.isfile(fname):
        raise QgsProcessingException('File '+fname
        + ' already exists. Please choose another folder.')
    try:
        for i, v_layer in enumerate(vector_layer_list):
            fname_layer = fname
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.fileEncoding = 'utf-8'
            options.driverName = geodata_driver_name
            if i > 0:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            options.layerName = v_layer.name()
            transform_context = QgsProject.instance().transformContext()
            a = QgsVectorFileWriter.writeAsVectorFormatV3(
                v_layer,
                fname_layer,
                transform_context,
                options
            )
    except BaseException:        # for older QGIS versions
        for v_layer in vector_layer_list:
            fname_layer = fname+'|layername='+v_layer.name()
            QgsVectorFileWriter.writeAsVectorFormat(
                v_layer,
                fname_layer,
                'utf-8',
                v_layer.crs(),
                driverName=geodata_driver_name
            )
