def get_missing_fields(layer_key, layer, pflichtfelder):
    """
    Diese Funktion prueft, ob alle Pflichtfelder vorhanden sind
    :param str layer_key
    :param QgsVectorLayer layer
    :param dict pflichtfelder
    :return: list missing_fields
    """
    pflichtfelder_i = pflichtfelder[layer_key]
    layer_i_felder = layer.fields().names()
    missing_fields = [
        feld for feld in pflichtfelder_i if not feld in layer_i_felder
    ]
    return missing_fields

def check_missing_fields(layer_key, layer, report_dict, report_object ,pflichtfelder, params_processing):
    """
    Diese Funktion fuegt die fehlenden Felder in das report_dict ein
    :param str layer_key
    :param QgsVectorLayer layer
    :param dict report_dict
    :param layerReport report_object
    :param dict pflichtfelder
    :param dict params_processing
    """ 
    missing_fields = get_missing_fields(layer_key, layer, pflichtfelder)
    ereign_gew_id_field = params_processing['ereign_gew_id_field']
    report_dict[layer_key]['attribute']['missing_fields'] = missing_fields
    report_object.add_attribute_entry(
        layer_key,
        'missing_fields',
        missing_fields,
        accept_empty = False
    )
    if layer_key == 'gewaesser' and ereign_gew_id_field in missing_fields:
        params_processing['gew_primary_key_missing'] = True

def check_layer_attributes(
    layer_key,
    layer,
    report_dict,
    params_processing
):
    missing_fields = report_dict[layer_key]['attribute']['missing_fields']
    ereign_gew_id_field = params_processing['ereign_gew_id_field']
    feedback = params_processing['feedback']
    if ereign_gew_id_field in missing_fields:
        prim_text = 'Primärschlüssel' if layer_key == 'gewaesser' else 'Fremdschlüssel'
        feedback.pushWarning(
            'Feld \"' + ereign_gew_id_field + '\" ('
            + prim_text +' des Gewässers) fehlt. '
            + 'Der Attributtest für dieses Feld wird übersprungen'
        )
    else:
        feedback.setProgressText('-- Attribute')
        check_primary_and_foreign_key(
            layer_key,
            layer,
            ereign_gew_id_field,
            report_dict,
            params_processing,
            feedback
        )

def check_primary_and_foreign_key(
    layer_key,
    layer,
    ereign_gew_id_field,
    report_dict,
    params_processing,
    feedback
):
    """
    Pruef korrekt primary keys bei Gewaessern und foreign keys bei Ereignissen
    :param str layer_key
    :param QgsVectorLayer layer
    :param str ereign_gew_id_field
    :param dict report dict
    :param dict params_processing
    :param QgsProcessingFeedback feedback
    """
    layer_steps = params_processing['layer_dict'][layer_key]['steps']
    if layer_key == 'gewaesser':
        list_primary_key_empty = []
        prim_key_dict = {}
        for i, feature in enumerate(layer.getFeatures()):
            feedback.setProgress(int((i+1) * layer_steps))
            if feedback.isCanceled():
                break
            ft_key = feature.attribute(ereign_gew_id_field)
            if ft_key in params_processing['emptystrdef']:
                # fehlender Primaerschluessel
                list_primary_key_empty.append(feature.id())
            else:
                # mehrfache Primaerschluessel ? -> Liste an eindeutigen keys
                if ft_key in prim_key_dict.keys():
                    prim_key_dict[ft_key].append(feature.id())
                else:
                    prim_key_dict[ft_key] = [feature.id()]
        list_primary_key_duplicat = [
            lst for lst in prim_key_dict.values() if len(lst) > 1
        ]
        if len(list_primary_key_empty) > 0:
            report_dict[layer_key]['attribute']['primary_key_empty'] = list_primary_key_empty
        if len(list_primary_key_duplicat) > 0:
            report_dict[layer_key]['attribute']['primary_key_duplicat'] = list_primary_key_duplicat

    else:  # Attributtest für Ereignisse
        list_gew_key_empty = []
        list_gew_key_invalid = []
        layer_gew = params_processing['layer_dict']['gewaesser']['layer']
        if params_processing['gew_primary_key_missing']:
            feedback.pushWarning(
                'Die Zuordnung der Ereignisse über den Gewässernamen kann '
                + 'nicht geprüft werden, weil das Feld \"'
                + ereign_gew_id_field
                + '\" im Gewässerlayer fehlt.'
            )
        else:
            list_gew_keys = [
                gew_ft.attribute(ereign_gew_id_field) for gew_ft in layer_gew.getFeatures()
            ]
            for i, feature in enumerate(layer.getFeatures()):
                feedback.setProgress(int((i+1) * layer_steps))
                if feedback.isCanceled():
                    break
                ft_key = feature.attribute(ereign_gew_id_field)
                if ft_key in params_processing['emptystrdef']:
                    # fehlender Gewaesserschluessel
                    list_gew_key_empty.append(feature.id())
                else:
                    if not ft_key in list_gew_keys:
                        # Der angegebene Gewaesserschluessel(=Gewaessername)
                        # ist nicht im Gewaesserlayer vergeben
                        list_gew_key_invalid.append(feature.id())
            if len(list_gew_key_empty) > 0:
                report_dict[layer_key]['attribute']['gew_key_empty'] = list_gew_key_empty
            if len(list_gew_key_invalid) > 0:
                report_dict[layer_key]['attribute']['gew_key_invalid'] = list_gew_key_invalid