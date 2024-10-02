# dieses script Enthaelt die Funktionen fuer den Report
from datetime import datetime
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


def clean_report_dict(report_dict):
    """
    Loescht leere Listen und Dicts im report_dict
    :param dict report_dict
    """
    for key in report_dict.keys():
        if key == 'Hinweis':
            continue
        #if not key == 'layer_rldl':
        for rep_section in ['attribute','geometrien']:
            del_list = []
            for rep_sub_section, lst in report_dict[key][rep_section].items():
                if len(lst) == 0:
                    del_list.append(rep_sub_section)
            for rep_sub_section in del_list:
                del report_dict[key][rep_section][rep_sub_section]
        for rep_section in ['attribute','geometrien']:
            if len(report_dict[key][rep_section]) == 0:
                del report_dict[key][rep_section]



# Funktionen fuer die Textausgabe
def write_report_text(report_dict, txt_file):
    """
    Gerade nicht benutzt! Schreib das report_dict als Text; ist aber noch nicht fertig
    :param dict report_dict
    :param str txt_file
    """
    with open(txt_file, 'w') as f:
        f.write(
            'Ergebnis des Datentests\nDatum: '
            + datetime.today().strftime('%d.%m.%Y')
            + '\n \n'
        )
        for key in report_dict.keys():
            if key == 'Hinweis':
                continue
            if not key == 'layer_rldl':
                #Ueberschrift
                f.write(
                    key.capitalize()
                    + '\n'
                    + '-'*len(key)
                    + '\n'
                )
                f.write(
                    'Layer: '
                    + report_dict[key]['name']
                    + '\n'
                )
                if len(report_dict[key]['attribute']) > 0 or all([len(v)==0 for v in report_dict[key]['attribute'].values()]):
                    f.write('Attribute:\n')
                    for k, v in report_dict[key]['attribute'].items():
                        text_line = write_text_lines(k, v)
                        f.write(text_line)
                else:
                    f.write('Attribute: kein Fehler\n')
                if len(report_dict[key]['geometrien']) > 0 or all([len(v)==0 for v in report_dict[key]['geometrien'].values()]):
                    f.write('Geometrien:\n')
                    for k, v in report_dict[key]['geometrien'].items():
                        text_line = write_text_lines(k, v)
                        f.write(text_line)
                else:
                    f.write('Geometrien: kein Fehler\n')
                f.write('\n\n')

def write_text_lines(k, v):
    """
    :param str k
    :param list/dict v
    """
    if len(v) != 0:
        if k == 'geom_ereign_auf_gew':
            text_line = ' - ' + k + str(v) + '\n'
        elif k == 'geom_schacht_auf_rldl':
            text_line = ' - ' + k + str(v) + '\n'
        else:
            text1 = dict_report_texts[k]
            text_line = ' - ' + text1 + ': ' + ', '.join([str(i) for i in v]) + '\n'
    else:
        text_line = ''
    return text_line



# Funktionen fuer die Layerausgabe
def write_report_layer():
    pass