from infi.systray import SysTrayIcon as _SysTrayIcon
from infi.systray.win32_adapter import (
    encode_for_locale,
    RegisterWindowMessage,
    WM_DESTROY,
    WM_CLOSE,
    WM_COMMAND,
    WM_USER,
)
import uuid
from dataclasses import dataclass, field, fields
from pathlib import Path
from raw_hid import REQUEST_IDS
import psutil
import ctypes


WE_ARE_NOT_FRIENDS = {"Vial.exe", "VIA.exe"}


def active_window_process_name():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    # print(psutil.Process(pid.value).name() if pid.value else None)
    return psutil.Process(pid.value).name() if pid.value else None


def list_all_processes():
    processes = list()
    try:
        processes = [process.name() for process in psutil.process_iter()]
    except Exception as e:
        print(e)
    return processes


@dataclass(slots=True)
class Matches:
    layer_1: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_2: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_3: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_4: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_5: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_6: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_7: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_8: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)
    layer_9: dict[str, set[str] | str, tuple[int]] = field(default_factory=dict)

    def __post_init__(self):
        for n, _field in enumerate(fields(self), 1):
            getattr(self, _field.name)["apps"] = set()
            getattr(self, _field.name)["request"] = getattr(REQUEST_IDS, f"id_layer_{n}")


# fmt:off
@dataclass(slots=True)
class Icons:
    running:      str = str(Path("icons/auto_layers_running.ico"))
    paused:       str = str(Path("icons/auto_layers_paused.ico"))
    blocked:      str = str(Path("icons/auto_layers_blocked.ico"))
    pause_resume: str = str(Path("icons/auto_layers_pause_resume.ico"))
    grab:         str = str(Path("icons/auto_layers_grab.ico"))
    remove:       str = str(Path("icons/auto_layers_remove.ico"))
    device:       str = str(Path("icons/auto_layers_device.ico"))
    quit:         str = str(Path("icons/auto_layers_quit.ico"))
# fmt:on

ICONS = Icons()


# there is no other option to change quit icon
class SysTrayIcon(_SysTrayIcon):
    def __init__(
        self, icon, hover_text, menu_options=None, on_quit=None, default_menu_index=None, window_class_name=None
    ):

        self._icon = icon
        self._icon_shared = False
        self._hover_text = hover_text
        self._on_quit = on_quit

        menu_options = menu_options or ()
        # here
        menu_options = menu_options + (("Quit", ICONS.quit, SysTrayIcon.QUIT),)
        #
        self._next_action_id = SysTrayIcon.FIRST_ID
        self._menu_actions_by_id = set()
        self._menu_options = self._add_ids_to_menu_options(list(menu_options))
        self._menu_actions_by_id = dict(self._menu_actions_by_id)

        window_class_name = window_class_name or ("SysTrayIconPy-%s" % (str(uuid.uuid4())))

        self._default_menu_index = default_menu_index or 0
        self._window_class_name = encode_for_locale(window_class_name)
        self._message_dict = {
            RegisterWindowMessage("TaskbarCreated"): self._restart,
            WM_DESTROY: self._destroy,
            WM_CLOSE: self._destroy,
            WM_COMMAND: self._command,
            WM_USER + 20: self._notify,
        }
        self._notify_id = None
        self._message_loop_thread = None
        self._hwnd = None
        self._hicon = 0
        self._hinst = None
        self._window_class = None
        self._menu = None
        self._register_class()
