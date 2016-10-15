# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RasterIndexExtract
                                 A QGIS plugin
 Extract raster from index catalog images
                              -------------------
        begin                : 2016-10-12
        git sha              : $Format:%H$
        copyright            : (C) 2016 by G. Ryckelynck
        email                : guillaume.ryckelynck@region-alsace.eu
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QObject, pyqtSignal, Qt, QThread
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QMessageBox, QProgressBar, QPushButton
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from raster_index_extract_dialog import RasterIndexExtractDialog
import os.path
# Import QGIS Core
from qgis.core import *
from qgis.gui import QgsMessageBar
from qgis.analysis import QgsGeometryAnalyzer
# Import python standard modules
import shutil
import traceback
import time


class WorkerFiles(QObject):
    '''Worker to list files from directory
    '''

    def __init__(self, src, dst, selected_images):
        QObject.__init__(self)
        if os.path.isdir(src) is False or os.path.isdir(dst) is False:
            raise TypeError('Worker expected an existing directory for source and destination')
        self.src = src
        self.dst = dst
        self.selected_images = selected_images
        self.killed = False

    def run(self):
        result = None
        try:
            # Get files list from dir
            percent = 0
            copy_files = []
            nb_files = len(os.listdir(self.src))
            for i, filename in enumerate(os.listdir(self.src)):
                if self.killed is True:
                    # kill request received, exit loop early
                    break
                if os.path.isfile(os.path.join(self.src, filename)):
                    file = os.path.splitext(os.path.basename(filename))[0]
                    if file in self.selected_images:
                        copy_files.append(filename)
                percent = i / float(nb_files) * 100
                if percent == int(percent):
                    self.progressList.emit(int(percent))

            print self.selected_images
            print filename

            self.progressList.emit(100)

            # Copy files
            percent = 0
            nb_files = len(copy_files)
            error_files = []
            for fid, fval in enumerate(copy_files):
                if self.killed is True:
                    # kill request received, exit loop early
                    break
                src = os.path.join(self.src, fval)
                dst = os.path.join(self.dst, fval)
                try:
                    shutil.copy2(src, dst)
                except IOError, e:
                    error_files.append(fval)

                percent = fid / float(nb_files) * 100
                if percent == int(percent):
                    self.progressCopy.emit(percent)

            if self.killed is False:
                self.progressList.emit(100)
                self.progressCopy.emit(100)
                result = nb_files
        except Exception, e:
            # forward the exception upstream
            self.error.emit(e, str(e))

        self.finished.emit(result)

    def kill(self):
        self.killed = True

    finished = pyqtSignal(int)
    error = pyqtSignal(Exception, str)
    progressList = pyqtSignal(int)
    progressCopy = pyqtSignal(int)


