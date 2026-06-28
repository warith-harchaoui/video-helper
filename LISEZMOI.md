# Video Helper

> 🌐 English version: [README.md](README.md)

`Video Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

[🕸️ AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

Video Helper est une bibliothèque Python qui fournit des fonctions utilitaires pour le traitement de fichiers vidéo. Elle inclut le chargement, la conversion, l'extraction de frames ainsi que la manipulation de formats de sous-titres.

# Installation

## Installer le paquet

Nous recommandons l'utilisation d'environnements Python. Consultez ce lien si vous ne savez pas comment faire :

[🥸 Conseils techniques](https://harchaoui.org/warith/4ml/#install)

## Installer `ffmpeg`
Pour utiliser Video Helper, vous devez installer `ffmpeg` :

- Sous macOS 🍎

  Récupérer [brew](https://brew.sh)
  ```bash
  brew install ffmpeg
  ```
- Sous Ubuntu 🐧
  ```bash
  sudo apt install ffmpeg
  ```
- Sous Windows 🪟
  Allez sur le [site FFmpeg](https://ffmpeg.org/download.html) et suivez les instructions. Il faut ajouter manuellement FFmpeg au PATH système.

Pour finir, nous discutons encore entre différents gestionnaires de paquets Python et essayons de supporter autant que possible.

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/video-helper.git@v1.5.1
```

# Utilisation

Pour le catalogue complet d'exemples, voir [📋 EXAMPLES.md](EXAMPLES.md).

Voici un exemple d'utilisation de Video Helper pour charger, convertir et extraire des frames d'une vidéo :

```python
import video_helper as vh

# Vérifier que le fichier vidéo est valide
video_file = "example.mp4"
valid = vh.is_valid_video_file(video_file)  # True ou False

# Récupérer les dimensions et les détails de la vidéo
details = vh.video_dimensions(video_file)
print(details)
# {'width': 1920, 'height': 1080, 'duration': 10.0, 'frame_rate': 30.0, 'has_sound': True}

# Convertir la vidéo vers un autre format
output_video = "video_tests/example_converted.mp4"
vh.video_converter(video_file, output_video,
                   frame_rate=30, width=640, without_sound = True)

# Les images ne seront jamais déformées :
# le ratio d'aspect est préservé même pour width/height arbitraires
# grâce à un padding noir si nécessaire.

# Extraire des frames de la vidéo

start_instant=5  # secondes
# correspond à start_index = start_instant * frame_rate = 5 * 30 = la 150e frame

end_instant=10   # secondes
# correspond à end_index = end_instant * frame_rate = 10 * 30 = la 300e frame

frame_step=5     # prendre une frame sur 5
# soit 1 frame toutes les 5 / frame_rate = 5 / 30 = 0,17 seconde

# Donc on prend 1 frame sur 5 entre la 150e et la 300e.

# Exemple sous forme de liste
frames = list(
    vh.extract_frames(video_file, start_instant=start_instant, end_instant=end_instant, frame_step=frame_step)
)

# Exemple sous forme de boucle for
for frame in vh.extract_frames(
    video_file,
    start_instant=start_instant,
    end_instant=end_instant,
    frame_step=frame_step):
    pass  # Remplacer par votre logique de traitement

# Chaque frame est un tableau numpy de forme (height, width, channels)
# avec des valeurs de pixels entre 0 et 255.
```

Un autre exemple concerne les sous-titres.

Convertir des sous-titres SRT en WebVTT avec préservation des couleurs :

```python
import video_helper as vh

srt_file = "subtitles.srt"
vtt_file = "subtitles.vtt"
css_file = "subtitles.css"

vh.srt2vtt(srt_file, vtt_file, css_file)
```

# Fonctionnalités
- **Validation vidéo** : `is_valid_video_file` — extension + aller-retour `ffmpeg.probe`.
- **Conversion** : `video_converter` — ré-encodage, rééchantillonnage fps, redimensionnement (avec préservation du ratio), suppression de l'audio.
- **Accès aux frames** : `extract_frames` (générateur avec plage temps/index, stabilisation, échantillonnage) et `dump_frames` (liste → vidéo).
- **Coupe temporelle** : `extract_video_chunk`, `video_duration`.
- **Primitives de pipeline** : `black_video`, `image_loop_to_video`, `concat_videos`, `overlay_image`, `extract_audio_track`, `mux_audio_video`, `burn_subtitles`.
- **Sous-titres** : `srt2vtt` (avec CSS compagnon), `extract_unique_colors`.

# Référence d'API

