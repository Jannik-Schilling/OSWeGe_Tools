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
ereign_gew_id_feld = ['gu_cd', 'ba_cd']

# zu pruefenden Mindestlaenge fuer Gewaesser
minimallaenge_gew = 0.5

# Suchraum fuer die Stationierungsfunktion
findGew_tolerance_dist = 0.2

# Suchraum fuer die Checks
distanz_suchen = 0

# Fehldermeldungen
pluginPath = os.path.dirname(__file__)
df_fehlermeldungen = pd.read_csv(
    os.path.join(
        pluginPath,
        "tables/Meldungen.csv"
    ),
    encoding = 'windows-1252'
)

