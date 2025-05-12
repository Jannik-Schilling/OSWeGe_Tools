import os
import json

from qgis.PyQt import (
    QtWidgets,
    uic,
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


class oswegeToolsConfigEntryEdit(QtWidgets.QDialog, FORM_CLASS_EDIT):
    '''	Dialog to edit the entries of the config dialog'''
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
    '''Dialog to edit the config of the oswegeTools'''
    def __init__(self, json_file, parent=None):
        super(oswegeToolsConfigDialog, self).__init__(parent)
        self.setupUi(self)
        self.json_file = json_file
        self.edit_dialog_is_open = False
        self.setWindowTitle('OSWeGe Tools - Konfiguration')
        
        # set the values; depends on self.config_dict
        self.set_up_attribute_params(json_file)

        # connect the signals
        self.pushButtonGew.clicked.connect(lambda: self.open_edit_dialog('gewaesser'))
        self.pushButtonRl.clicked.connect(lambda: self.open_edit_dialog('rohrleitungen'))
        self.pushButtonDl.clicked.connect(lambda: self.open_edit_dialog('durchlaesse'))
        self.pushButtonSchaechte.clicked.connect(lambda: self.open_edit_dialog('schaechte'))
        self.pushButtonWehre.clicked.connect(lambda: self.open_edit_dialog('wehre'))
        self.dialogSaveCancel.accepted.connect(self.save_config)
        #self.dialogSaveCancel.accepted.connect(self.save_config_test)
        self.dialogSaveCancel.accepted.connect(self.close_edit_dialog)
        self.dialogSaveCancel.rejected.connect(self.close_edit_dialog)
        self.restoreButton.clicked.connect(
            lambda: self.set_up_attribute_params(
                file_config_for_reset
            )
        )

    def set_up_attribute_params(self, json_file):
        '''
        sets up params from self.config_dict
        :param json_file: path to the json file
        '''
        self.config_dict = get_config_from_json(json_file)

        # QListWidget
        self.comboBoxPrimrschl.clear()
        loadad_primary_key = self.config_dict['check_layer_defaults']['primaerschluessel_gew']
        self.comboBoxPrimrschl.addItems(self.config_dict['check_layer_defaults']['pflichtfelder']['gewaesser'])
        # check if the primary key is already in the list
        # if not, add it to the list
        if not loadad_primary_key in self.config_dict['check_layer_defaults']['pflichtfelder']['gewaesser']:
            self.comboBoxPrimrschl.addItem(loadad_primary_key)
        self.comboBoxPrimrschl.setCurrentText(loadad_primary_key)

        self.dict_list_widgets = {
            'gewaesser': self.WidgetPflichtfeldGew,
            'rohrleitungen': self.WidgetPflichtfeldRl,
            'durchlaesse': self.WidgetPflichtfeldDl,
            'schaechte':self.WidgetPflichtfeldSchaechte,
            'wehre': self.WidgetPflichtfeldWehre
        }
        for layer_key, widget_obj in self.dict_list_widgets.items():
            widget_obj.clear()
            widget_obj.addItems(self.config_dict['check_layer_defaults']['pflichtfelder'][layer_key])
            if not loadad_primary_key in self.config_dict['check_layer_defaults']['pflichtfelder'][layer_key]:
                widget_obj.addItem(loadad_primary_key)
        self.WidgetLaengeGew.setValue(self.config_dict['check_layer_defaults']['minimallaenge_gew'])
        self.comboBoxPrimrschl.currentTextChanged.connect(
            lambda: self.handle_field_in_all_lists(self.comboBoxPrimrschl.currentText())
        )

    def handle_field_in_all_lists(self, entry_i):
        '''
        Checks if the entry is in all list_items and adds it if not
        :param entry_i'''
        for layer_key, listwidget_obj in self.dict_list_widgets.items():
            self.add_required_field(entry_i, listwidget_obj)

    def add_required_field(self, entry_i, listwidget_obj):
        '''
        adds an entry (str) to the listwidget_obj if it is not already in the list of entries
        '''
        list_of_fields = [listwidget_obj.item(i).text() for i in range(listwidget_obj.count())]
        if not entry_i in list_of_fields:
            listwidget_obj.addItem(entry_i)

    def save_config_test(self):
        '''
        saves the current config to the self.json_file
        '''
        current_config = self.get_current_dialog_config()
        print(current_config)
        
    def open_edit_dialog(self, layer_key):
        edit_dialog_title = f'Pflichtfelder für {layer_key.capitalize()}-Layer ändern'
        current_list_widget = self.dict_list_widgets[layer_key]
        current_value_list = [current_list_widget.item(i).text() for i in range(current_list_widget.count())]
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
        if self.edit_dialog_is_open:
            self.editDialog.close()
            self.edit_dialog_is_open = False
            
    def closeEvent(self, event):
        self.close_edit_dialog()

    def update_from_entry_edit(self, layer_key):
        new_entries = self.editDialog.result()
        widget_obj = self.dict_list_widgets[layer_key]
        widget_obj.clear()
        widget_obj.addItems(new_entries)
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
                'rohleitungen',
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
        dialog_PflichtfeldGew =  [self.WidgetPflichtfeldGew.item(i).text() for i in range(self.WidgetPflichtfeldGew.count())]
        dialog_PflichtfeldRl =  [self.WidgetPflichtfeldRl.item(i).text() for i in range(self.WidgetPflichtfeldRl.count())]
        dialog_flichtfeldDl =  [self.WidgetPflichtfeldDl.item(i).text() for i in range(self.WidgetPflichtfeldDl.count())]
        dialog_PflichtfeldSchaechte =  [self.WidgetPflichtfeldSchaechte.item(i).text() for i in range(self.WidgetPflichtfeldSchaechte.count())]
        dialog_PflichtfeldWehre =  [self.WidgetPflichtfeldWehre.item(i).text() for i in range(self.WidgetPflichtfeldWehre.count())]
        dialog_primaerschluessel = self.comboBoxPrimrschl.currentText()
        dialog_minimallaenge = self.WidgetLaengeGew.value()
        dialog_dict = {
            'last_change': last_change,
            'layer_names': layer_names,
            'check_layer_defaults': {
                'pflichtfelder': {
                    'gewaesser': dialog_PflichtfeldGew,
                    'rohrleitungen': dialog_PflichtfeldRl,
                    'durchlaesse': dialog_flichtfeldDl,
                    'schaechte': dialog_PflichtfeldSchaechte,
                    'wehre': dialog_PflichtfeldWehre
                },
                'primaerschluessel_gew': dialog_primaerschluessel,
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