"""Outil "image" : lire les métadonnées EXIF d'une photo.

Les appareils photo et smartphones enregistrent dans chaque photo des
informations cachées (EXIF) : modèle de l'appareil, date de prise de vue,
logiciel utilisé et parfois les coordonnées GPS exactes !

Bon à savoir : la plupart des réseaux sociaux (Facebook, Instagram, X...)
suppriment ces métadonnées. On les trouve surtout sur les fichiers originaux,
les sites personnels, les forums ou les pièces jointes.
"""

from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

# Tags EXIF les plus parlants pour une enquête.
INTERESTING_TAGS = [
    "Make", "Model", "LensModel", "Software", "DateTime", "DateTimeOriginal",
    "DateTimeDigitized", "OffsetTimeOriginal", "Artist", "Copyright",
    "ImageDescription", "HostComputer", "BodySerialNumber", "CameraOwnerName",
]


def _dms_to_decimal(dms: tuple, ref: str) -> float:
    """Convertit des coordonnées "degrés, minutes, secondes" en degrés décimaux."""
    degrees, minutes, seconds = (float(x) for x in dms)
    value = degrees + minutes / 60 + seconds / 3600
    return round(-value if ref in ("S", "W") else value, 6)


def _clean(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode(errors="replace").strip("\x00 ")
    if isinstance(value, str):
        return value.strip("\x00 ")
    return str(value)


def image_metadata(path: str) -> dict[str, Any]:
    """Point d'entrée de l'outil : extrait les métadonnées d'une image locale."""
    file = Path(path).expanduser()
    if not file.is_file():
        raise ValueError(f"Fichier introuvable : {file}")

    with Image.open(file) as img:
        result: dict[str, Any] = {
            "fichier": str(file),
            "format": img.format,
            "dimensions": f"{img.width} x {img.height}",
        }
        exif = img.getexif()

        # Les tags principaux sont identifiés par un numéro : on les traduit en nom.
        tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
        # Les dates de prise de vue et l'objectif sont dans un sous-bloc "Exif".
        sub = exif.get_ifd(ExifTags.IFD.Exif)
        tags.update({ExifTags.TAGS.get(k, str(k)): v for k, v in sub.items()})

        found = {name: _clean(tags[name]) for name in INTERESTING_TAGS if name in tags}
        if found:
            result["exif"] = found

        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        if gps:
            gps = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps.items()}
            try:
                lat = _dms_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
                lon = _dms_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                result["gps"] = {"brut": {k: _clean(v) for k, v in gps.items()}}
            else:
                result["gps"] = {
                    "latitude": lat,
                    "longitude": lon,
                    "carte": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}",
                }

    if "exif" not in result and "gps" not in result:
        result["remarque"] = (
            "Aucune métadonnée EXIF : elles ont probablement été supprimées "
            "(réseau social, capture d'écran, logiciel de retouche...)."
        )
    return result
