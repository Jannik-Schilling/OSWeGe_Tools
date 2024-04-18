import pandas as pd

from .defaults import df_fehlermeldungen

# Funktionen fuer Fehlermeldungen
def fehlermeldungen_generieren(f_dict):
    """
    baut eine Fehlermeldung zusammen
    :param dict f_dict
    """
    if f_dict['Typ'] == 'allgemein':
        if f_dict['Report'] == 0: 
            f_obj_str = ''
        else:
            f_obj_str = fehlermeldung_allgemein(f_dict['Report'])
    if f_dict['Typ'] == 'Attribut':
        f_obj_str = fehlermeldung_objekt(
            f_dict['Objekte'],
            f_dict['Report'],
            f_dict['Spalte']
        )
    if f_dict['Typ'] == 'Geometrie':
        f_obj_str = fehlermeldung_objekt(
            f_dict['Objekte'],
            f_dict['Report']
        )
    if f_obj_str != '':
        f_obj_str = f_obj_str+'\n\n'
    return f_obj_str

def fehlermeldung_allgemein(fehlercode):
    """
    allgemeine fehlermeldung aus der Tabelle
    :param oswDataFeedback fehlercode
    """
    meldung = df_fehlermeldungen.loc[
        df_fehlermeldungen['Code']==fehlercode,'Meldung'
    ].values[0]
    return meldung

def fehlermeldung_objekt(
    obj,
    fehlercode,
    spaltenname = None
):
    """
    fehlermeldung fuer Objektliste
    :param list obj
    :param oswDataFeedback fehlercode
    :param str spaltenname
    """
    if len (obj) == 0:
        meldung = ''
    else:
        if spaltenname is None:
            meldung = ''
        else:
            meldung = (
                'Spalte \"'
                + spaltenname
                + '\": '
            )
        meldung = (
            meldung 
            + fehlermeldung_allgemein(fehlercode)
            + '; Objekt-IDs:\n'
            + (', ').join([str(x) for x in obj])
        )
    return meldung
