import os
import pandas as pd

class oswScriptType:
    """Klasse fuer die Scripttypen"""
    PROCESSING='PROCESSING'
    BUTTON='BUTTON'

# Konventionen / Festlegungen in diesem Skript
feld_typen = {
    'Integer64': 'int',
    'String': 'str',
    'Real' : 'float'
}

# Pflichtfelder: der erste ist Primaerschluessel bei gewässern
pflichtfelder = {
    'gewaesser': ['ba_cd', 'gu_cd'],
    'rohrleitungen': ['obj_nr_gu', 'gu_cd', 'profil'],
    'durchlaesse': ['obj_nr_gu', 'gu_cd', 'profil'],
    'wehre':['obj_nr_gu', 'name', 'gu_cd', 'wehr'],
    'schaechte':['obj_nr_gu', 'name', 'gu_cd', 'scha'],
}
# Schluessel zur Identifikation des Gewaessers bei Ereignissen
list_ereign_gew_id_fields = ['gu_cd', 'ba_cd']

# zu pruefenden Mindestlaenge fuer Gewaesser
minimallaenge_gew = 0.5

# Suchraum fuer die Stationierungsfunktion
findGew_tolerance_dist = 0.2

# Suchraum fuer die Checks
distanz_suchen = 0

# Fehler beim Vergleich von Ereignisssen auf Gewässer
dict_ereign_fehler = {
    'Anzahl': {
        0: 'korrekt',
        1: 'zu viele Stützpunkte',
        2: 'zu wenige Stützpunkte'
    },
    'Lage': {
        0: 'korrekt',
        1: 'Abweichung',
    },
    'Lage_rldl': {
        0: 'korrekt',
        1: 'Schacht auf offenem Gewaesser',
        2: 'Rohrleitung oder Durchlass verschoben',
        3: 'Schacht weder auf Gewaesser noch auf RL/DL'
    }
}