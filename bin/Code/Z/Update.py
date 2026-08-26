import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

import Code
from Code import Util
from Code.Board import Eboard
from Code.QT import QTProgressBars, SelectFiles, QTMessages

platform = "r6_win" if Util.is_windows() else "r6_linux"

WEBUPDATES = f"https://lucaschess.pythonanywhere.com/static/updater/updates_{platform}.txt"
WEBUPDATES_EBOARD_VERSION = f"https://lucaschess.pythonanywhere.com/static/updater/version_eboards_{platform}.txt"
WEBUPDATES_EBOARD_ZIP = f"https://lucaschess.pythonanywhere.com/static/updater/eboards_{platform}.zip"


def _download_with_progress(
    url: str,
    destination: Path,
    progress_bar: QTProgressBars.ProgressBarSimple,
    expected_size: Optional[int] = None,
) -> bool:
    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            if total_size > 0 and expected_size and total_size != expected_size:
                return False

            block_size = 8192
            total_blocks = (total_size + block_size - 1) // block_size if total_size > 0 else 0

            if total_blocks > 0:
                progress_bar.set_total(total_blocks)

            with open(destination, "wb") as out_file:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    progress_bar.inc()
        return True
    except Exception:
        return False


def update_file(titulo: str, urlfichero: str, tam: int) -> bool:
    folder_actual = Path("actual")
    shutil.rmtree(folder_actual, ignore_errors=True)
    Util.create_folder(folder_actual)

    progreso = QTProgressBars.ProgressBarSimple(None, titulo, _("Updating..."), 100).mostrar()

    local_file = folder_actual / urlfichero.split("/")[-1]

    success = _download_with_progress(urlfichero, local_file, progreso, tam)

    is_canceled = progreso.is_canceled()
    progreso.cerrar()

    if is_canceled or not success:
        return False

    if tam != Util.filesize(str(local_file)):
        return False

    with zipfile.ZipFile(local_file, "r") as zp:
        zp.extractall(folder_actual)

    path_act_py = folder_actual / "act.py"
    exec(open(path_act_py).read())

    return True


def update_eboard(main_window):
    version_local = Eboard.version()

    ftxt = Code.configuration.temporary_file("txt")
    ok = Util.urlretrieve(WEBUPDATES_EBOARD_VERSION, ftxt)

    if not ok:
        return

    with open(ftxt, "rt") as f:
        version_remote = f.read().strip()

    if version_local == version_remote:
        return

    um = QTMessages.one_moment_please(main_window, _("Downloading eboards drivers"))

    fzip = Code.configuration.temporary_file("zip")
    ok = Util.urlretrieve(WEBUPDATES_EBOARD_ZIP, fzip)

    um.final()

    if ok:
        with zipfile.ZipFile(fzip) as zfobj:
            for name in zfobj.namelist():
                path_dll = Util.opj(Code.folder_os, "DigitalBoards", name)
                with open(path_dll, "wb") as outfile:
                    outfile.write(zfobj.read(name))

        news_path = Util.opj(Code.folder_os, "DigitalBoards", "news")
        if Path(news_path).exists():
            with open(news_path, "rt", encoding="utf-8") as f:
                news = f.read().strip()
        else:
            news = ""

        QTMessages.message(
            main_window, _("Updated the eboards drivers") + "\n %s: %s\n%s" % (_("Version"), version_remote, news)
        )

    else:
        QTMessages.message_error(main_window, _("It has not been possible to update the eboards drivers"))


def update(main_window):
    # Auto-update disabled in Caissa — this fork diverges from upstream versioning.
    # For releases see https://github.com/JohnnyFoulds/caissa/releases
    return False


def test_update(procesador):
    # Auto-update disabled in Caissa.
    pass


def update_manual(main_window) -> bool:
    config = Code.configuration

    dic = config.read_variables("MANUAL_UPDATE")

    folder = dic.get("FOLDER", config.folder_userdata())

    path_zip = SelectFiles.read_file(main_window, folder, "zip")
    if not path_zip or not Util.exist_file(path_zip):
        return False

    dic["FOLDER"] = str(Path(path_zip).parent)
    config.write_variables("MANUAL_UPDATE", dic)

    folder_actual = Util.opj(Code.folder_root, "bin", "actual")
    shutil.rmtree(folder_actual, ignore_errors=True)
    Util.create_folder(folder_actual)

    local_file = Path(path_zip)

    with zipfile.ZipFile(local_file, "r") as zp:
        zp.extractall(folder_actual)

    path_act_py = Path(folder_actual) / "act.py"

    if path_act_py.exists():
        try:
            result = subprocess.run(
                ["python", str(path_act_py)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                return False
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    return True
