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

try:
    from qgis.PyQt.QtCore import QMetaType
except BaseException:
    from qgis.PyQt.QtCore import QVariant

from .defaults import (
    dict_report_texts,
    dict_ereign_fehler,
    output_layer_prefixes
)

from .hilfsfunktionen import (
    get_geom_type,
    get_entry_from_dict,
    is_path_in_dict
)


class layerReport:
    def __init__(self, layer_dict):
        """
        Initiiert die Klasse mit self.report_dict = {
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
        :param dict layer_dict: {'layer_name': layer, 'layer_name2': layer2 ...}
        """
        self.report_dict = {}
        for key, value in layer_dict.items():
            layer = value['layer']
            self.report_dict[key] = {
                'name': layer.name(),
                'attribute': {},
                'geometrien': {}
            }
        # ein Dictionary fuer die Stationierung der Objekte
        self.stats_dict = dict()

    def add_rldl(self):
        self.report_dict['layer_rldl'] = {'geometrien':{}}

    def add_attribute_entry(self, layer_key, error_name, entry, accept_empty = False):
        """
        Traegt einen neuen Attribut-Fehler ein
        :param str layer_key
        :param str error_name
        :param list or dataframe entry
        :param bool accept_empty: Wenn True, werden auch leere Eintraege aktzeptiert
        """
        if accept_empty:
            self.report_dict[layer_key]['attribute'][error_name] = entry
        else:
            if len(entry) > 0:
                self.report_dict[layer_key]['attribute'][error_name] = entry

    def add_geom_entry(self, layer_key, error_name, entry, accept_empty = False):
        """
        Traegt einen neuen Attribut-Fehler ein
        :param str layer_key
        :param str error_name
        :param list or dataframe entry
        :param bool accept_empty: Wenn True, werden auch leere Eintraege aktzeptiert
        """
        if accept_empty:
            self.report_dict[layer_key]['geometrien'][error_name] = entry
        else:
            if len(entry) > 0:
                self.report_dict[layer_key]['geometrien'][error_name] = entry

    def prepare_report_dict(self, feedback):
        """
        Bereitet self.report_dict fuer die Ausgabe vor
        :param QgsProcessingFeedback feedback
        """
        step_temp = 100/len(self.report_dict)
        for i, layer_key in enumerate(['rohrleitungen', 'durchlaesse', 'layer_rldl', 'schaechte', 'wehre']):
            if feedback.isCanceled():
                break
            feedback.setProgress(int((i+1) * step_temp))
            if layer_key not in self.report_dict.keys():
                continue
            else:
                for error_name in ['geom_ereign_auf_gew','geom_schacht_auf_rldl']:
                    if error_name in self.report_dict[layer_key]['geometrien'].keys():
                        df = self.report_dict[layer_key]['geometrien'][error_name]
                        # Unbenoetige Spalten loeschen
                        df2 = delete_column_if_exists(df, ['vtx_stat', 'start', 'stop'])
                        # # Fehlercodes mit Text ersetzen
                        df3 = replace_values_with_strings(df2, dict_ereign_fehler)
                        self.report_dict[layer_key]['geometrien'][error_name] = df3
        resulting_dict = self.report_dict.copy()
        for layer_key in resulting_dict.keys():
            for rep_section in ['attribute', 'geometrien']:
                if not rep_section in resulting_dict[layer_key].keys():
                    pass
                else:
                    resulting_dict[layer_key][rep_section] = {
                        sub_section: elem for sub_section, elem in resulting_dict[layer_key][rep_section].items() if len(elem) != 0
                    }
                    if len(resulting_dict[layer_key][rep_section]) == 0:
                        del resulting_dict[layer_key][rep_section]
        replace_report_dict_keys(resulting_dict, dict_report_texts)
        return resulting_dict
    
    def get_report_dict(self):
        """
        Gibt das komplette Report-Dict zurueck
        :return: dict
        """
        return self.report_dict
        
    def get_report_entry(self, key_list):
        """
        Gibt das Objekt aus dem report dict zurück, wenn der Pfad existiert
        :param list key_list
        """
        if not key_list:
            return None
        else:
            if is_path_in_dict(self.report_dict, key_list):
                return get_entry_from_dict(self.report_dict, key_list)
            else:
                return None



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

def join_list_items(x):
    """
    Fuegt alles in x zu einem String zusammen
    """
    if isinstance(x, list):
        return ', '.join(map(str, x))
    else:
        return str(x) 
    
    
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
        try:
        # QgsField is deprecated since QGIS 3.38 -> QMetaType
            vector_layer.addAttribute(QgsField(column_name, QMetaType.Type.QString,))
        except:  # fuer aeltere QGIS Versionen (vermutl. vor 3.8)
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
    except BaseException:  # for older QGIS versions
        for v_layer in vector_layer_list:
            fname_layer = fname+'|layername='+v_layer.name()
            QgsVectorFileWriter.writeAsVectorFormat(
                v_layer,
                fname_layer,
                'utf-8',
                v_layer.crs(),
                driverName=geodata_driver_name
            )
