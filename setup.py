from dataclasses import field, fields, make_dataclass
from enum import StrEnum, auto
from pathlib import Path

import psutil
import pywinctl

from raw_hid import REQUEST_IDS

WE_ARE_NOT_FRIENDS = {"Vial.exe", "Vial", "VIA.exe"}


def active_window_process_name():
    try:
        return psutil.Process(pywinctl.getActiveWindow().getPID()).name()
    except Exception as e:
        print(e)
        return None


def list_all_processes():
    processes = list()
    try:
        processes = [process.name() for process in psutil.process_iter()]
    except Exception as e:
        print(e)
    return processes


def _matches_post_init(cls):
    for n, _field in enumerate(fields(cls), 1):
        getattr(cls, _field.name)["apps"] = set()
        getattr(cls, _field.name)["request"] = getattr(REQUEST_IDS, f"id_layer_{n}")


Matches = make_dataclass(
    cls_name="Matches",
    fields=[(f"layer_{i}", dict, field(default_factory=dict)) for i in range(1, 10)],
    namespace={"__post_init__": lambda self: _matches_post_init(self)},
    slots=True,
)


# fmt:off
class Icons(StrEnum):
    RUNNING      = str(Path("icons/auto_layers_running.ico"))
    PAUSED       = str(Path("icons/auto_layers_paused.ico"))
    BLOCKED      = str(Path("icons/auto_layers_blocked.ico"))
    PAUSE_RESUME = str(Path("icons/auto_layers_pause_resume.ico"))
    GRAB         = str(Path("icons/auto_layers_grab.ico"))
    REMOVE       = str(Path("icons/auto_layers_remove.ico"))
    DEVICE       = str(Path("icons/auto_layers_device.ico"))
    QUIT         = str(Path("icons/auto_layers_quit.ico"))


class States(StrEnum):
    RUNNING  = auto()
    PAUSED   = auto()
    BLOCKED  = auto()
    GRABBING = auto()
    REMOVING = auto()
    QUITTING = auto()
# fmt:on
