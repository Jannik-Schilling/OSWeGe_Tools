import os
import json

from qgis.PyQt import (
    QtWidgets,
    uic,
)

from qgis.core import (
    Qgis,
    QgsProject
)

from qgis.PyQt.QtWidgets import QDialog

from .defaults import (
    file_config_for_reset
)

# files for user interfaces
plugin_dir = os.path.dirname(__file__)
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_dir,
    'userinterfaces',
    'config_base.ui')
)
FORM_CLASS_EDIT, _2 = uic.loadUiType(os.path.join(
    plugin_dir,
    'userinterfaces',
    'edit_config_entry_base.ui')
)


def get_config_from_json(json_file):
    '''
    opens a json file and returns the current config as a dictionary
    :param json_file: path to the json file
    :return: config as a dictionary
    '''
    # check if the file exists
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"Config file {json_file} does not exist")
    # check if the file is readable
    if not os.access(json_file, os.R_OK):
        raise PermissionError(f"Config file {json_file} is not readable")
    with open(json_file, 'r') as f:
        config = json.load(f)
    return config


def open_message_box(message):
    '''
    opens a message box with the given message (critical)
    :param message: message to be displayed
    '''
    QtWidgets.QMessageBox.critical(
        None,
        "Warning",
        message
    )


def config_layer_if_in_project(file_config_user, QgsInstance = None):
    """
    gibt ein Dictionary mit layernamen aus der Konfig zurück, wenn diese vorhanden sind
    :param str file_config_user
    :return: dict
    """
    user_config_dict = get_config_from_json(file_config_user)
    dict_layer_defaults = {
        'gewaesser': None,
        'rohrleitungen': None,
        'durchlaesse': None,
        'schaechte':None,
        'wehre': None
    }
    
    filtered_layer_list = [layer for layer in QgsProject.instance().mapLayers().values() if layer.type() == 0]  # nur Vektorlayer
    #print(filtered_layer_list)
    for layer_key in dict_layer_defaults.keys():
        default_layer_name = user_config_dict['layer_names'][layer_key]
        if layer_key in ['gewaesser', 'rohrleitungen', 'durchlaesse']:
            filtered_layer_name_list = [layer.name() for layer in filtered_layer_list if layer.geometryType() == 1]  # nur Linienlayer
        else:
            filtered_layer_name_list = [layer.name() for layer in filtered_layer_list if layer.geometryType() == 0]  # nur Punktlayer
        if default_layer_name in filtered_layer_name_list:
            dict_layer_defaults[layer_key] = default_layer_name
    return dict_layer_defaults


