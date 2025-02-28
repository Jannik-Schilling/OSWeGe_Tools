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
    'Richtung':{
        0: 'korrekt',
        1: 'verkehrt herum',
    },
    'Lage_rldl': {
        0: 'korrekt',
        1: 'Schacht auf offenem Gewaesser',
        2: 'Schacht auf Rohrleitung (RL) / Durchlass (DL), aber RL / DL verschoben',
        3: 'Schacht weder auf Gewaesser noch auf Rohrleitung / Durchlass'
    }
}

# Fehlertexte
dict_report_texts = {
    'missing_fields': 'fehlende Felder',
    'primary_key_empty': 'fehlender Gewässername (Primärschlüssel)',
    'primary_key_duplicat': 'doppelter Gewässername (ungültig als Primaerschlüssel)',
    'gew_key_empty': 'fehlender Gewässername',
    'gew_key_invalid': 'ungültiger Gewässername (im Gewässerlayer nicht vergeben)',
    'geom_crossings': 'sich kreuzende Linien',
    'geom_ereign_auf_gew': 'Lage auf Gewässerlinie',
    'geom_duplicate': 'identische Geometrien (Duplikate)',
    'geom_is_multi': 'Multigeometrie',
    'geom_is_empty': 'leere Geometrie',
    'geom_overlap': 'sich überlappende Linienereignisse',
    'geom_selfintersect': 'Selbstüberschneidung',
    'geom_schacht_auf_rldl': 'Lage auf Rohrleitung oder Durchlass',
    'wasserscheiden': 'Alle Linien führen von einander weg (\"Wasserscheide\" ohne Zufluss)',
    'senken': 'Alle Linien führen auf einander zu (\"Senke\" ohne Abfluss)'
}

# Output Geometrien nach Layern
default_typical_geoms = {
    'schaechte': 'Point',
    'wehre': 'Point',
    'gewaesser': 'LineString',
    'rohrleitungen' : 'LineString',
    'durchlaesse' : 'LineString',
    'layer_rldl': 'LineString',
}

# Output Geometrien nach Fehlern
default_report_geoms = {
    'missing_fields': 'NoGeometry',
    'primary_key_empty': 'NoGeometry',
    'primary_key_duplicat': 'NoGeometry',
    'gew_key_empty': 'NoGeometry',
    'gew_key_invalid': 'NoGeometry',
    'geom_crossings': 'Point',
    'geom_ereign_auf_gew': default_typical_geoms,
    'geom_duplicate': default_typical_geoms,
    'geom_is_multi': 'NoGeometry',
    'geom_is_empty': 'NoGeometry',
    'geom_overlap': 'LineString',
    'geom_sefintersect': default_typical_geoms,
    'geom_schacht_auf_rldl': 'Point',
    'wasserscheiden': 'Point',
    'senken': 'Point',
}

output_layer_prefixes = {
    'schaechte': 'Schächte',
    'wehre': 'Wehre',
    'gewaesser': 'Gewässer',
    'rohrleitungen' : 'Rohrleitungen',
    'durchlaesse' : 'Durchlässe',
    'layer_rldl': 'Rohrleitungen + Durchlässe',
}
