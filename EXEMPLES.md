# Exemples Video Helper

Recettes pratiques pour la surface publique de `video-helper`. Chaque
extrait suppose :

```python
import video_helper as vh
import os_helper as osh
```

et que `ffmpeg` est installé et accessible dans le `PATH`. La recette
`burn_subtitles` exige en plus un ffmpeg compilé avec `libass`.

---

## Table des matières

1. [Installation](#installation)
2. [Sonder & valider](#sonder--valider)
3. [Convertir & redimensionner](#convertir--redimensionner)
4. [Accès aux frames](#accès-aux-frames)
   - [Parcourir les frames](#parcourir-les-frames)
   - [Accès épars / aléatoire](#accès-épars--aléatoire)
   - [Choisir un backend](#choisir-un-backend)
   - [Accélération matérielle](#accélération-matérielle)
   - [Destination : tenseurs numpy ou torch](#destination--tenseurs-numpy-ou-torch)
   - [Écrire des frames vers une vidéo](#écrire-des-frames-vers-une-vidéo)
5. [Découpe temporelle](#découpe-temporelle)
6. [Primitives de pipeline](#primitives-de-pipeline)
   - [Vidéo noire](#vidéo-noire)
   - [Boucle d'image](#boucle-dimage)
   - [Concaténer](#concaténer)
   - [Incruster une image](#incruster-une-image)
   - [Extraire / muxer l'audio](#extraire--muxer-laudio)
   - [Incruster des sous-titres](#incruster-des-sous-titres)
7. [Outils de sous-titrage](#outils-de-sous-titrage)
   - [SRT → VTT + CSS](#srt--vtt--css)
   - [Couleurs uniques](#couleurs-uniques)

---

## Installation

```bash
# Base uniquement : vidgear + opencv + ffmpeg-python (sans backend optionnel).
pip install --force-reinstall --no-cache-dir \
  video-helper
```

Extras optionnels, à combiner entre eux ou à installer en bloc via `[all]` :

```bash
# [pyav]  : meilleur décodeur séquentiel par fenêtre + accès épars. Honore hwaccel.
# [torch] : destination="torch" (NCHW / CTHW RGB sur cpu / mps / cuda).
# [pil]   : destination="pil" (PIL.Image, RGB, size=(W, H)).
# [all]   : tout (pyav + torch + pillow).

pip install --force-reinstall --no-cache-dir \
  "video-helper[all]"
```

Il faut aussi `ffmpeg`. macOS : `brew install ffmpeg` (installez `brew` grâce à [brew.sh](https://brew.sh/)). Linux : `apt install ffmpeg`. Windows : voir le [site ffmpeg](https://ffmpeg.org/download.html).

Pour utiliser [`burn_subtitles`](#incruster-des-sous-titres), le build ffmpeg doit inclure
`libass`. Vérifiez avec `ffmpeg -filters | grep subtitles` ; si absent sur
macOS, essayez `brew uninstall ffmpeg && brew install ffmpeg --HEAD`
(installez `brew` grâce à [brew.sh](https://brew.sh/)).

## Sonder & valider

```python
if vh.is_valid_video_file("clip.mp4"):
    info = vh.video_dimensions("clip.mp4")
    print(info)
    # {'width': 1920, 'height': 1080, 'duration': 12.34,
    #  'frame_rate': 30.0, 'has_sound': True}

duration_seconds = vh.video_duration("clip.mp4")
```

`is_valid_video_file` rejette les faux fichiers `.mp4` (sans flux vidéo)
**et** les vidéos valides portant une extension non vidéo.

`video_dimensions` accepte aussi une URL à la place d'un chemin local,
avec un dictionnaire `http_headers` optionnel transmis à ffprobe : utile
pour un contenu résolu par yt-dlp (YouTube en direct, réservé aux
abonnés ou soumis à vérification d'âge) qui exige des en-têtes
spécifiques pour être lisible.

## Convertir & redimensionner

`video_converter` ré-encode une vidéo avec des changements optionnels de
fréquence d'échantillonnage, de fps et de dimensions. Comportement par
défaut sur le conteneur : les entrées de même conteneur sont copiées en
flux ; les entrées inter-conteneurs sont transcodées en H.264 / AAC.

```python
# Retirer le son + réduire la résolution + diviser le fps par deux.
vh.video_converter(
    "in.mp4",
    "out.mp4",
    frame_rate=15,
    width=640,
    height=360,
    without_sound=True,
)
```

Ne passez que `width` ou que `height` pour préserver le ratio d'aspect.

## Accès aux frames

### Parcourir les frames

`extract_frames` est un générateur. Choisissez la plage par index OU par
temps (secondes) ; la densité d'échantillonnage se règle via `frame_step`
(un frame sur N) ou `frame_interval` (secondes entre deux frames). Tous
les backends produisent des tableaux BGR uint8 de forme `(H, W, 3)`, la
convention OpenCV.

```python
for frame in vh.extract_frames(
    "clip.mp4",
    start_instant=5.0,
    end_instant=10.0,
    frame_interval=0.5,   # un frame toutes les 0,5 s
):
    pass
```

### Accès épars / aléatoire

Besoin de quelques frames à des instants précis ? Passez `frame_indices`
ou `frame_times` plutôt qu'une plage : le répartiteur route vers PyAV
(seek par keyframe) et bascule sur VidGear (tout décoder puis filtrer)
si PyAV n'est pas installé.

```python
frames = list(vh.extract_frames("clip.mp4", frame_times=[1.5, 12.0, 47.0]))
frames = list(vh.extract_frames("clip.mp4", frame_indices=[0, 150, 900]))
```

Pour de longues vidéos avec quelques prélèvements épars, c'est
**nettement** plus rapide que l'API par plage : PyAV fait un seek par
keyframe au lieu de tout décoder depuis t=0.

### Choisir un backend

| Backend | Idéal pour | Notes |
|---|---|---|
| `vidgear` | Séquentiel complet ≤ 720p, seul chemin pour `stabilize=True` | OpenCV + thread producteur. Décode depuis t=0 ; paie une taxe sur les lectures par fenêtre / éparses. |
| `pyav` | Séquentiel par fenêtre, accès épars, tout `destination="torch"` + GPU | Liaisons directes libav. Overhead Python le plus bas, prend en charge `hwaccel`. |
| `ffmpeg-pipe` | Séquentiel quand PyAV n'est pas installé | Sous-processus + pipe bgr24 brut. Honore `hwaccel`. Pas d'accès épars. ~10-20× plus lent que PyAV, à garder seulement en repli. |

Un backend decord a été prototypé pendant le développement de la v1.4
puis abandonné : voir [`SPEED_ANALYSIS.md`](SPEED_ANALYSIS.md) pour les
chiffres (PyAV a battu decord d'environ 30 % sur son propre terrain de
prédilection dans notre banc d'essai).

```python
# Laisser le répartiteur décider (par défaut).
frames = list(vh.extract_frames("clip.mp4", start_instant=0, end_instant=2))

# Forcer un backend précis (utile pour le benchmarking ou le débogage).
frames = list(vh.extract_frames("clip.mp4", start_instant=0, end_instant=2,
                                backend="pyav"))

# La stabilisation force toujours VidGear :
frames = list(vh.extract_frames("clip.mp4", stabilize=True))
```

### Accélération matérielle

Par défaut `hwaccel=None` (décodage logiciel). Activez-la via
`hwaccel="auto"` ou une valeur explicite (`"videotoolbox"`, `"cuda"`,
`"qsv"`). `"auto"` se résout en :

- macOS → `videotoolbox` (le moteur média d'Apple : rapide, très basse
  consommation, excellent sur Apple Silicon pour H.264 / HEVC / VP9 ;
  M3+ ajoute AV1).
- Linux + NVIDIA → `cuda` (NVDEC).
- Linux + iGPU Intel → `qsv` (QuickSync).
- Sinon → décodage logiciel.

```python
# Activer le décodeur matériel adapté à la plateforme.
frames = list(vh.extract_frames("clip.mp4", hwaccel="auto"))

# Forcer un accélérateur précis.
frames = list(vh.extract_frames("clip.mp4", hwaccel="videotoolbox"))
```

`hwaccel` est ignoré par `vidgear` (OpenCV ne l'expose pas proprement).

**Note honnête sur la performance** (voir [SPEED_ANALYSIS.md](SPEED_ANALYSIS.md)) :
hwaccel décharge **effectivement** le décodage vers le moteur média : le
ratio CPU/temps réel passe d'environ 4× à environ 0,8×, le CPU reste
surtout inactif. **Mais** le temps réel est 2 à 3× *pire* pour
`destination="numpy"`, car les frames doivent quand même faire un
aller-retour GPU→CPU puis un swscale pour arriver en tableaux numpy BGR.
Avec `destination="numpy"`, hwaccel apporte donc un gain de **puissance,
de parallélisme**, pas un gain de latence : utile pour des traitements
par lots sur batterie ou pour libérer le CPU pour un traitement en aval.
Pour `destination="torch"` avec un device GPU en revanche, le répartiteur
active automatiquement hwaccel : le transfert hôte→device reste
incontournable, mais il est groupé, ce qui rend le déchargement rentable.

### En-têtes HTTP (URL protégées par authentification)

Certaines sources exigent un `User-Agent` / `Referer` / `Cookie` /
`Authorization` précis pour se lire, typiquement les flux YouTube live
résolus par yt-dlp, le contenu réservé aux membres / à âge limité, les
vidéos privées Vimeo, les flux Twitch. Passez-les via `http_headers` :

```python
# En-têtes obtenus depuis youtube-helper (ou construits à la main)
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.youtube.com/",
}

for frame in vh.extract_frames(
    "https://rr5---sn-googlevideo.com/videoplayback?...",
    http_headers=headers,
    backend="pyav",        # ou "ffmpeg-pipe" ; vidgear avertit + ignore
):
    process(frame)
```

Le backend VidGear journalise un avertissement et ignore `http_headers`
— OpenCV ne les expose pas proprement. Utilisez `backend="pyav"`
(préféré) ou `"ffmpeg-pipe"` pour les URL protégées par authentification.

### Taille de sortie exacte avec padding préservant le ratio

Pour les pipelines ML qui ont besoin d'une forme d'entrée fixe, réglez
`output_width` + `output_height`. Le frame est **redimensionné en
préservant le ratio** puis **complété par padding** jusqu'à la taille
demandée exacte avec `pad_color` :

```python
# Source 1920×1080 → carré 224×224 avec bandes noires (letterbox)
for frame in vh.extract_frames(
    "clip.mp4",
    output_width=224, output_height=224, pad_color="black",
):
    # frame.shape == (224, 224, 3) ; la source en 16:9 est centrée
    # horizontalement avec des bandes noires en haut et en bas (letterbox).
    model_input = frame
```

| `output_width` | `output_height` | Effet |
|---|---|---|
| défini | défini | Redimensionne + complète avec `pad_color` jusqu'à `(W, H)` exact |
| défini | Aucun | Redimensionne à cette largeur, préserve le ratio, **sans padding** (hauteur dérivée) |
| Aucun | défini | Redimensionne à cette hauteur, préserve le ratio, **sans padding** |
| Aucun | Aucun | Dimensions natives (par défaut) |

`pad_color` accepte `"black"` (par défaut), `"white"`, `"red"`, `"green"`, `"blue"`, `"yellow"`, `"cyan"`, `"magenta"`, `"gray"` / `"grey"`, ou un hex `"#RRGGBB"`. `"transparent"` n'est pas implémenté : il lève une `ValueError`, une sortie à 4 canaux serait nécessaire.

Composable avec tout le reste : destinations, hwaccel, accès épars :

```python
# Tenseurs torch carrés sur GPU Apple Silicon, par lots
for batch in vh.extract_frames(
    "clip.mp4",
    output_width=224, output_height=224, pad_color="black",
    destination="torch", device="mps", batch_size=32, layout="image",
):
    # batch.shape == (32, 3, 224, 224), NCHW RGB uint8 sur MPS
    logits = model(batch)
```

### Destination : numpy, torch ou PIL

`extract_frames` respecte l'espace colorimétrique et l'ordre des axes
**conventionnels** du framework de destination :

| Destination  | Espace colorimétrique | Forme par frame | Forme par lot (`batch_size=N`)                    |
|---|---|---|---|
| `"numpy"` (par défaut, OpenCV) | **BGR** uint8 | `(H, W, 3)` HWC | `(N, H, W, 3)` NHWC (`layout="image"`) **ou** THWC (`layout="video"`), même mémoire |
| `"torch"` (PyTorch)         | **RGB** uint8 | `(3, H, W)` CHW | `(N, 3, H, W)` NCHW (`layout="image"`) **ou** `(3, N, H, W)` CTHW (`layout="video"`) |
| `"pil"` (Pillow)            | **RGB**       | `PIL.Image`, `size=(W, H)` | non pris en charge (Pillow n'a pas de type par lots) |

Légende : N = taille du lot, T = temps (= N), C = canaux (= 3), H = hauteur, W = largeur.

Notes :
- Pour numpy, le choix de `layout` est **purement sémantique** (NHWC et
  THWC partagent la même disposition mémoire). Pour torch c'est une
  vraie permutation : NCHW et CTHW diffèrent dans l'ordre des axes.
- `image.size` de PIL est `(W, H)`, l'inverse du `(H, W)` de numpy/torch.
- Toutes les destinations non-numpy sont des **imports paresseux** :
  video-helper lui-même ne dépend ni de torch ni de Pillow.

```python
# Par défaut : numpy, BGR, canaux en dernier (style OpenCV).
for frame in vh.extract_frames("clip.mp4", start_instant=10, end_instant=20):
    # frame.shape == (H, W, 3), BGR uint8
    ...

# Torch CHW RGB sur GPU Apple Silicon, par frame.
import torch
for frame in vh.extract_frames("clip.mp4", destination="torch", device="mps"):
    # frame.shape == (3, H, W), RGB uint8, sur MPS
    ...

# Torch NCHW RGB : lot typique pour un modèle image.
for batch in vh.extract_frames(
    "clip.mp4",
    destination="torch", device="mps", batch_size=32, layout="image",
):
    # batch.shape == (N, 3, H, W) ; un transfert hôte→device par lot
    embeddings = image_model(batch)

# Torch CTHW RGB : clip typique pour un CNN 3D / modèle vidéo.
for clip in vh.extract_frames(
    "clip.mp4",
    destination="torch", device="mps", batch_size=16, layout="video",
):
    # clip.shape == (3, T, H, W) ; T == 16 pour tous les clips sauf le dernier
    embedding = video_model(clip)

# PIL.Image par frame : pour du code qui utilise les filtres / dessin / collage Pillow.
for im in vh.extract_frames("clip.mp4", destination="pil"):
    # im.mode == "RGB", im.size == (W, H)
    im.filter(...)
```

`device="auto"` pour torch se résout dans l'ordre `cuda` → `mps` → `cpu`.

**Note honnête sur la performance :** au moment de la v1.4.1, le chemin
torch matérialise chaque frame en numpy avant de l'empiler et de
l'envoyer au device. C'est un aller-retour par lot, pas un zéro-copie.
Une future extension C++ (prévue pour la v1.5+) permettra à
VideoToolbox / NVDEC de remettre les frames directement à torch sur le
device, sans passage par numpy ; voir `SPEED_ANALYSIS.md` pour les
dernières mesures. Le chemin par lots actuel reste déjà un gain de
5-20× par rapport à envelopper chaque frame à la main dans
`torch.from_numpy(...).to(device)`.

### Écrire des frames vers une vidéo

`dump_frames` fait l'inverse : une liste de frames → un fichier vidéo.

```python
import numpy as np
frames = [np.zeros((72, 128, 3), dtype=np.uint8) for _ in range(30)]
vh.dump_frames(frames, "buffer.mp4", fps=15)
```

## Découpe temporelle

`extract_video_chunk(input, start_s, end_s, output)` découpe une tranche
`[start, end]`. Des bornes hors plage lèvent une `AssertionError`. Le
conteneur de sortie est dicté par l'extension du fichier de sortie.
Passez `copy=True` pour copier le flux au lieu de ré-encoder : rapide et
sans perte, mais l'exactitude à la frame près exige que chaque frame de
l'entrée soit déjà une image clé.

```python
vh.extract_video_chunk("podcast.mp4", 60.0, 75.0, "highlight.mp4")

# Copie de flux : rapide, sans ré-encodage, exige des bornes alignées sur les images clés.
vh.extract_video_chunk("podcast.mp4", 60.0, 75.0, "highlight.mp4", copy=True)
```

## Primitives de pipeline

### Vidéo noire

```python
vh.black_video(0.5, 1920, 1080, "buffer.mp4", frame_rate=30)
```

Utile comme respiration entre deux visuels ou comme substitut à un
asset manquant.

### Boucle d'image

Boucler une image fixe en vidéo silencieuse. Passez `width` et `height`
pour un letterboxing préservant le ratio (padding noir).

```python
vh.image_loop_to_video(
    "title.png", 3.0, "title.mp4",
    frame_rate=30, width=1920, height=1080,
)
```

### Concaténer

Concaténation bout à bout via le démultiplexeur `concat` de ffmpeg (le
seul chemin sûr pour des clips à codecs / fréquences d'images
différents).

```python
vh.concat_videos(
    ["intro.mp4", "body.mp4", "outro.mp4"],
    "final.mp4",
    reencode=True,        # par défaut ; ne mettre False que si toutes les entrées sont des conteneurs bit-identiques
    frame_rate=30,
)
```

### Incruster une image

Incruster un PNG (alpha pris en charge). `x` / `y` acceptent des entiers
simples OU des expressions ffmpeg pour un mouvement variable dans le
temps.

```python
vh.overlay_image(
    "clip.mp4", "cursor.png", "out.mp4",
    x="if(lt(t,2),100,400)",   # se déplace à t=2s
    y="200",
    scale_width=24,
)
```

### Extraire / muxer l'audio

```python
# Extraire l'audio d'une vidéo.
vh.extract_audio_track("interview.mp4", "interview.wav")
vh.extract_audio_track("interview.mp4", "interview.mp3",
                       encoding="libmp3lame", sample_rate=22050)

# Remplacer la piste audio d'une vidéo par un fichier séparé.
vh.mux_audio_video("silent.mp4", "voice.wav", "final.mp4")
```

Le flux vidéo est copié (sans ré-encodage), rapide et sans perte côté
vidéo.

### Incruster des sous-titres

Incruster les sous-titres de façon permanente dans les frames de la
vidéo. Accepte `.srt`, `.vtt`, `.ass`, `.ssa`. Nécessite ffmpeg avec
`libass`.

```python
# SRT simple, style par défaut.
vh.burn_subtitles("clip.mp4", "subs.srt", "captioned.mp4")

# WebVTT coloré (les classes de cue portent leurs propres couleurs).
vh.burn_subtitles("clip.mp4", "subs.vtt", "captioned.mp4")

# Forcer une police + une taille par-dessus n'importe quel format source.
vh.burn_subtitles(
    "clip.mp4", "subs.vtt", "captioned.mp4",
    force_style="FontName=Helvetica,FontSize=28,Outline=2",
)
```

## Outils de sous-titrage

### SRT → VTT + CSS

`srt2vtt` fait remonter les balises SRT `<font color="#RRGGBB">…</font>`
en classes de cue WebVTT `<c.rrggbb>…</c>` et écrit un fichier CSS
compagnon avec une règle `::cue(.rrggbb)` par couleur.

```python
vh.srt2vtt("subs.srt")                       # → subs.vtt + subs.css
vh.srt2vtt("subs.srt", "out.vtt", "out.css") # chemins explicites
```

### Couleurs uniques

`extract_unique_colors` retourne l'ensemble des couleurs hexadécimales
trouvées dans les balises `<font color>` d'un SRT. Utile pour
prévisualiser la palette avant une conversion.

```python
print(vh.extract_unique_colors("subs.srt"))
# {'#FF0000', '#00FF00', '#0000FF'}
```
