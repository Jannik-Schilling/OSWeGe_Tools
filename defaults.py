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

# Felder im Gewaesserlayer
feld_gew_name = 'ba_cd'
feld_gew_laenge = 'laenge'
feld_gew_stat_von = 'ba_st_von'
feld_gew_stat_bis = 'ba_st_bis'


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

class oswDataFeedback:
    COL_MISSING = 'COL_MISSING'
    COL_ID_MISSING = 'COL_ID_MISSING'
    VAL_DUPLICAT = 'VAL_DUPLICAT'
    VAL_MISSING = 'VAL_MISSING'
    VAL_ERROR = 'VAL_ERROR'
    GEOM_EMPTY = 'GEOM_EMPTY'
    GEOM_MULTI = 'GEOM_MULTI'
    GEOM_SELFINTERSECT = 'GEOM_SELFINTERSECT'
    GEOM_INTERSECT = 'GEOM_INTERSECT'
    GEOM_DUPLICAT = 'GEOM_DUPLICAT'
    GEOM_TOOSHORT = 'GEOM_TOOSHORT'
    GEOM_SENKE = 'GEOM_SENKE'
    GEOM_WASSERSCHEIDE = 'GEOM_WASSERSCHEIDE'
    GEOM_NOT_ON_GEWLINE = 'GEOM_NOT_ON_GEWLINE'

