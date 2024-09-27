# dieses script Enthaelt die Funktionen fuer den Report

def create_report_dict(params, is_test_version=False):
    """
    Erstellt das Dictionary, dass alle Informationen fuer den Bericht enthaelt
    Aufbau:     
    report_dict = {
        'gewaesser': {
            'name': 'so heisst die Datei",
            'attribute': {
                'missing_fields': [],
                'primary_key_empty': [id1, id2],
                'primary_key_duplicat': [[id3, id4],[id5, id6, id7]]
            },
            'geometrien': {
                fehler1: [],
                fehler2: []
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
                fehler1: [],
                fehler2: []
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
        if layer:
            # Anzahl Objekte fuer das Feedback
            ft_count = layer.featureCount() if layer.featureCount() else 0
            layer_steps = 100.0/ft_count if ft_count != 0 else 0
            params['layer_dict'][key].update({
                'count': ft_count,
                'steps': layer_steps
            })
            report_dict[key] = {'name': layer.name()}
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