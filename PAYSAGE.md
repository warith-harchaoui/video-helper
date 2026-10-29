# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/video-helper/blob/main/LANDSCAPE.md)

Bibliothèques Python voisines et concurrentes dans l'espace « manipulation
de fichiers vidéo », comparées à `video-helper`. Les notes vont de ⭐ (1) à
⭐⭐⭐⭐⭐ (5), évaluées sur la tâche visée par `video-helper` : le traitement
vidéo au quotidien pour les pipelines d'IA (validation, conversion,
découpage, concaténation, incrustation, extraction d'images, extraction
audio, multiplexage audio, incrustation de sous-titres, conversion de
formats de sous-titres, boucle d'image). Une bibliothèque optimisée pour un
tout autre usage (par ex. l'inférence temps réel, le montage non linéaire)
n'est pas pénalisée ; la note reflète seulement l'adéquation à *ce* créneau.

## En un coup d'œil

<!-- TABLE:START -->
| Analyse vidéo | E/S multi-formats | Conversion / mise à l'échelle et rembourrage | Découpage / concaténation / incrustation | Extraction d'images | Sous-titres | Décodage GPU | Multi-destination | Installation légère |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **video-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| moviepy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| decord | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| torchvision.io | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| VidGear | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| OpenCV | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| ffmpeg-python | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| imageio | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| scenedetect | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/video-helper/main/assets/paysage.png)

La carte est un résumé en 2D des 8 critères : à lire comme une forme, pas comme un classement. « video-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal : Précision ↔ Polyvalence** et **Vertical : Simplicité ↔ Efficacité**.
<!-- FIGURE:END -->

## Positionnement

`video-helper` se place volontairement à l'intersection de
l'**ergonomie à la moviepy** (conversion / découpage / concaténation /
incrustation / sous-titres incrustés en une ligne) et des **besoins des
pipelines d'IA** (répartiteur d'extraction d'images multi-backend,
accélération matérielle, destination torch à la demande, transmission des
en-têtes HTTP pour les flux résolus par yt-dlp). Il ne cherche
délibérément **pas** à concurrencer `PyAV` sur l'API paquet de bas niveau
ni `torchvision.io` sur les tenseurs torch natifs et il garde `torch` et
`PIL` **optionnels** : vous n'en payez le coût d'installation que si vous
appelez réellement `destination="torch"` / `destination="pil"`. Ce
compromis est le principal facteur de différenciation face à
`torchvision.io` (torch obligatoire) et face à `decord`, dont la dernière
publication ne fournit aucune roue pour Apple Silicon ni pour un Python ≥ 3.9
sur macOS : il faut donc le compiler depuis les sources contre `ffmpeg@4`.

D'où viennent les notes, en une phrase chacune : les E/S multi-formats
reposent sur le sondage et le multiplexage natifs ffmpeg ; l'extraction
d'images est un répartiteur au-dessus de VidGear / PyAV / ffmpeg-pipe, avec
des modes épars, fenêtrés et en flux ainsi qu'une recherche par image-clé ;
les sous-titres couvrent l'incrustation libass et la conversion SRT→VTT avec
CSS ; le décodage GPU détecte automatiquement l'accélération matérielle de
la plateforme (VideoToolbox sur macOS, CUDA/NVDEC ou Quick Sync sur
Linux/Windows) via PyAV / ffmpeg-pipe ; et la multi-destination renvoie du
numpy par défaut, avec torch et PIL disponibles sur demande.

## Quand choisir quoi

- **`video-helper`** : préparation vidéo pour les pipelines d'IA.
  Conversion par lots plus mise à l'échelle et rembourrage vers une entrée de
  modèle fixe, échantillonnage d'images épars / fenêtré avec accélération
  matérielle, incrustation de sous-titres, multiplexage audio pour la
  narration, concaténation pour assembler des clips d'entraînement,
  transmission des en-têtes HTTP pour les flux résolus par yt-dlp.
- **`moviepy`** : scénarisation façon timeline (graphes de clips à
  placer-et-couper), composition de plusieurs clips en un seul, cartons de
  titre rapides. Pas idéal pour le débit par lots.
- **`PyAV`** : vous avez besoin d'un contrôle au niveau paquet (réglages de
  codec personnalisés, placement des images-clés, précision de recherche).
- **`decord` / `torchvision.io`** : lectures d'images en accès aléatoire
  pur, décodées sur GPU, directement en tenseurs torch, avec une boucle
  d'entraînement qui domine le coût total (flux de travail axé sur le
  dataloader).
- **`VidGear`** : vous avez besoin des utilitaires OpenCV+FFmpeg avec le
  stabilisateur intégré et l'accès épars vous importe peu.
- **`OpenCV`** : prototypage rapide, sans objectif de débit par lots ni
  besoin de sous-titres.
