# -*- coding: utf-8 -*-
"""
/***************************************************************************
 oswege_tools
                                 A QGIS plugin
 werkzeugsammlung
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-04-04
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Jannik Schilling
        email                : jannik.schilling@uni-rostock.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import sys
import inspect

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsApplication,
    Qgis
)
from qgis.PyQt.QtCore import (
    QSettings,
    QTranslator,
    QCoreApplication
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QPushButton
)
from qgis.utils import iface

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog and provider
from .stationierung_dialog import stationierungDialog
from .oswegeToolsProvider import oswegeToolsProvider
from .hilfsfunktionen import (
    compare_versions,
    get_metadata
)

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

class oswege_tools_buttons:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # processing part
        self.provider = None
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'oswege_tools_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&oswege_tools')
        self.toolbar = self.iface.addToolBar('OswegeTools')
        self.toolbar.setObjectName('OswegeTools')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        
        
        # Check version
        path_meta_local = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            'metadata.txt'))
        lokal_repo, lokal_version = get_metadata(path_meta_local)
        path_meta_git = 'https://raw.githubusercontent.com/Jannik-Schilling/OSWeGe_Tools/refs/heads/main/metadata.txt'
        url_git = 'https://github.com/Jannik-Schilling/OSWeGe_Tools'
        try:
            git_repo, git_version = get_metadata(path_meta_git, lokal=False)
        except Exception:
            git_version = lokal_version

        versions_status = compare_versions(lokal_version, git_version)
        def open_git_link():
            try:
                import webbrowser
                webbrowser.open(url_git)
            except Exception:
                iface.messageBar().pushMessage(
                    "Info",
                    (
                        'Konnte denk Link nicht direkt öffen. Das Plugin ist unter '
                         + url_git
                         + 'verfügbar'
                    ),
                    level=Qgis.Warning,
                    duration=2
               )
        if versions_status == 1:
            widget_version = iface.messageBar().createMessage("OSWeGe Tools", (
                    'Es gibt eine neue Version ('
                    + str(lokal_version)
                    + ' > '
                    + str(git_version)
                    + ') des Plugins auf GitHub'
                )
            )
            button_git = QPushButton(widget_version)
            button_git.setText('öffne GitHub')
            button_git.clicked.connect(open_git_link)
            widget_version.layout().addWidget(button_git)
            iface.messageBar().pushWidget(widget_version, Qgis.Info, duration=8)
        elif versions_status == 2:
            iface.messageBar().pushMessage(
                "OSWeGe Tools [DEV]",
                (
                    'Die aktuelle Version Plugins ('
                    + str(lokal_version)
                    + ') ist neuer als die auf GitHub verfügbare ('
                    + str(git_version)
                    + ')'
                ),
                level=Qgis.Warning,
               
            )
        else:
            pass
            #iface.messageBar().pushMessage("Info", "Das Plugin ist aktuell", level=Qgis.Info, duration=8)
        
    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = oswegeToolsProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('oswege_tools', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            # self.iface.addToolBarIcon(action)
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(
            self.plugin_dir,
            'icons',
            'icon.png')

        self.add_action(
            icon_path,
            text=self.tr(u'Stationierung eines Gewässers anzeigen'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

        # fuer Processing
        self.initProcessing()


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        QgsApplication.processingRegistry().removeProvider(self.provider)

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&oswege_tools'),
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.canvas = iface.mapCanvas()
            self.dlg = stationierungDialog(
                canvas=self.canvas
            )
        self.dlg.show()

