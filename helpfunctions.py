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


class bcolors:
    PINK = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'

    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    ENDC = '\033[0m'

print(bcolors.PINK + "Hello World!" + bcolors.ENDC)
print(bcolors.OKBLUE + "Hello World!" + bcolors.ENDC)
print(bcolors.OKCYAN + "Hello World!" + bcolors.ENDC)
print(bcolors.OKGREEN + "Hello World!" + bcolors.ENDC)
print(bcolors.WARNING + "Hello World!" + bcolors.ENDC)
print(bcolors.FAIL + "Hello World!" + bcolors.ENDC)
print(bcolors.BOLD + "Hello World!" + bcolors.ENDC)
print(bcolors.UNDERLINE + "Hello World!" + bcolors.ENDC)
