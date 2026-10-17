"""Validate and embed passive images shared by review and notes renderers."""
import base64
import binascii
from pathlib import Path
from urllib.parse import urlsplit


MAX_IMAGE_BYTES = 20 * 1024 * 1024
DATA_HEADERS = {'data:image/png;base64': 'image/png',
                'data:image/jpeg;base64': 'image/jpeg',
                'data:image/webp;base64': 'image/webp'}


def _mime(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'image/webp'
    raise ValueError('Only PNG/JPEG/WebP image files are supported')


def _local_path(value):
    relative = Path(value)
    if urlsplit(value).scheme or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Images must be local paths beneath the input JSON folder')
    return relative


def validate_reference(value):
    """Validate data bytes, or relative-path syntax when no asset base is available."""
    if not isinstance(value, str) or not value:
        raise ValueError('Images require a nonempty source')
    if not value.startswith('data:'):
        _local_path(value)
        return value
    header, separator, encoded = value.partition(',')
    if not separator or header not in DATA_HEADERS:
        raise ValueError('Embedded images require PNG/JPEG/WebP base64 data URLs')
    if len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise ValueError('Image exceeds 20 MB')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError('Embedded image has invalid base64') from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Image exceeds 20 MB')
    if base64.b64encode(data).decode('ascii') != encoded:
        raise ValueError('Embedded image requires canonical base64')
    if _mime(data) != DATA_HEADERS[header]:
        raise ValueError('Embedded image MIME does not match image bytes')
    return value


def image_data(value, base):
    """Return a checked data URL, retaining support for input-relative image files."""
    checked = validate_reference(value)
    if checked.startswith('data:'):
        return checked
    folder = Path(base).resolve()
    path = (folder / _local_path(checked)).resolve()
    path.relative_to(folder)
    with path.open('rb') as source:
        data = source.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError('Image exceeds 20 MB')
    return 'data:' + _mime(data) + ';base64,' + base64.b64encode(data).decode('ascii')
