from fractions import Fraction

import pytest
from PIL import ExifTags, Image

from osint_mcp.tools.image import image_metadata


def make_photo(path, with_exif=True):
    img = Image.new("RGB", (64, 48), "blue")
    exif = Image.Exif()
    if with_exif:
        exif[ExifTags.Base.Make] = "Canon"
        exif[ExifTags.Base.Model] = "EOS 2000D"
        # Tour Eiffel : 48°51'29.6"N 2°17'40.2"E
        exif[ExifTags.Base.GPSInfo] = {
            ExifTags.GPS.GPSLatitudeRef: "N",
            ExifTags.GPS.GPSLatitude: (48.0, 51.0, Fraction(296, 10)),
            ExifTags.GPS.GPSLongitudeRef: "E",
            ExifTags.GPS.GPSLongitude: (2.0, 17.0, Fraction(402, 10)),
        }
    img.save(path, "JPEG", exif=exif)


def test_reads_camera_and_gps(tmp_path):
    photo = tmp_path / "photo.jpg"
    make_photo(photo)

    result = image_metadata(str(photo))

    assert result["format"] == "JPEG"
    assert result["dimensions"] == "64 x 48"
    assert result["exif"]["Make"] == "Canon"
    assert result["exif"]["Model"] == "EOS 2000D"
    assert result["gps"]["latitude"] == pytest.approx(48.858222, abs=1e-5)
    assert result["gps"]["longitude"] == pytest.approx(2.294500, abs=1e-5)
    assert "openstreetmap.org" in result["gps"]["carte"]


def test_image_without_exif(tmp_path):
    photo = tmp_path / "capture.jpg"
    make_photo(photo, with_exif=False)
    result = image_metadata(str(photo))
    assert "gps" not in result
    assert "supprimées" in result["remarque"]


def test_missing_file():
    with pytest.raises(ValueError, match="introuvable"):
        image_metadata("/nexiste/pas.jpg")
