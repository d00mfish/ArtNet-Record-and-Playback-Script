from gzip import GzipFile
from pathlib import Path
from tempfile import gettempdir


def write_file(data, fname, compress=True):
    if compress:
        f = GzipFile(fname, 'wb')
    else:
        f = open(fname, 'wb')
    try:
        f.write(data)
    finally:
        f.close()
        
def unzip_file(source: Path):
    """Unzips File to tmp location

    Args:
        source (Path): Location of Zip File

    Returns:
       Path: Path to unzipped txt
    """
    tmp_file = Path(gettempdir(), source.stem + ".txt")
    with open(tmp_file, 'wb') as txt:
        zip = GzipFile(source, 'rb')
        txt.write(zip.read())
    return tmp_file