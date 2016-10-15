# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RasterIndexExtract
                                 A QGIS plugin
 Extract raster from index catalog images
                             -------------------
        begin                : 2016-10-12
        copyright            : (C) 2016 by G. Ryckelynck
        email                : guillaume.ryckelynck@region-alsace.eu
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load RasterIndexExtract class from file RasterIndexExtract.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .raster_index_extract import RasterIndexExtract
    return RasterIndexExtract(iface)
