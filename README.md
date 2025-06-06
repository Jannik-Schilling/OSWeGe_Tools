# OSWeGe_Tools
Eine QGIS-Werkzeugsammlung für die Gewässerdatenverwaltung von Wasser- und Bodenverbänden / A collection of QGIS tools for the management of river geodata of German water and soil associations

## Installation

### Variante 1 Aus dem QGIS-Plugin-Repository
Im QGIS-Plugin Manager (*Erweiterungen > Erweiterungen verwalten und installieren...*):
- Unter "Alle" -> suche nach "OSWeGe"
- das Plugin auswählen und auf "installieren" klicken

### Variante 2 Plugin als .zip-Datei
1. herunterladen
   
![grafik](https://github.com/Jannik-Schilling/OSWeGe_Tools/assets/54308008/b736d8f9-0901-4297-af91-d3e1cdd419be)


2. Im QGIS-Plugin Manager (*Erweiterungen > Erweiterungen verwalten und installieren...*):
  - sollte bereits eine ältere Version des Plugins installiert sein, muss diese zunächst gelöscht werden.
  - Tab "Aus ZIP installieren"
  - ZIP-Datei auswählen und auf "Erweiterung installieren" klicken

## Verfügbare Werkzeuge
### Prüfroutine Gewässerlinien (Verarbeitungswerkzeug):   
für eine Auswahl an Layern wird geprüft
   - Korrekt vergebene Attribute, eindeutige Schlüssel (Primary Keys)
   - leere Geometrien
   - Duplikate
   - Überschneidungen
   - Lage von Rohrleitungen / Durchlässen / Schächten / Wehren auf Gewässern, sowie Lage von Schächten auf Rohrleitungen oder offenen Gewässern
   - Wasserscheiden und Senken
     
![grafik](https://github.com/user-attachments/assets/b02515e3-ce65-4385-bc8e-62007124517f)

   Die Ergebnisse werden als Separate Layer in einer Geopackage-Datei gespeichert
![grafik](https://github.com/user-attachments/assets/06891192-8364-4fd8-8918-a92cd533b8d4)
### fg_ae-Abschnitte erstellen (Verarbeitungswerkzeug)
Zwischen den Gewässern 2. Ordnung und den Gewässern 1. Ordnung werden die benötigten Einleitungs- und Ausleitungsabschnitte erstellt. Die Abschnitte können nur bei korrekter Linienrichtung der Verbandsgewässer erstellt werden (entgegen der Fließrichtung / 1. Stützpunkt an der Mündung)
![before](https://github.com/user-attachments/assets/ead523da-f77b-448a-b33d-edbb94beda20)


### Anzeige der Stationierung eines Gewässers (in der Werkeugleiste "Plugins")
  ![abfrage_stationierung](https://github.com/user-attachments/assets/f4a8d121-707b-46d7-bd82-077841d0af92)

## Förderung
Dieses Plugin wurde/wird entwickelt im Rahmen des [Projekts OSWeGe](https://oswege.auf.uni-rostock.de/), (gefördert durch das BMUV, Förderkennzeichen 67DAS263)

