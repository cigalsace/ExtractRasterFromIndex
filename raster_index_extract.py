# -*- coding: utf8 -*-
"""
/***************************************************************************
 RasterIndexExtract
                                 A QGIS plugin
 Extract raster from index catalog images
                              -------------------
        begin                : 2016-10-12
        git sha              : $Format:%H$
        copyright            : (C) 2017 by G. Ryckelynck
        email                : guillaume.ryckelynck@grandest.fr
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
from __future__ import unicode_literals

from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QObject, pyqtSignal, Qt, QThread
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QProgressBar, QPushButton, QMessageBox

# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from raster_index_extract_dialog import RasterIndexExtractDialog
import os
import sys
# Import QGIS Core
from qgis.core import *
from qgis.gui import QgsMessageBar
from qgis.analysis import QgsGeometryAnalyzer
# Import python standard modules
import shutil
import time
import json
import ftplib
import urllib2
import traceback
import ConfigParser


# CONFIG
CONFIG_FILE = 'config.json'
LOG_FILE = 'log.txt'


# HELPERS
def getPath(name, basepath=None):
    if not basepath:
        basepath = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(basepath, name)


def log(message='', level='INFO'):
    log_file = getPath(LOG_FILE)
    time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    line = time_now + ' - ' + level + ': ' + message + "\n"
    with open(log_file, 'a') as f:
        f.write(line.encode('utf8'))


def getMetadata():
    metadata = {}
    config = ConfigParser.ConfigParser()
    config.read(os.path.join(os.path.dirname(__file__), 'metadata.txt'))
    metadata['name'] = config.get('general', 'name')
    metadata['description'] = config.get('general', 'description')
    metadata['version'] = config.get('general', 'version')
    metadata['author'] = config.get('general', 'author')
    metadata['email'] = config.get('general', 'email')
    return metadata


# FTP HELPERS
def getFileListFromFtp(ftp_config, src):
    result = []
    try:
        ftp = ftplib.FTP(ftp_config['ftp_url'], ftp_config['ftp_login'], ftp_config['ftp_pwd'])
        ftp.voidcmd('TYPE I')
        ftp.cwd(src)
        result = ftp.nlst()
        ftp.quit()
    except:
        log()
        log(u'Get files list from FTP error.', 'ERROR')
    return result


def downloadFileFromFtp(ftp_config, filename, src=None, dst=None, overwrite=True):
    try:
        if dst:
            os.chdir(dst)
        dst_size = 0
        if os.path.isfile(filename):
            dst_size = os.path.getsize(filename)
        ftp = ftplib.FTP(ftp_config['ftp_url'], ftp_config['ftp_login'], ftp_config['ftp_pwd'])
        ftp.voidcmd('TYPE I')
        if src:
            ftp.cwd(src)
        src_size = ftp.size(filename)
        log()
        log('Dowload FTP file')
        log('src: ' + src)
        log('dst: ' + dst)
        log('filename: ' + filename)
        log('src size: ' + str(src_size))
        log('dst size: ' + str(dst_size))
        if (filename in ftp.nlst() and (overwrite or ((not overwrite and not os.path.isfile(filename)) or (not overwrite and os.path.isfile(filename) and dst_size != src_size)))):
            with open(filename, 'w+b') as f:
                ftp.retrbinary("RETR " + filename, f.write)
            log('dst new size: ' + str(os.path.getsize(filename)))
            log('status: file copied')
        else:
            log('status: file escaped')
        ftp.quit()
    except:
        log()
        log(u'Download file from FTP error', 'ERROR')
        log('src: ' + src)
        log('dst: ' + dst)
        log('filename: ' + filename)


# WORKER CLASS
class WorkerFiles(QObject):
    '''Worker to list files from directory
    '''

    def __init__(self, checked, src, dst, selected_images, local_config=False):
        QObject.__init__(self)
        if os.path.isdir(dst) is False:
            raise TypeError('Worker expected an existing directory for destination')
        self.src = src
        self.dst = dst
        self.selected_images = selected_images
        self.killed = False
        self.checked = checked
        self.local_config = local_config

    def run(self):
        result = 0
        ftp = False
        percent = 0
        copy_files = []

        if self.checked == 'local':
            files_list = os.listdir(self.src)
            if os.path.isdir(self.src) is False:
                raise TypeError('Worker expected an existing directory for source')

        elif self.checked == 'remote':
            files_list = getFileListFromFtp(self.local_config, self.src)

        nb_files = len(files_list)
        for i, filename in enumerate(files_list):
            if self.killed is True:
                # kill request received, exit loop early
                break

            file = os.path.splitext(os.path.basename(filename))[0]
            if file in self.selected_images:
                copy_files.append(filename)

            percent = i / float(nb_files) * 100
            if percent == int(percent):
                self.progressList.emit(int(percent))

        self.progressList.emit(100)

        # Copy files
        percent = 0
        nb_files = len(copy_files)
        log()
        log('Nb files to copy: ' + str(nb_files))
        error_files = []
        for fid, fval in enumerate(copy_files):
            if self.killed is True:
                # kill request received, exit loop early
                break

            try:
                if self.checked == 'local':
                    dst = os.path.join(self.dst, fval)
                    src = os.path.join(self.src, fval)
                    shutil.copy2(src, dst)
                elif self.checked == 'remote':
                    downloadFileFromFtp(self.local_config, fval, self.src, self.dst, False)
            except IOError, e:
                error_files.append(fval)
                self.error.emit(e, str(e))

            percent = fid / float(nb_files) * 100
            self.progressCopy.emit(int(percent))
            result = fid

        if self.killed is False:
            self.progressList.emit(100)
            self.progressCopy.emit(100)

        self.finished.emit(str(result) + '/' + str(nb_files))

    def kill(self):
        self.killed = True

    finished = pyqtSignal(str)
    error = pyqtSignal(Exception, str)
    progressList = pyqtSignal(int)
    progressCopy = pyqtSignal(int)


# RasterIndexExtract PLUGIN MAIN CLASS
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
        # Path to config json file
        self.config_file = os.path.join(self.plugin_directory, CONFIG_FILE)
        # Config loaded
        self.is_config_local_loaded = False
        self.is_config_remote_loaded = False
        self.remote_config = {}
        self.local_config = {}

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

        # Connect Run and Cancel buttons
        self.dlg.pbRun.clicked.connect(self.runExtract)
        self.dlg.pbCancel.clicked.connect(self.cancel)

        # Clear editLine for source and destination path and connect select_source_directory and select_destination_directory to buttons
        self.dlg.leSrcPath.clear()
        self.dlg.pbChooseSrcPath.clicked.connect(self.select_source_directory)
        self.dlg.leDstPath.clear()
        self.dlg.pbChooseDstPath.clicked.connect(self.select_destination_directory)

        # Connect radio buttons for remote source
        self.dlg.rb_locale.toggled.connect(self.rb_locale_clicked)
        self.dlg.rb_remote.toggled.connect(self.rb_remote_clicked)

        self.dlg.cb_remote.activated[str].connect(self.select_source_remote)

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
            layer = QgsMapLayerRegistry.instance().mapLayersByName(str(layerName))[0]
            field_names = [field.name() for field in layer.pendingFields()]
            self.dlg.cbIndexColumnsName.addItems(field_names)
        else:
            QgsMessageLog.logMessage(unicode('load_cb_index_layer(): layerName not defined.'))

    def select_source_remote(self):
        self.remote_src_index = self.dlg.cb_remote.currentIndex()
        self.remote_src = self.remote_config['bdd'][self.dlg.cb_remote.currentIndex()]

    def rb_locale_clicked(self, enabled):
        if enabled:
            self.dlg.leSrcPath.setEnabled(True)
            self.dlg.pbChooseSrcPath.setEnabled(True)
        else:
            self.dlg.leSrcPath.setEnabled(False)
            self.dlg.pbChooseSrcPath.setEnabled(False)

    def rb_remote_clicked(self, enabled):
        if enabled:
            self.dlg.cb_remote.setEnabled(True)
            self.dlg.cbIndexLayers.setEnabled(False)
            self.dlg.cbIndexColumnsName.setEnabled(False)
        else:
            self.dlg.cb_remote.setEnabled(False)
            self.dlg.cbIndexLayers.setEnabled(True)
            self.dlg.cbIndexColumnsName.setEnabled(True)

    def start_worker_files(self, checked, src, dst, selected_images, local_config):
        # create a new worker instance
        worker = WorkerFiles(checked, src, dst, selected_images, local_config)

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
            self.iface.messageBar().pushMessage('{} files copied.'.format(result))
        elif result == 0:
            self.iface.messageBar().pushMessage('None file copied. Check extent layer.')
        else:
            # notify the user that something went wrong
            self.iface.messageBar().pushMessage('Something went wrong! See the message log for more information.', level=QgsMessageBar.CRITICAL, duration=3)

    def workerError(self, e, exception_string):
        QgsMessageLog.logMessage(u'Worker thread raised an exception:\n'.format(exception_string), level=QgsMessageLog.CRITICAL)

    def cancel(self):
        '''Close dialog plugin
        '''
        self.dlg.close()

    def runExtract(self):
        '''Process extract
        '''
        # Create or clear log file
        open(getPath(LOG_FILE), 'w').close()

        indexLayerColumn = False

        # Initiate generic error message
        msg_error = u"Erreur lors de l'extraction: merci de vérifier les paramètres saisis."

        # Get directories path
        dstDirectory = self.dlg.leDstPath.text()
        # Empty tmp directory = remove and recreate it
        tmp_dir = os.path.join(self.plugin_directory, 'tmp')

        try:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)
            os.makedirs(tmp_dir)
        except:
            message = 'Unable to remove temporal layer.'
            log()
            log(message, 'ERROR')
            QgsMessageLog.logMessage(unicode(message))

        checked = False
        # If local radio button is activated
        if self.dlg.rb_locale.isChecked():
            checked = 'local'
            # Define source directory
            srcDirectory = self.dlg.leSrcPath.text()
            if not os.path.isdir(srcDirectory):
                srcDirectory = False
            # Get index layer
            indexLayerId = self.dlg.cbIndexLayers.currentIndex()
            if len(self.layers):
                indexLayer = self.layers[indexLayerId]
                # Get colum name of list for index layer
                indexLayerColumnName = self.dlg.cbIndexColumnsName.currentText()
                indexLayerColumn = indexLayer.fieldNameIndex(indexLayerColumnName)

        # If remote radio button is activated
        elif self.dlg.rb_remote.isChecked():
            checked = 'remote'
            # Define source directory
            srcDirectory = self.remote_src['src_directory']
            # Get index layer
            try:
                # Load file from FTP in tmp_dir
                for ext in ['.shp', '.dat', '.dbf', '.shx', '.prj', '.id', '.tab', '.map']:
                    filename = self.remote_src['index_file'] + ext
                    downloadFileFromFtp(self.local_config, filename, self.remote_src['index_path'], tmp_dir)
                # Load index file in QGIS
                indexLayerPath = os.path.join(tmp_dir, self.remote_src['index_file'] + '.shp')
                indexLayer = self.iface.addVectorLayer(indexLayerPath, self.remote_src['index_file'] + '.shp', 'ogr')
                # Get colum name of list for index layer
                indexLayerColumnName = self.remote_src['index_col_name']
            except Exception as e:
                QgsMessageLog.logMessage(unicode("Can't get index file from FTP or load in QGIS: " + str(e)))

        # Get extent layer
        if len(self.layers):
            extentLayerId = self.dlg.cbExtentLayers.currentIndex()
            extentLayer = self.layers[extentLayerId]
            # Get buffer
            buffer = self.dlg.leBuffer.text()
            # Calculate buffer and create temporal shp layer
            extent_buffer_shp = 'extent_buffer.shp'
            extentLayerBufferPath = os.path.join(tmp_dir, extent_buffer_shp)
            QgsGeometryAnalyzer().buffer(extentLayer, extentLayerBufferPath, int(buffer), False, False, -1)

            extentLayerBuffer = QgsVectorLayer(extentLayerBufferPath, 'extent_buffer_layer', 'ogr')
            extentLayerBuffer_isValid = True
            if not extentLayerBuffer.isValid():
                extentLayerBuffer_isValid = False
                msg_error = "Fichier d'emprise (buffer) non valide."
                log(msg_error, 'ERROR')

        log()
        log('indexLayer CRS: ' + str(indexLayer.crs().authid()))
        log('extentLayer CRS: ' + str(extentLayer.crs().authid()))
        is_crs_equal = True
        if indexLayer.crs().authid() != extentLayerBuffer.crs().authid():
            is_crs_equal = False
            msg_error = "Les systèmes de projection (CRS) des couches 'index' (" + str(indexLayer.crs().authid()) + ") et 'emprise/buffer' (" + str(extentLayer.crs().authid()) + ") sont différents."
            log(msg_error, 'ERROR')

        if indexLayerColumn >= 0 and extentLayerBuffer_isValid and srcDirectory and os.path.isdir(dstDirectory) and is_crs_equal:
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
            self.start_worker_files(checked, srcDirectory, dstDirectory, dalles_name, self.local_config)

        else:
            QgsMessageLog.logMessage(msg_error.encode('utf8'))
            QMessageBox.warning(self.dlg, 'Extraction erreur!', msg_error, QMessageBox.Ok)

    def run(self):
        """Run method that performs all the real work"""
        metadata = getMetadata()
        self.dlg.labelMention.setOpenExternalLinks(True)
        self.dlg.labelMention.setText(metadata['name'] + ' - ' + metadata['version'] + ' - <a href="file:///' + getPath(LOG_FILE) + '">log.txt</a>')

        # Get local config file
        if os.path.isfile(self.config_file):
            # Get and load config file
            with open(self.config_file) as data:
                self.local_config = json.load(data)
                self.is_config_local_loaded = True

        # Get and load proxy configuration from QGIS
        s = QSettings()
        proxyEnabled = s.value("proxy/proxyEnabled", "")
        proxyHost = s.value("proxy/proxyHost", "")
        proxyPort = s.value("proxy/proxyPort", "")
        proxyUser = s.value("proxy/proxyUser", "")
        proxyPassword = s.value("proxy/proxyPassword", "")
        if proxyEnabled:
            proxy_url = ''.join(['http://', proxyUser, ':', proxyPassword, '@', proxyHost, ':', proxyPort])
            proxy = urllib2.ProxyHandler({'ftp': proxy_url, 'http': proxy_url, 'https': proxy_url})
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)

        # Get remote config file
        if self.is_config_local_loaded and not self.is_config_remote_loaded:
            remote_config_file = self.local_config['remote_config']
            try:
                remote_data = urllib2.urlopen(remote_config_file)
                self.remote_config = json.loads(remote_data.read())
                # Load BDD
                bdd_list = []
                for bdd in self.remote_config['bdd']:
                    bdd_list.append(bdd['name'])
                self.is_config_remote_loaded = True
            except urllib2.URLError:
                bdd_list = ['Remote URL error']
            self.dlg.cb_remote.clear()
            self.dlg.cb_remote.addItems(bdd_list)
            if self.is_config_remote_loaded:
                self.select_source_remote()
            else:
                self.dlg.rb_remote.setEnabled(False)

        # Clear and populate cbExtentLayers and cbIndexLayers
        self.layers = self.iface.mapCanvas().layers()
        layer_list = []
        for layer in self.layers:
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
        self.dlg.exec_()
