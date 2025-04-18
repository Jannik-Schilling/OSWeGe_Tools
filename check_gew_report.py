# Dieses Pythonskript Enthaelt die Funktionen fuer den Report
import pandas as pd

from qgis.core import (
    NULL,
    QgsField,
    QgsFeature,
    QgsProcessingException,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from qgis.PyQt.QtCore import QVariant

from .defaults import (
    dict_report_texts,
    dict_ereign_fehler,
    output_layer_prefixes
)

from .hilfsfunktionen import get_geom_type


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
    return report_dict


# Aufraeumfunktionen
def replace_lst_ids(series_i, dict_repl):
    """
    Ersetzt alle einzelnen id-Nummern anhand von dict_repl
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


def listcol_to_str (df, column_name):
    """
    Fuegt in df in einer Spalte die Listen zu Strings zusammen
    :param pd.DataFrame df
    :param str column_name
    :return: pd.DataFrame
    """
    def join_list_items(x):
        if isinstance(x, list):
            return ', '.join(map(str, x))
        else:
            return str(x) 
    
    df[column_name] = df[column_name].apply(join_list_items)
    return df
    
    
def delete_column_if_exists(df, column_names):
    """
    Loescht Spalten, falls vorhanden
    :param pd.DataFrame df
    :param list column_names 
    :return: pd.DataFramee
    """
    columns_to_delete = [col for col in column_names if col in df.columns]
    if columns_to_delete:
        df = df.drop(columns=columns_to_delete)
    return df

def delete_rows_with_zero(df, column_names):
    """
    Loescht Zeilen, wenn die Werte in den Spalten column_names 0 sind
    :param pd.DataFrame df
    :param list column_names 
    :return: pd.DataFrame
    """
    mask = (df[column_names] == 0).all(axis=1)
    df_filtered = df[~mask]
    df_filtered.reset_index(drop=True, inplace=True)
    return df_filtered

def replace_values_with_strings(df, replace_dict):
    """
    Ersetzt die Werte anhand des dictionarys
    :param pd.DataFrame df
    :param dict replace_dict
    :return: pd.DataFrame
    """
    for column, replace_dict_i in replace_dict.items():
        if column in df.columns:
            df[column] = df[column].replace(replace_dict_i)
            if column == 'Lage':
                df[column] = [
                    'Abweichung: Stp. '+', '.join(val[1]) if type(val)==list else val for val in df[column]
                ]  # Ausnahme für Linien
    return df
    
def replace_report_dict_keys(report_dict, replacement_dict):
    """
    Ersetzt die keys auf der dritten Ebene des report dicts mit neuen keys ("in place")
    :param dict replace_dict
    :param dict report_dict
    """
    for layer_key in report_dict.keys():
        if layer_key == 'Hinweis':
            continue
        for error_type in report_dict[layer_key].keys():
            if error_type == 'name':
                pass
            else:
                try:
                    occuring_error_names = list(report_dict[layer_key][error_type].keys())
                except Exception:
                    raise QgsProcessingException(
                        'Unknown error type ' 
                        + str(report_dict[layer_key][error_type])
                        + '. Please contact the developer / maintainer of the plugin'
                    )
                for error_name in occuring_error_names:
                    if error_name in replacement_dict:
                        report_dict[layer_key][error_type][replacement_dict[error_name]] = report_dict[layer_key][error_type].pop(error_name)
    
    
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
                if rep_section == 'geometrien':
                    if key == 'gewaesser':
                        for error_name in ['wasserscheiden', 'senken']:
                            if error_name in report_dict[key][rep_section].keys():
                                df = report_dict[key][rep_section][error_name]
                                # Listen durch Strings ersetzen
                                df2 = listcol_to_str (df, 'feature_id')
                                report_dict[key][rep_section][error_name] = df2

                    if key in ['rohrleitungen', 'durchlaesse', 'layer_rldl']:
                        if 'geom_ereign_auf_gew' in report_dict[key][rep_section].keys():
                            df = report_dict[key][rep_section]['geom_ereign_auf_gew']
                            # Unbenoetige Spalten loeschen
                            df2 = delete_column_if_exists(df, ['vtx_stat', 'start', 'stop'])
                            # Unbenoetige Zeilen loeschen
                            df3 = delete_rows_with_zero(df2, ['Anzahl','Lage','Richtung'])
                            # Fehlercodes mit Text ersetzen
                            df4 = replace_values_with_strings(df3, dict_ereign_fehler)
                            report_dict[key][rep_section]['geom_ereign_auf_gew'] = df4

                    if key in ['schaechte', 'wehre']:
                        if 'geom_ereign_auf_gew' in report_dict[key][rep_section].keys():
                            df = report_dict[key][rep_section]['geom_ereign_auf_gew']
                            # Unbenoetige Zeilen loeschen
                            df2 = delete_rows_with_zero(df, ['Lage'])
                            # Fehlercodes mit Text ersetzen
                            df3 = replace_values_with_strings(df2, dict_ereign_fehler)
                            report_dict[key][rep_section]['geom_ereign_auf_gew'] = df3
                        if 'geom_schacht_auf_rldl' in report_dict[key][rep_section].keys():
                            df = report_dict[key][rep_section]['geom_schacht_auf_rldl']
                            # Unbenoetige Zeilen loeschen
                            df2 = delete_rows_with_zero(df, ['Lage_rldl'])
                            # Fehlercodes mit Text ersetzen
                            df3 = replace_values_with_strings(df2, dict_ereign_fehler)
                            report_dict[key][rep_section]['geom_schacht_auf_rldl'] = df3
                            
                report_dict[key][rep_section] = {
                    sub_section: elem for sub_section, elem in report_dict[key][rep_section].items() if len(elem) != 0
                }
                if len(report_dict[key][rep_section]) == 0:
                    del report_dict[key][rep_section]
    # Fehlernamen ersetzen
    replace_report_dict_keys(report_dict, dict_report_texts)

# Layererstellung
def create_feature_from_attrlist(
    attrlist,
    geom_type,
    f_geometry=NULL
):
    """
    creates a QgsFeature from with attributes in a list
    :param list attrlist
    :param str geom_type
    :param QgsGeometry geometry
    :return: QgsFeature
    """
    f = QgsFeature()
    if geom_type != 'NoGeometry':
        try:
            f.setGeometry(f_geometry)
        except Exception:
            raise QgsProcessingException(
                'Could not set geometry of type \"' 
                + str(f_geometry)
                + '\" in function create_feature_from_attrlist. '
                + 'Please contact the developer / maintainer of the plugin'
            )
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
        return create_feature_from_attrlist(
            attrlist,
            geom_type,
            f_geometry
        )
    else:
        attrlist = df_i.tolist()
        return create_feature_from_attrlist(
            attrlist,
            geom_type
        )


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
    else:  
        # No Geometry
        layer_fields = data_df.keys()
    
    # leeren Layer generieren
    vector_layer = QgsVectorLayer(
        geom_type,
        layer_name,
        'memory'
    )
    vector_layer.startEditing()
    for  column_name in layer_fields:
        # QgsField is deprecated since QGIS 3.38 -> QMetaType
        vector_layer.addAttribute(QgsField(column_name, QVariant.String))
    vector_layer.updateFields()

    # Objekte 
    feature_list = data_df.apply(
        lambda x: create_feature_from_row(
            x,
            geom_type
        ),
        axis=1  # auf jede Zeile anwenden
    )
    vector_layer.addFeatures(feature_list)
    vector_layer.updateExtents()
    vector_layer.commitChanges()
    return vector_layer


def create_layers_from_report_dict(report_dict, crs_out, feedback):
    '''
    Generiert für alle Geometrie-Einträge einen Layer
    :param dict report_dict
    :param str crs_out
    :param QgsProcessingFeedback feedback 
    :return: list vector_layer_list
    :return: list list_messages
    '''
    vector_layer_list = []
    list_messages = []
    for layer_key in report_dict.keys():
        if layer_key == 'Hinweis':
            continue
        for rep_section in ['attribute','geometrien']:
            if not rep_section in report_dict[layer_key].keys():
                pass
            else:
                for error_name, error_df in report_dict[layer_key][rep_section].items():
                    layer_name = output_layer_prefixes[layer_key]+': '+error_name
                    feedback.setProgressText(layer_name)
                    if error_name in ['missing_fields', 'fehlende Felder']:
                        list_messages.append(
                            'Fehlende Felder im '
                            + layer_key.capitalize()
                            +'-Layer: '
                            + ', '.join(error_df)
                        )
                    else:
                        if isinstance(error_df, list):
                            error_df = pd.DataFrame({'feature_id':error_df})
                        if not isinstance(error_df, pd.DataFrame):
                            pass  # sollte eigentlich nicht vorkommen
                        else:
                            for col in error_df.keys():
                                if col != 'geometry':
                                    error_df[col] = [str(f) for f in error_df[col]]
                            if (rep_section == 'attribute') or (not 'geometry' in error_df.keys()):
                                geom_type = 'NoGeometry'
                            else:
                                geom_type = get_geom_type(error_name, layer_key)
                            layer_neu = create_layer_from_df( 
                                error_df,
                                layer_name,
                                geom_type,
                                crs_out,
                                feedback
                            )
                            vector_layer_list = vector_layer_list+[layer_neu]
    return vector_layer_list, list_messages
    
    
    
def save_layer_to_file(
    vector_layer_list,
    fname
):
    """
    Schreibt alle Layer in der list in ein Geopackage
    :param list vector_layer_list: Layerliste
    :param str fname: Speicherpfad
    """
    # "Treiber"
    geodata_driver_name = 'GPKG'

    # Alle Layer aus der Liste in Datei schreiben
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
            QgsVectorFileWriter.writeAsVectorFormatV3(
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