| Fonction | Signature | Description |
| --- | --- | --- |
| `is_valid_video_file` | `(video_file: str) -> bool` | Vrai si le fichier existe, a une extension vidéo reconnue, et que `ffmpeg.probe` y trouve un flux vidéo. |
| `video_dimensions` | `(video_file: str) -> dict` | Retourne `{width, height, duration, frame_rate, has_sound}` via `ffmpeg.probe`. |
| `video_duration` | `(input_video: str) -> float` | Durée en secondes (wrapper léger sur `video_dimensions`). |
| `video_converter` | `(input_video, output_video=None, frame_rate=None, width=None, height=None, without_sound=False)` | Ré-encode avec fps optionnel, redimensionnement (padding noir préservant le ratio quand width et height sont fournis), et suppression de l'audio. |
| `extract_frames` | `(video_path, start_index=None, end_index=None, start_instant=None, end_instant=None, stabilize=False, frame_step=1, frame_interval=None, frame_indices=None, frame_times=None, backend="auto", hwaccel=None, http_headers=None, output_width=None, output_height=None, pad_color="black", destination="numpy", device="cpu", batch_size=None, layout="image") -> Iterator` | Dispatcher multi-backend (VidGear / PyAV / ffmpeg-pipe). `destination` : `"numpy"` (HWC BGR), `"torch"` (CHW RGB), ou `"pil"` (PIL.Image RGB, `size=(W, H)`). `batch_size`+`layout` produisent NHWC/NCHW ou THWC/CTHW. `frame_indices`/`frame_times` = accès clairsemé via le seek par keyframes de PyAV. `http_headers` transmet User-Agent/Referer/Cookie à PyAV / ffmpeg-pipe (nécessaire pour YouTube live résolu par yt-dlp, contenus members-only, contenus age-gated). `output_width`+`output_height` → taille exacte avec letterbox/pillarbox `pad_color` ; l'un des deux seul → mise à l'échelle avec préservation du ratio. `pad_color="transparent"` → v1.6.0. Voir [SPEED_ANALYSIS.md](SPEED_ANALYSIS.md) et [EXAMPLES.md](EXAMPLES.md#frame-access). |
| `dump_frames` | `(frames_list, output_movie, fps=30)` | Écrit une liste de frames BGR (convention OpenCV, identique à ce que `extract_frames` produit) dans un fichier vidéo. |
| `extract_video_chunk` | `(input_video, sample_start, sample_end, output_video)` | Coupe temporelle de `sample_start` à `sample_end` (secondes). |
| `black_video` | `(duration, width, height, output_video, frame_rate=30)` | Génère une vidéo noire silencieuse. Les dimensions impaires sont arrondies au pair inférieur. |
| `image_loop_to_video` | `(image, duration, output_video, frame_rate=30, width=None, height=None)` | Boucle une image fixe en vidéo silencieuse ; letterboxing optionnel. |
| `concat_videos` | `(input_videos, output_video, reencode=True, frame_rate=None)` | Concatène des clips bout-à-bout via le demuxer concat de ffmpeg. |
| `overlay_image` | `(input_video, image, output_video, x="0", y="0", scale_width=None)` | Superpose un PNG/JPG (alpha supporté) ; `x` / `y` acceptent des expressions ffmpeg pour un mouvement temporel. |
| `extract_audio_track` | `(input_video, output_audio, sample_rate=44100, channels=2, encoding="pcm_s16le")` | Extrait le flux audio d'un fichier vidéo. |
| `mux_audio_video` | `(input_video, input_audio, output_video, audio_codec="aac", audio_bitrate="192k", shortest=False)` | Remplace la piste audio d'une vidéo (souvent silencieuse). |
| `burn_subtitles` | `(input_video, subtitles_file, output_video, force_style=None)` | Incruste des `.srt` / `.vtt` / `.ass` / `.ssa` dans les frames (requiert ffmpeg compilé avec libass). |
| `srt2vtt` | `(srt_file_path, vtt_file_path=None, css_file_path=None)` | Convertit SRT → WebVTT en sortant les balises `<font color>` dans un fichier CSS compagnon. |
| `extract_unique_colors` | `(srt_file_path: str) -> Set[str]` | Ensemble des couleurs hexadécimales uniques trouvées dans les balises `<font color>` d'un SRT. |

Par défaut les frames sont des `numpy.ndarray` BGR de forme `(H, W, 3)` avec des valeurs de pixels dans `[0, 255]`. Voir [EXAMPLES.md → Destination](EXAMPLES.md#destination-numpy-torch-or-pil) pour la table complète forme × colorimétrie incluant torch (CHW/NCHW/CTHW RGB) et PIL (RGB, `size=(W, H)`).

# Auteur
 - [Warith HARCHAOUI](https://harchaoui.org/warith)

# Remerciements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
