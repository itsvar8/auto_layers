import os
import sys
import time
from configparser import ConfigParser
from dataclasses import fields, asdict
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, QThreadPool
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from raw_hid import send_raw_report, REQUEST_IDS, list_qmk_devices
from setup import Matches, Icons, active_window_process_name, WE_ARE_NOT_FRIENDS, list_all_processes, States


class WorkerSignals(QObject):
    finished = Signal()
    update_devices = Signal()
    icon_update = Signal()
    layer_change = Signal()
    block_check = Signal()


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()

        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        self.kwargs["update_devices_signal"] = self.signals.update_devices
        self.kwargs["icon_update_signal"] = self.signals.icon_update
        self.kwargs["layer_change_signal"] = self.signals.layer_change
        self.kwargs["block_check_signal"] = self.signals.block_check

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception as e:
            print(e)
        finally:
            self.signals.finished.emit()


class AutoLayers:
    def __init__(self, q_app):
        self.app = q_app
        self.threadpool = QThreadPool()
        self.vid = -1
        self.pid = -1
        self.name = "NONE"
        self.matches = Matches()
        self.devices = list_qmk_devices()
        self.block_list = WE_ARE_NOT_FRIENDS
        self.block_if_active = set()
        self.state = States.RUNNING
        self.state_before_block = self.state

        # create the tray
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon(Icons.RUNNING))
        self.tray.activated.connect(self.tray_activated)
        self.tray.setVisible(True)

        # create the menu
        self.menu = QMenu()

        # menu options
        self.pause_resume_action = QAction(QIcon(Icons.PAUSE_RESUME), "Pause/Resume")
        self.pause_resume_action.triggered.connect(self.pause_resume)

        self.grab_action = QAction(QIcon(Icons.GRAB), "Grab")
        self.grab_action.triggered.connect(self.grab)

        self.remove_action = QAction(QIcon(Icons.REMOVE), "Remove")
        self.remove_action.triggered.connect(self.remove)

        self.quit_action = QAction(QIcon(Icons.QUIT), "Quit")
        self.quit_action.triggered.connect(self.quit)

        self.default_menu_actions = [
            self.pause_resume_action,
            self.grab_action,
            self.remove_action,
            self.quit_action,
        ]
        self.menu.addActions(self.default_menu_actions)

        self.devices_menu = QMenu(parent=self.menu)
        self.devices_menu.setTitle("Devices")
        self.devices_menu.setIcon(QIcon(Icons.DEVICE))

        self.device_action = None

        self.no_devices_action = QAction("No devices")
        self.no_devices_action.setDisabled(True)
        self.devices_menu.addAction(self.no_devices_action)

        self.menu.insertMenu(self.quit_action, self.devices_menu)

        # Add the menu to the tray
        self.tray.setContextMenu(self.menu)

        self.update_devices()

        # try to load config.ini
        self.config = ConfigParser()
        self.load_config()

        self.run()

    def quit(self):
        self.save_config()
        self.state = States.QUITTING

    def tray_activated(self, reason):
        if self.state == States.BLOCKED:
            return
        if reason == QSystemTrayIcon.DoubleClick:  # noqa
            self.pause_resume()

    def change_device(self, _checked, device_name):
        self.name = device_name
        self.load_config()

    def update_devices(self):
        self.devices = list_qmk_devices()

        self.no_devices_action.setVisible(True)  # empty a menu while open crashes

        for action in [a for a in self.devices_menu.actions() if not a.text() == "No devices"]:
            self.devices_menu.removeAction(action)

        if len(self.devices) == 0:
            return

        for device in self.devices:
            name = device["name"]
            self.device_action = QAction(name, parent=self.devices_menu)
            self.device_action.triggered.connect(lambda checked, n=name: self.change_device(checked, n))
            self.devices_menu.addAction(self.device_action)

        self.no_devices_action.setVisible(False)

    def load_config(self):
        self.config.read(Path(CONFIG_FOLDER, "config.ini"))
        try:
            if self.config.has_option("general", "block_list"):
                self.block_list = self.block_list.union(eval(self.config["general"]["block_list"]))

            if self.config.has_option("general", "block_if_active"):
                self.block_if_active = eval(self.config["general"]["block_if_active"])

            if self.config.has_option("general", "last_device") and self.name == "NONE":
                self.name = self.config["general"]["last_device"]

            if self.name not in [device["name"] for device in self.devices]:
                self.name = "NONE"

            if not self.name == "NONE":
                self.vid = [device for device in self.devices if device["name"] == self.name][0]["vid"]
                self.pid = [device for device in self.devices if device["name"] == self.name][0]["pid"]

            if self.config.has_section(self.name):
                for option in [opt for opt in self.config.options(self.name) if opt.startswith("layer")]:
                    getattr(self.matches, option)["apps"] = eval(self.config.get(self.name, option))
                    getattr(self.matches, option)["apps"].discard("comma_separated.exe")
            else:
                self.matches = Matches()

        except Exception as e:
            print(f"Bad config.ini, {e = }, {self.name = }, {self.vid = }, {self.pid = }")
            sys.exit()

        self.pause_resume(force=States.PAUSED) if self.name == "NONE" else self.pause_resume(force=States.RUNNING)
        print(self.name, self.vid, self.pid)

    def save_config(self):
        self.config.read_dict(asdict(self.matches))
        self.config["general"] = {
            "last_device": self.name,
            "block_list": self.block_list,
            "block_if_active": self.block_if_active if len(self.block_if_active) > 0 else {"comma_separated.exe"},
        }

        self.config[self.name] = {"vid": hex(self.vid), "pid": hex(self.pid)}

        for section in [section for section in self.config.sections() if section.startswith("layer")]:
            if self.config[section]["apps"] == "set()":
                self.config[section]["apps"] = "{'comma_separated.exe'}"
            self.config[self.name][section] = self.config[section]["apps"]
            self.config.remove_section(section)

        # if started with no config.ini and closed without selecting a device
        for section in self.config.sections():
            if section == "last_device" and self.config[section]["name"] == "NONE":
                self.config.remove_section(section)
            if section == "NONE":
                self.config.remove_section(section)

        with open(Path(CONFIG_FOLDER, "config.ini"), "w") as configfile:
            self.config.write(configfile)  # noqa
        print("config.ini saved")

    def icon_update(self):
        match self.state:
            case States.RUNNING:
                icon = Icons.RUNNING
            case States.PAUSED:
                icon = Icons.PAUSED
            case States.BLOCKED:
                icon = Icons.BLOCKED
            case States.GRABBING:
                icon = Icons.GRAB
            case States.REMOVING:
                icon = Icons.REMOVE
            case _:
                icon = Icons.QUIT
        self.tray.setIcon(QIcon(icon))

        for device in self.devices_menu.actions():
            if device.text() == self.name:
                device.setIcon(QIcon(Icons.RUNNING))
            else:
                device.setIcon(QIcon(Icons.DEVICE))

    def pause_resume(self, *_args, force: States | None = None):
        if not force:
            self.state = States.RUNNING if self.state == States.PAUSED else States.PAUSED
        else:
            self.state = force
        self.icon_update()

    def grab(self):
        current_state = self.state
        self.state = States.PAUSED
        time.sleep(4)
        current_layer = send_raw_report(REQUEST_IDS.id_current_layer, self.vid, self.pid)
        active_window = active_window_process_name()
        if active_window in self.block_list.union(self.block_if_active):
            self.state = current_state
            return
        if not current_layer == "0" and not current_layer is None:
            self.state = States.GRABBING
            self.icon_update()
            for _field in fields(self.matches):
                getattr(self.matches, _field.name)["apps"].discard(active_window)
            getattr(self.matches, f"layer_{current_layer}")["apps"].add(active_window)
            print(getattr(self.matches, f"layer_{current_layer}"))
            self.save_config()
            time.sleep(2)
        self.state = current_state

    def remove(self):
        current_state = self.state
        time.sleep(4)
        self.state = States.REMOVING
        self.icon_update()
        active_window = active_window_process_name()
        for _field in fields(self.matches):
            getattr(self.matches, _field.name)["apps"].discard(active_window)
        print(active_window, "removed")
        self.save_config()
        time.sleep(2)
        self.state = current_state

    def layer_change(self):
        current_layer = send_raw_report(REQUEST_IDS.id_current_layer, self.vid, self.pid)
        if current_layer is None:
            return
        active_window = active_window_process_name()
        if active_window_process_name() is None:
            print("no active window")
            return
        found = False
        for f in fields(self.matches):
            if not active_window in getattr(self.matches, f.name)["apps"]:
                continue
            if not f.name.endswith(current_layer):
                send_raw_report(getattr(self.matches, f.name)["request"], self.vid, self.pid)
            found = True
            break
        if not found and not current_layer == "0":
            send_raw_report(REQUEST_IDS.id_layer_0, self.vid, self.pid)

    def block_check(self):
        if self.state == States.QUITTING:
            return

        if not self.state == States.BLOCKED:
            self.state_before_block = self.state

        if (
            any(process in self.block_list for process in list_all_processes())
            or active_window_process_name() in self.block_if_active
        ):
            self.state = States.BLOCKED
            self.pause_resume_action.setDisabled(True)
            self.grab_action.setDisabled(True)
            self.remove_action.setDisabled(True)
        else:
            self.state = self.state_before_block
            self.pause_resume_action.setDisabled(False)
            self.grab_action.setDisabled(False)
            self.remove_action.setDisabled(False)

        self.icon_update()

    @staticmethod
    def loop(
        autolayers,
        update_devices_signal,
        icon_update_signal,
        layer_change_signal,
        block_check_signal,
    ):
        scan_devices_timer = time.monotonic()
        while not autolayers.state == States.QUITTING:
            time.sleep(0.5)

            block_check_signal.emit()
            if autolayers.state == States.BLOCKED:
                continue

            if not autolayers.state in (States.PAUSED, States.BLOCKED):
                layer_change_signal.emit()

            icon_update_signal.emit()

            if int(time.monotonic() - scan_devices_timer) <= 4:
                continue
            scan_devices_timer = time.monotonic()
            if not autolayers.devices == list_qmk_devices():
                print("devices changed")
                update_devices_signal.emit()

        # return to default layer on quit
        send_raw_report(REQUEST_IDS.id_layer_0, autolayers.vid, autolayers.pid)

    def update_devices_signal(self):
        self.update_devices()
        self.load_config()

    def finished_signal(self):
        self.threadpool.waitForDone()
        self.app.quit()

    def run(self):
        worker = Worker(self.loop, self)
        worker.signals.update_devices.connect(self.update_devices_signal)
        worker.signals.icon_update.connect(self.icon_update)
        worker.signals.layer_change.connect(self.layer_change)
        worker.signals.block_check.connect(self.block_check)
        worker.signals.finished.connect(self.finished_signal)
        self.threadpool.start(worker)


if __name__ == "__main__":
    # this is needed to find icons after using pyinstaller and not saving config.ini in temp
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)  # noqa
        CONFIG_FOLDER = os.path.dirname(sys.executable)
    else:
        CONFIG_FOLDER = "."

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    auto_layers = AutoLayers(app)
    app.exec()
