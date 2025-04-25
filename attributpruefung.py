def get_missing_fields(layer, key, pflichtfelder):
                """
                Diese Funktion prueft, ob alle Pflichtfelder vorhanden sind
                :param QgsVectorLayer layer
                :param str key
                :param dict pflichtfelder
                :return: list missing_fields
                """
                pflichtfelder_i = pflichtfelder[key]
                layer_i_felder = layer.fields().names()
                missing_fields = [
                    feld for feld in pflichtfelder_i if not feld in layer_i_felder
                ]
                return missing_fields

def missing_fields_check(key, layer, report_dict, pflichtfelder, params):
    """
    Diese Funktion fuegt die fehlenden Felder in das report_dict ein
    :param str key
    :param QgsVectorLayer layer
    :param dict report_dict
    :param dict pflichtfelder
    :param dict params
    """ 
    missing_fields = get_missing_fields(layer, key, pflichtfelder)
    ereign_gew_id_field = params['ereign_gew_id_field']
    report_dict[key]['attribute']['missing_fields'] = missing_fields
    if key == 'gewaesser' and ereign_gew_id_field in missing_fields:
        params['gew_primary_key_missing'] = True