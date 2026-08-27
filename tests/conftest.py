"""
tests/conftest.py — shared pytest fixtures for Caissa headless tests.

Run from the repo root:
    QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/ -v
"""
import os
import sys
import types

import pytest
from tests.helpers import _AutoStub

# ── repo paths ────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(REPO_ROOT, "bin")


def _bootstrap():
    """One-time init: QApplication + Code.configuration + icons + pieces."""
    sys.argv = ["LucasR.py"]
    os.chdir(BIN_DIR)
    if BIN_DIR not in sys.path:
        sys.path.insert(0, BIN_DIR)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    import Code
    from Code.Config import Configuration
    from Code.QT import IconosBase
    from Code.Main import InitApp

    if not hasattr(Code, "configuration") or Code.configuration is None:
        Code.configuration = Configuration.Configuration("")
        Code.configuration.start()
        InitApp.init_app_style(app, Code.configuration)
        IconosBase.icons.reset(Code.configuration.x_style_icons)

        from Code.QT import Piezas
        Code.all_pieces = Piezas.AllPieces()

        from Code.Engines import ListEngineManagers
        Code.list_engine_managers = ListEngineManagers.ListEngineManagers()

        # runSound defaults to None in Code.__init__; that's fine for tests

    return app


_APP = _bootstrap()


@pytest.fixture(scope="session")
def qt_app():
    return _APP


@pytest.fixture(scope="session")
def configuration():
    import Code
    return Code.configuration


@pytest.fixture
def minimal_procesador(qt_app, configuration):
    """
    A minimal stub Procesador suitable for creating game managers.
    Mirrors what Procesador.__init__ exposes that game managers rely on.
    """
    import Code
    from Code.Engines import ListEngineManagers
    from Code import Procesador as ProcMod

    # Real engine manager list (tracks open engine processes so they can be closed)
    Code.list_engine_managers = ListEngineManagers.ListEngineManagers()

    def _noop(*a, **kw):
        pass

    proc = _AutoStub(
        configuration=Code.configuration,
        manager=None,
        manager_tutor=None,
        manager_analyzer=None,
        list_engine_managers=Code.list_engine_managers,
        # Used by create_manager_engine (static) and close_engines
        create_manager_engine=ProcMod.Procesador.create_manager_engine,
        # Tutor / analyzer stubs (Manager.__init__ calls get_manager_*)
        get_manager_tutor=lambda: None,
        get_manager_analyzer=lambda: None,
        # WBase/Manager misc
        siCapturas=False,
        li_opciones_inicio=[],
        # Kibitzers manager stub — some_working() must return False to skip kibitzer logic
        kibitzers_manager=_AutoStub(
            some_working=lambda: False,
            stop=_noop,
            run_new=_noop,
            check=_noop,
            put_game=_noop,
        ),
    )
    yield proc

    # Teardown: close any engine processes that were opened
    try:
        Code.list_engine_managers.close_all()
    except Exception:
        pass
