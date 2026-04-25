# PyInstaller runtime hook: load before the main script.
# eyetrax.models._auto_discover() does Path(__file__).parent.iterdir() to find model
# modules. In a one-file build those .py files live in the PYZ, so the path under
# sys._MEIPASS/eyetrax/models often does not exist and iterdir() raises.
import importlib
import sys

if getattr(sys, "frozen", False):
    from eyetrax import models as _em

    def _auto_discover_frozen() -> None:
        if _em.AVAILABLE_MODELS:
            return
        for _stem in ("elastic_net", "ridge", "svr", "tiny_mlp"):
            importlib.import_module(f"eyetrax.models.{_stem}")

    _em._auto_discover = _auto_discover_frozen
