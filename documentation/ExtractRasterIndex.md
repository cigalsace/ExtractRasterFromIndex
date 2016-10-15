# Extract raster from index

ExtractRasterFromIndex est une extension (plugin) QGIS qui permet d'extraire un ensemble de dalles d'un raster à partir d'un catalogue d'images (index) et d'une emprise.

## Installation

- Télécharger et dézipper le code du plugin sur votre ordinateur das un répertoirte nommé `ExtractRasterFromIndex`
- Placer le dossier résultant (`ExtractRasterFromIndex`) dans le répertoire des plugins QGIS (généralement de la forme `utilisateurs/user/.qgis2/python/plugins`)

## Utilisation

### Requis

- Un raster découpé sous forme de dalles, stocké dans dossier unique sans arborescence
- Un fichier d'index des images raster (catalogue d'images avec un champ correspondant au nom de chaque dalle)
- Un fichier d'emrise d'extraction

**NB:** Pour le bon fonctionnement du plugin, il est important que le système de projection des fichiers soit correctement défini.

### Utilisation

![qgis_window.png](images/qgis_window.png)

- Chargez le fichier du catalogue d'images (index) dans QGIS
- Chargez le fichier d'emprise dans QGIS (au dessus du catalogue d'images)
- Ouvrez le plugin "ExtractRasterFromIndex" (bouton ![icon.png](images/icon.png))
- Renseignez les différents champs demandés (tous sont obligatoires)
- Cliquez sur OK pour démarrer l'extraction. Une barre de progression s'affiche permettant de suivre la lecture et copie des fichiers

**NB:** En cas de problème, si un message d'erreur apparaît, il peut-être nécessaire de redémarrer QGIS pour s'assurer du bon fonctionnement du plugin.

### Liste des paramètres

![plugin_dialog.png](images/plugin_dialog.png)

- "Select extent layer": couche d'emprise à extraire
- "Buffer": buffer autour de l'emprise à ajouter (en mètres)
- "Select index layer": couche du catalogue d'images
- "Column name": nom de la colonne attributaire de la couche d'index contenant le nom des images
- "Source": répertoire contenant les images du raster
- "Destination": répertoire de destination pour les images extraites

**NB:** Pensez, lors de la diffusion à transmettre les métadonnées et l'ensemble des ressources nécessaires au bon usage des données extraites (licence, guide d'utilisation etc.).