class RasterIndexExtract:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Path to plugin directory
        self.plugin_directory = os.path.dirname(os.path.realpath(__file__))

        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RasterIndexExtract_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = RasterIndexExtractDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Raster Index Extract')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RasterIndexExtract')
        self.toolbar.setObjectName(u'RasterIndexExtract')

        # Clear editLine for source and destination path and connect select_source_directory and select_destination_directory to buttons
        self.dlg.leSrcPath.clear()
        self.dlg.pbChooseSrcPath.clicked.connect(self.select_source_directory)
        self.dlg.leDstPath.clear()
        self.dlg.pbChooseDstPath.clicked.connect(self.select_destination_directory)

        self.dlg.cbIndexLayers.activated[str].connect(self.load_cb_index_layer)

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
        return QCoreApplication.translate('RasterIndexExtract', message)

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
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/RasterIndexExtract/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'RasterIndexExtract'),
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Raster Index Extract'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def select_source_directory(self):
        srcDirectory = QFileDialog.getExistingDirectory(self.dlg, "Select source directory ")
        self.dlg.leSrcPath.setText(srcDirectory)

    def select_destination_directory(self):
        dstDirectory = QFileDialog.getExistingDirectory(self.dlg, "Select destination directory ")
        self.dlg.leDstPath.setText(dstDirectory)

    def load_cb_index_layer(self, layerName):
        if layerName:
            self.dlg.cbIndexColumnsName.clear()
            QgsMessageLog.logMessage(str(layerName))
            layer = QgsMapLayerRegistry.instance().mapLayersByName(str(layerName))[0]
            field_names = [field.name() for field in layer.pendingFields()]
            self.dlg.cbIndexColumnsName.addItems(field_names)
        else:
            QgsMessageLog.logMessage(unicode('load_cb_index_layer(): layerName not defined.'))

    def start_worker_files(self, src, dst, selected_images):
        # create a new worker instance
        worker = WorkerFiles(src, dst, selected_images)

        # configure the QgsMessageBar
        messageBar = self.iface.messageBar().createMessage('List and copy files...',)
        progressBarList = QProgressBar()
        progressBarCopy = QProgressBar()
        progressBarList.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        progressBarCopy.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        cancelButton = QPushButton()
        cancelButton.setText('Cancel')
        cancelButton.clicked.connect(worker.kill)
        messageBar.layout().addWidget(progressBarList)
        messageBar.layout().addWidget(progressBarCopy)
        messageBar.layout().addWidget(cancelButton)
        self.iface.messageBar().pushWidget(messageBar, self.iface.messageBar().INFO)
        self.messageBarFiles = messageBar

        # start the worker in a new thread
        thread = QThread()
        worker.moveToThread(thread)
        worker.finished.connect(self.finished_worker_files)
        worker.error.connect(self.workerError)
        worker.progressList.connect(progressBarList.setValue)
        worker.progressCopy.connect(progressBarCopy.setValue)
        thread.started.connect(worker.run)
        thread.start()
        self.thread_files = thread
        self.worker_files = worker

    def finished_worker_files(self, result):
        # clean up the worker and thread
        self.worker_files.deleteLater()
        self.thread_files.quit()
        self.thread_files.wait()
        self.thread_files.deleteLater()
        # remove widget from message bar
        self.iface.messageBar().popWidget(self.messageBarFiles)
        if result > 0:
            # report the result
            self.iface.messageBar().pushMessage('{nb} files copied.'.format(nb=result))
        elif result == 0:
            self.iface.messageBar().pushMessage('None file copied. Check extent layer.')
        else:
            # notify the user that something went wrong
            self.iface.messageBar().pushMessage('Something went wrong! See the message log for more information.', level=QgsMessageBar.CRITICAL, duration=3)

    def workerError(self, e, exception_string):
        QgsMessageLog.logMessage(u'Worker thread raised an exception:\n'.format(exception_string), level=QgsMessageLog.CRITICAL)

    def run(self):
        """Run method that performs all the real work"""

        # Clear and populate cbExtentLayers and cbIndexLayers
        layers = self.iface.legendInterface().layers()
        layer_list = []
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                layer.removeSelection()
                layer_list.append(layer.name())
        self.dlg.cbExtentLayers.clear()
        self.dlg.cbExtentLayers.addItems(layer_list)
        self.dlg.cbIndexLayers.clear()
        self.dlg.cbIndexLayers.addItems(layer_list)

        self.load_cb_index_layer(str(self.dlg.cbIndexLayers.currentText()))

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Get directories path
            srcDirectory = self.dlg.leSrcPath.text()
            dstDirectory = self.dlg.leDstPath.text()

            # Get selected layers
            extentLayerId = self.dlg.cbExtentLayers.currentIndex()
            extentLayer = layers[extentLayerId]
            indexLayerId = self.dlg.cbIndexLayers.currentIndex()
            indexLayer = layers[indexLayerId]

            # Get colum name of list for index layer
            indexLayerColumnName = self.dlg.cbIndexColumnsName.currentText()
            indexLayerColumn = indexLayer.fieldNameIndex(indexLayerColumnName)

            # Get buffer
            buffer = self.dlg.leBuffer.text()
            # Calculate buffer and create temporal shp layer
            tmp_dir = os.path.join(self.plugin_directory, 'tmp')
            tmp_shp = 'tmp.shp'
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)
            extentLayerBufferPath = os.path.join(tmp_dir, tmp_shp)
            QgsGeometryAnalyzer().buffer(extentLayer, extentLayerBufferPath, int(buffer), False, False, -1)

            extentLayerBuffer = QgsVectorLayer(extentLayerBufferPath, 'extent_layer_buffer', 'ogr')

            msg_success = u"Erreur lors de l'extraction. \nMerci de vérifier les paramètres saisis."

            if indexLayerColumn >= 0 and extentLayerBuffer.isValid() and os.path.isdir(srcDirectory) and os.path.isdir(dstDirectory):

                # Get dalles from index
                dalles_id = []
                dalles_name = []

                for extent_feature in extentLayerBuffer.getFeatures():
                    cands = indexLayer.getFeatures(QgsFeatureRequest().setFilterRect(extent_feature.geometry().boundingBox()))
                    for index_feature in cands:
                        if extent_feature.geometry().intersects(index_feature.geometry()):
                            attrs = index_feature.attributes()
                            dalles_id.append(index_feature.id())
                            dalle_name = os.path.splitext(os.path.basename(attrs[indexLayerColumn]))[0]
                            dalles_name.append(dalle_name)

                indexLayer.select(dalles_id)

                # Use worker thread to get files list from srcDirectory, check files to copy and copy files
                self.start_worker_files(srcDirectory, dstDirectory, dalles_name)

            # QgsMessageLog.logMessage(unicode(msg_success))
            # self.iface.mainWindow().statusBar().showMessage(msg_success)
            # self.iface.mainWindow().statusBar().clearMessage()