class oswegeToolsConfigEntryEdit(QtWidgets.QDialog, FORM_CLASS_EDIT):
    '''Dialog to edit the entries of the config dialog'''
    def __init__(
        self,
        title_text,
        current_list,
        current_primary_key,
        layer_key,
        parent
    ):
        QDialog.__init__(self, parent)
        self.setParent(parent)
        self.setupUi(self)
        self.setWindowTitle(title_text)
        
        self.layer_key = layer_key
        self.current_primary_key = current_primary_key
        self.current_list = current_list
        
        self.set_up_entrys(current_list)
        self.buttonDelete.clicked.connect(self.delete_entries)
        self.buttonAdd.clicked.connect(self.add_entry)
        self.buttonBox.accepted.connect(self.update_parent)
        self.attributesComboBox.setToolTip("Um ein Attribut aus der Liste zu löschen, setzen Sie den Haken")
        self.textEdit.setToolTip("Geben Sie ein neues Pflichtattribut / -Feld ein")

    def delete_entries(self):
        '''
        deletes the checked entries from self.attributesComboBox 
        and updates self.current_list
        '''
        checked_entries = self.attributesComboBox.checkedItems()
        if self.current_primary_key in checked_entries:
            # remove current primary key from checked entries
            open_message_box(
                f'Der Primärschlüssel ({self.current_primary_key}) kann nicht gelöscht werden.'
            )
            checked_entries = [entr for entr in checked_entries if entr != self.current_primary_key]
        remaining_entries = [entr for entr in self.current_list if not entr in checked_entries]
        self.set_up_entrys(remaining_entries)
        self.current_list = remaining_entries

    def set_up_entrys(self, new_list):
        '''
        sets up the entries in the QListWidget and the textBrowser 
        :param new_list: list of entries to be displayed
        '''
        self.attributesComboBox.clear()
        self.attributesComboBox.addItems(new_list)
        self.textBrowser.clear()
        self.textBrowser.setText(
            'Aktuelle Attributliste: \n\n'
            + '\n'.join(new_list)
        )

    def add_entry(self):
        '''
        adds the entry from the textEdit to the QListWidget and updates self.current_list
        '''
        # check if the entry is empty or already in the list
        new_entry = self.textEdit.toPlainText()
        if len(new_entry) == 0:
            open_message_box(
                'Bitte einen Eintrag eingeben.'
            )
        if new_entry in self.current_list:
            open_message_box(
                f'Der Eintrag "{new_entry}" ist bereits in der Liste.'
            )
        else:
            self.current_list.append(new_entry)
            self.set_up_entrys(self.current_list)
            self.textEdit.clear()

    def update_parent(self):
        '''updates the parent dialog with the new entries'''
        self.parent().update_from_entry_edit(self.layer_key)

    def result(self):
        '''returns the current list of entries'''
        return self.current_list


