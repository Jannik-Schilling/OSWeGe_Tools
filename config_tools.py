from qgis.PyQt import (
    QtWidgets,
    uic
)


import os
import json



FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__),
    'userinterfaces',
    'config_base.ui')
)

def get_config_from_json(json_file):
    """
    opens a json file and returns the current config as a dictionary
    :param json_file: path to the json file
    :return: config as a dictionary
    """
    # check if the file exists
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"Config file {json_file} does not exist")
    # check if the file is readable
    if not os.access(json_file, os.R_OK):
        raise PermissionError(f"Config file {json_file} is not readable")
    with open(json_file, 'r') as f:
        config = json.load(f)
    return config
    
class oswegeToolsConfigDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, json_file, parent=None):
        super(oswegeToolsConfigDialog, self).__init__(parent)
        self.setupUi(self)
        self.json_file = json_file
        self.config_dict = get_config_from_json(json_file)
        # set the value of the QListWidget
        self.WidgetPflichtfeldGew.clear()
        self.WidgetPflichtfeldGew.addItems(self.config_dict['check_layer_defaults']['pflichtfelder']['gewaesser'])

    def get_dialog_config(self):
        """
        """
        last_change = "07.05.2025"  # Todo
        layer_names = {
            "gewaesser": self.LayerComboBoxGewaesser.currentLayer(),
            "rohleitungen": self.LayerComboBoxRL.currentLayer(),
            "durchlaesse": self.LayerComboBoxDL.currentLayer(),
            "schaechte": self.LayerComboBoxSchaechte.currentLayer(),
            "wehre": self.LayerComboBoxWehre.currentLayer()
        }
        dialog_PflichtfeldGew =  [self.WidgetPflichtfeldGew.item(i).text() for i in range(self.WidgetPflichtfeldGew.count())]
        dialog_PflichtfeldRl =  [self.WidgetPflichtfeldRl.item(i).text() for i in range(self.WidgetPflichtfeldRl.count())]
        dialog_flichtfeldDl =  [self.WidgetPflichtfeldDl.item(i).text() for i in range(self.WidgetPflichtfeldDl.count())]
        dialog_PflichtfeldSchaechte =  [self.WidgetPflichtfeldSchaechte.item(i).text() for i in range(self.WidgetPflichtfeldSchaechte.count())]
        dialog_PflichtfeldWehre =  [self.WidgetPflichtfeldWehre.item(i).text() for i in range(self.WidgetPflichtfeldWehre.count())]
        dialog_primaerschluessel = self.comboBoxPrimrschl.currentText()
        dialog_minimallaenge = self.WidgetLaengeGew.item(0).text() if self.WidgetLaengeGew.count() > 0 else ''
        dialog_dict = {
            "last_change": last_change,
            "layer_names": layer_names,
            "pflichtfelder": {
                "gewaesser": dialog_PflichtfeldGew,
                "rohleitungen": dialog_PflichtfeldRl,
                "durchlaesser": dialog_flichtfeldDl,
                "schaechte": dialog_PflichtfeldSchaechte,
                "wehre": dialog_PflichtfeldWehre
            },
            "primaerschluessel_gew": dialog_primaerschluessel,
            "minimallaminimallaenge_gewenge": dialog_minimallaenge,
            "findGew_tolerance_dist": 0.2  # ToDo
        }
        return dialog_dict

    def save_config(self):
        """
        saves the current config to the self.json_file
        """
        current_config = self.get_dialog_config()
        self.write_to_json(self.json_file, current_config)
        

    def write_to_json(self, json_file, dict_to_write):
        with open(json_file, 'w') as f:
            json.dump(dict_to_write, f, indent=4)


