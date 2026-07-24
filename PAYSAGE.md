# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/video-helper/blob/main/LANDSCAPE.md)

Bibliothèques Python voisines et concurrentes dans l'espace « manipulation
de fichiers vidéo », comparées à `video-helper`. Les notes vont de ⭐ (1) à
⭐⭐⭐⭐⭐ (5), évaluées sur la tâche visée par `video-helper` — le traitement
vidéo au quotidien pour les pipelines d'IA (validation, conversion,
découpage, concaténation, incrustation, extraction d'images, extraction
audio, multiplexage audio, incrustation de sous-titres, conversion de
formats de sous-titres, boucle d'image). Une bibliothèque optimisée pour un
tout autre usage (par ex. l'inférence temps réel, le montage non linéaire)
n'est pas pénalisée — la note reflète seulement l'adéquation à *ce* créneau.

## En un coup d'œil

<!-- TABLE:START -->
| Analyse vidéo | E/S multi-formats | Conversion / mise à l'échelle et rembourrage | Découpage / concaténation / incrustation | Extraction d'images | Sous-titres | Décodage GPU | Multi-destination | Installation légère |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **video-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| moviepy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| decord | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| torchvision.io | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| VidGear | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| OpenCV | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| ffmpeg-python | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| imageio | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| scenedetect | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/video-helper/main/assets/paysage.png)

La carte est un résumé en 2D des 8 critères : à lire comme une forme, pas comme un classement. « video-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Polyvalent ↔ Efficace** et **Vertical — Léger ↔ Performant**.
<!-- FIGURE:END -->

## Positionnement

`video-helper` se place volontairement à l'intersection de
l'**ergonomie à la moviepy** (conversion / découpage / concaténation /
incrustation / sous-titres incrustés en une ligne) et des **besoins des
pipelines d'IA** (répartiteur d'extraction d'images multi-backend,
accélération matérielle, destination torch à la demande, transmission des
en-têtes HTTP pour les flux résolus par yt-dlp). Il ne cherche
délibérément **pas** à concurrencer `PyAV` sur l'API paquet de bas niveau
ni `torchvision.io` sur les tenseurs torch natifs, et il garde `torch` et
`PIL` **optionnels** — vous n'en payez le coût d'installation que si vous
appelez réellement `destination="torch"` / `destination="pil"`. Ce
compromis est le principal facteur de différenciation face à
`torchvision.io` (torch obligatoire) et face à `decord` (compilation depuis
les sources d'ffmpeg4 requise).

D'où viennent les notes, en une phrase chacune : les E/S multi-formats
reposent sur le sondage et le multiplexage natifs ffmpeg ; l'extraction
d'images est un répartiteur au-dessus de VidGear / PyAV / ffmpeg-pipe, avec
des modes épars, fenêtrés et en flux ainsi qu'une recherche par image-clé ;
les sous-titres couvrent l'incrustation libass et la conversion SRT→VTT avec
CSS ; le décodage GPU est une accélération matérielle automatique
(VideoToolbox / NVDEC) via PyAV / ffmpeg-pipe ; et la multi-destination
renvoie du numpy par défaut, avec torch et PIL disponibles sur demande.

## Quand choisir quoi

- **`video-helper`** — préparation vidéo pour les pipelines d'IA :
  conversion par lots + mise à l'échelle et rembourrage vers une entrée de
  modèle fixe, échantillonnage d'images épars / fenêtré avec accélération
  matérielle, incrustation de sous-titres, multiplexage audio pour la
  narration, concaténation pour assembler des clips d'entraînement,
  transmission des en-têtes HTTP pour les flux résolus par yt-dlp.
- **`moviepy`** — scénarisation façon timeline (graphes de clips à
  placer-et-couper), composition de plusieurs clips en un seul, cartons de
  titre rapides. Pas idéal pour le débit par lots.
- **`PyAV`** — vous avez besoin d'un contrôle au niveau paquet (réglages de
  codec personnalisés, placement des images-clés, précision de recherche).
- **`decord` / `torchvision.io`** — lectures d'images en accès aléatoire
  pur directement en tenseurs torch, avec une boucle d'entraînement qui
  domine le coût total (flux de travail axé sur le dataloader).
- **`VidGear`** — vous avez besoin des utilitaires OpenCV+FFmpeg avec le
  stabilisateur intégré et l'accès épars vous importe peu.
- **`OpenCV`** — prototypage rapide, sans objectif de débit par lots ni
  besoin de sous-titres.
- **`ffmpeg-python`** — vous voulez composer un graphe de filtres arbitraire
  et vous n'avez pas besoin d'interopérabilité numpy.
- **`scenedetect`** — vous avez spécifiquement besoin de la détection des
  limites de plans.