class oswegeToolsConfigDialog(QtWidgets.QDialog, FORM_CLASS):
    '''Main Dialog to edit the config of the oswegeTools'''
    def __init__(self, json_file, parent=None):
        super(oswegeToolsConfigDialog, self).__init__(parent)
        #print('start_conf')
        self.setupUi(self)
        self.json_file = json_file
        self.edit_dialog_is_open = False
        self.setWindowTitle('OSWeGe Tools - Konfiguration')
        #self.ignoreCaseCheckBox.setToolTip("Setzen Sie den Haken, um bei der Attributprüfung Groß-/Kleinschreibung der Felder zu ignorieren, z.B. \"BA_CD\" und \"ba_cd\"")
        self.ignoreCaseCheckBox.setVisible(False)
        
        # Layerauswahl
        config_dict = get_config_from_json(json_file)
        config_dict_layers = config_dict['layer_names']
        dict_layer_widgets = {
            'gewaesser': self.LayerComboBoxGewaesser,
            'rohrleitungen': self.LayerComboBoxRL,
            'durchlaesse': self.LayerComboBoxDL,
            'schaechte':self.LayerComboBoxSchaechte,
            'wehre': self.LayerComboBoxWehre
        }
        for layer_key, widget_obj in dict_layer_widgets.items():
            if layer_key in ['gewaesser', 'rohrleitungen', 'durchlaesse']:
                widget_obj.setFilters(Qgis.LayerFilter.LineLayer)
            else:
                widget_obj.setFilters(Qgis.LayerFilter.PointLayer)
            widget_obj.setAdditionalItems([''])
            all_layer_items = [widget_obj.itemText(i) for i in range(widget_obj.count())]
            if config_dict_layers[layer_key] in all_layer_items:
                widget_obj.setCurrentText(config_dict_layers[layer_key])
            else:
                widget_obj.setCurrentText('')



        # set the values; depends on json_file
        self.set_up_pruefroutinen_params(json_file)

        # connect the signals
        self.pushButtonGew.clicked.connect(lambda: self.open_edit_dialog('gewaesser'))
        self.pushButtonRl.clicked.connect(lambda: self.open_edit_dialog('rohrleitungen'))
        self.pushButtonDl.clicked.connect(lambda: self.open_edit_dialog('durchlaesse'))
        self.pushButtonSchaechte.clicked.connect(lambda: self.open_edit_dialog('schaechte'))
        self.pushButtonWehre.clicked.connect(lambda: self.open_edit_dialog('wehre'))
        self.dialogSaveCancel.accepted.connect(self.save_config)
        #self.dialogSaveCancel.accepted.connect(self.save_config_test)  # nur zu testzwecken
        self.dialogSaveCancel.accepted.connect(self.close_edit_dialog)
        self.dialogSaveCancel.rejected.connect(self.close_edit_dialog)
        self.restoreButton.clicked.connect(
            lambda: self.set_up_pruefroutinen_params(
                file_config_for_reset
            )
        )
        self.comboBoxPrimrschl.currentTextChanged.connect(
            lambda: self.handle_field_in_all_lists(self.comboBoxPrimrschl.currentText())
        )

    def set_up_pruefroutinen_params(self, json_file):
        '''
        sets up params from self.config_dict
        :param json_file: path to the json file
        '''
        # Die Config-Datei lesen
        config_dict = get_config_from_json(json_file)

        # fg_ae-Parameter
        self.fg_ae_spinbox.setValue(config_dict['max_suchraum_fg_ae_in_m'])

        # Combobox fuer den Primaerschluesseln
        self.comboBoxPrimrschl.clear()
        loadad_primary_key = config_dict['check_layer_defaults']['primaerschluessel_gew']
        self.comboBoxPrimrschl.addItems(config_dict['check_layer_defaults']['pflichtfelder']['gewaesser'])
        # check if the primary key is already in the list if not, add it to the list
        if not loadad_primary_key in config_dict['check_layer_defaults']['pflichtfelder']['gewaesser']:
            self.comboBoxPrimrschl.addItem(loadad_primary_key)
        self.comboBoxPrimrschl.setCurrentText(loadad_primary_key)

        # Pflichtfelder
        self.dict_list_widgets = {
            'gewaesser': self.WidgetPflichtfeldGew,
            'rohrleitungen': self.WidgetPflichtfeldRl,
            'durchlaesse': self.WidgetPflichtfeldDl,
            'schaechte':self.WidgetPflichtfeldSchaechte,
            'wehre': self.WidgetPflichtfeldWehre
        }
        for layer_key, widget_obj in self.dict_list_widgets.items():
            widget_obj.clear()
            text_list = config_dict['check_layer_defaults']['pflichtfelder'][layer_key]
            if not loadad_primary_key in config_dict['check_layer_defaults']['pflichtfelder'][layer_key]:
                text_list.append(loadad_primary_key)
            widget_obj.setText('\n'.join(text_list))
        #self.ignoreCaseCheckBox.setChecked(config_dict["check_layer_defaults"]["feldname_gross_klein_ignorieren"]) #JSON: "feldname_gross_klein_ignorieren": false,

        # Minimallaenge Gewaesser
        self.WidgetLaengeGew.setValue(config_dict['check_layer_defaults']['minimallaenge_gew'])


    def handle_field_in_all_lists(self, entry_i):
        '''
        Checks if the entry is in all list_items and adds it if not
        :param any entry_i
        '''
        if entry_i:
            for layer_key, listwidget_obj in self.dict_list_widgets.items():
                self.add_required_field(entry_i, listwidget_obj)

    def add_required_field(self, entry_i, listwidget_obj):
        '''
        adds an entry (str) to the listwidget_obj if it is not already in the list of entries
        '''
        list_of_fields = listwidget_obj.toPlainText().split('\n')
        if not entry_i in list_of_fields:
            list_of_fields.append(entry_i)
            listwidget_obj.clear()
            new_text = '\n'.join(list_of_fields)
            listwidget_obj.setText(new_text)

    def save_config_test(self):
        '''
        saves the current config to the self.json_file.
        This function exists for debugging purposes
        '''
        current_config = self.get_current_dialog_config()
        print(current_config)

    def open_edit_dialog(self, layer_key):
        """
        Opens a new QDialog to edit the required fields for a layer
        :param str layer_key
        """
        edit_dialog_title = f'Pflichtfelder für {layer_key.capitalize()}-Layer ändern'
        current_list_widget = self.dict_list_widgets[layer_key]
        current_value_list = current_list_widget.toPlainText().split('\n')
        current_primary_key = self.comboBoxPrimrschl.currentText()
        self.editDialog = oswegeToolsConfigEntryEdit(
            edit_dialog_title,
            current_value_list,
            current_primary_key,
            layer_key,
            self
        )
        self.editDialog.show()
        self.edit_dialog_is_open = True
        
    def close_edit_dialog(self):
        """
        Closes the child QDialog when the parent is closed (if child dialog is open)
        """
        if self.edit_dialog_is_open:
            self.editDialog.close()
            self.edit_dialog_is_open = False
            
    def closeEvent(self, event):
        self.close_edit_dialog()

    def update_from_entry_edit(self, layer_key):
        new_entries = self.editDialog.result()
        widget_obj = self.dict_list_widgets[layer_key]
        widget_obj.clear()
        widget_obj.setText('\n'.join(new_entries))
        if layer_key == 'gewaesser':
            self.comboBoxPrimrschl.clear()
            self.comboBoxPrimrschl.addItems(new_entries)
        self.close_edit_dialog()

    def get_current_dialog_config(self):
        '''
        returns the current config as a dictionary
        :return: config as a dictionary
        '''
        last_change = '07.05.2025'  # Todo
        layer_names = {}
        for layer_key, layer_i in zip(
            [
                'gewaesser',
                'rohrleitungen',
                'durchlaesse',
                'schaechte',
                'wehre'
            ],
            [
                 self.LayerComboBoxGewaesser.currentLayer(),
                 self.LayerComboBoxRL.currentLayer(),
                 self.LayerComboBoxDL.currentLayer(),
                 self.LayerComboBoxSchaechte.currentLayer(),
                 self.LayerComboBoxWehre.currentLayer()
            ]
        ):
            layer_names[layer_key] = layer_i.name() if layer_i else ''
        dialog_PflichtfeldGew = self.WidgetPflichtfeldGew.toPlainText().split('\n')
        dialog_PflichtfeldRl = self.WidgetPflichtfeldRl.toPlainText().split('\n')
        dialog_flichtfeldDl = self.WidgetPflichtfeldDl.toPlainText().split('\n')
        dialog_PflichtfeldSchaechte = self.WidgetPflichtfeldSchaechte.toPlainText().split('\n')
        dialog_PflichtfeldWehre = self.WidgetPflichtfeldWehre.toPlainText().split('\n')

        dialog_primaerschluessel = self.comboBoxPrimrschl.currentText()
        #dialog_ignore_case = self.ignoreCaseCheckBox.isChecked()
        dialog_minimallaenge = self.WidgetLaengeGew.value()
        dialog_fg_ae_laenge = int(self.fg_ae_spinbox.value())
        dialog_dict = {
            'last_change': last_change,
            'layer_names': layer_names,
            'max_suchraum_fg_ae_in_m': dialog_fg_ae_laenge,
            'check_layer_defaults': {
                'pflichtfelder': {
                    'gewaesser': dialog_PflichtfeldGew,
                    'rohrleitungen': dialog_PflichtfeldRl,
                    'durchlaesse': dialog_flichtfeldDl,
                    'schaechte': dialog_PflichtfeldSchaechte,
                    'wehre': dialog_PflichtfeldWehre
                },
                'primaerschluessel_gew': dialog_primaerschluessel,
                'feldname_gross_klein_ignorieren': False,  #ToDo: dialog_ignore_case
                'minimallaenge_gew': dialog_minimallaenge,
                'findGew_tolerance_dist': 0.2  # ToDo
            }
        }
        return dialog_dict

    def save_config(self):
        '''
        saves the current config to the self.json_file
        '''
        current_config = self.get_current_dialog_config()
        self.write_to_json(self.json_file, current_config)

    def write_to_json(self, json_file, dict_to_write):
        with open(json_file, 'w') as f:
            json.dump(dict_to_write, f, indent=4)