- **`ffmpeg-python`** : vous voulez composer un graphe de filtres arbitraire
  et vous n'avez pas besoin d'interopérabilité numpy.
- **`scenedetect`** : vous avez spécifiquement besoin de la détection des
  limites de plans.

## Sources et date de relevé

Relevé le **27 octobre 2026**. Chaque version et chaque date ci-dessous ont été
lues ce jour-là dans les métadonnées de publication que chaque projet dépose
lui-même sur PyPI (`https://pypi.org/pypi/<nom>/json`) : c'est le registre de
l'éditeur, pas un résumé de seconde main.

| Projet | Dernière publication | Date |
|---|---|---|
| moviepy | 2.2.1 | 2025-05-21 |
| av (PyAV) | 19.0.2 | 2026-10-21 |
| decord | 0.6.0 | 2021-06-14 |
| torchvision | 0.29.1 | 2026-09-30 |
| vidgear | 0.3.6 | 2026-10-26 |
| opencv-python | 5.0.0.93 | 2026-07-02 |
| ffmpeg-python | 0.2.0 | 2019-07-06 |
| imageio | 2.38.1 | 2026-10-08 |
| scenedetect | 0.7.2 | 2026-10-12 |

Deux lignes de ce tableau portent l'essentiel du tableau d'étoiles ci-dessus.

- Les ⭐⭐ de `decord` en **installation légère** ne sont pas un avis, c'est sa
  liste de roues : la version 0.6.0 publie `macosx_10_15_x86_64` (CPython
  3.6–3.8), `manylinux2010_x86_64` et `win_amd64`, rien d'autre.
  `video-helper` a prototypé un backend decord pendant le développement de la
  v1.4 puis l'a retiré pour cette raison précise ; le raisonnement figure dans
  [SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md),
  section *History*.
- Les ⭐⭐⭐⭐⭐ de `ffmpeg-python` en **installation légère** et sa date de
  publication de 2019 sont un seul et même fait vu deux fois : c'est un petit
  constructeur d'arguments, terminé, posé sur la ligne de commande ffmpeg. C'est
  aussi la raison pour laquelle `video-helper` en dépend.

Les colonnes des autres bibliothèques sont un jugement d'**adéquation à ce
créneau**, lu dans la documentation et l'API publique de chaque projet. Ce n'est
pas un comparatif chronométré et aucun chiffre présenté ici ne sort d'un tel
comparatif. Une affirmation que nous n'avons pas pu sourcer a été retirée
plutôt qu'estimée.

La ligne de `video-helper` n'est pas une affirmation sur le logiciel d'autrui :
les capacités qui la fondent sont les fonctions listées dans
[LISEZMOI.md](https://github.com/warith-harchaoui/video-helper/blob/main/LISEZMOI.md)
et couvertes par la suite de tests. Les chiffres de décodage derrière
**décodage GPU** et **extraction d'images** viennent de
[SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md),
mesurés sur Apple Silicon / macOS (Darwin 25.5.0) avec le ffmpeg système 8.1.2
et PyAV 17.1.0. Cet instantané date de la refonte des backends en v1.4.0 et n'a
pas été remesuré depuis : à lire comme un ordre de grandeur plutôt que comme
les millisecondes du jour.

## Idées à reprendre

Étudié plutôt que deviné : ce que chaque voisin fait mieux, puis ce que cette bibliothèque devrait changer pour l'égaler. Rien ici n'est un engagement : c'est la liste de lecture dont part la version suivante.

- **`torchcodec` — le décodeur vers lequel PyTorch pointe désormais** — Un décodage processeur de premier plan avec une accélération CUDA, la vidéo étant exposée comme une suite d'images indexable par position ou par instant de présentation. Cela compte doublement ici : l'API vidéo de `torchvision.io`, que ce tableau note encore, est en train d'être remplacée par lui, donc cette ligne relève désormais de l'héritage plutôt que d'une alternative vivante.

- **`decord` puis `deffcode` — le positionnement à l'image près comme garantie énoncée** — Se placer sur un horodatage puis obtenir l'image demandée — et non l'image clé la plus proche — est la propriété que les appelants supposent sans la vérifier. `deffcode` (avril 2026) en fait son argument principal.

- **`scenedetect` — les frontières de plan comme opération de premier rang** — Couper sur le contenu plutôt que sur un intervalle fixe est ce que veulent réellement la plupart des usages en aval, puis cela se compose avec le découpage que cette bibliothèque fait déjà.

- **`VidGear` — un tampon de lecture en fil d'exécution devant le consommateur** — Décoder sur le fil appelant fait payer à chaque consommateur toute la latence de décodage par image. Un tampon d'avance borné coûte peu, puis c'est la leçon qu'a tirée le jumeau Rust de capture à propos des files bornées.
