import os
import sys
import time
from configparser import ConfigParser
from dataclasses import fields, asdict
from pathlib import Path
from raw_hid import send_raw_report, REQUEST_IDS, list_qmk_devices
from setup import Matches, ICONS, SysTrayIcon, active_window_process_name, WE_ARE_NOT_FRIENDS, list_all_processes


class AutoLayers:
    selected_device = None

    def __init__(self):
        self.vid = -1
        self.pid = -1
        self.name = "NONE"
        self.matches = Matches()
        self.pause = False
        self.quit = False
        self.reboot = False
        self.devices = list_qmk_devices()
        self.icon_change_skip = False
        self.block_list = WE_ARE_NOT_FRIENDS
        self.block_if_active = set()

        # systray
        self.pause_resume_option = ("Pause/Resume", ICONS.pause_resume, self.pause_resume)
        self.grab_option = ("Grab", ICONS.grab, self.grab)
        self.remove_option = ("Remove", ICONS.remove, self.remove)
        if len(self.devices) > 0:
            self.devices_option_sub = list()
            for device in self.devices:
                name = device["name"]
                icon = ICONS.device if not name == AutoLayers.selected_device else ICONS.running
                self.create_method(name)
                self.devices_option_sub.append((name, icon, getattr(self, name)))
            self.devices_option = ("Devices", ICONS.device, self.devices_option_sub)
            self.menu_options = (self.pause_resume_option, self.grab_option, self.remove_option, self.devices_option)
        else:
            self.menu_options = (self.pause_resume_option, self.grab_option, self.remove_option)

        self.systray = SysTrayIcon(
            icon=ICONS.running,
            hover_text="Auto Layers",
            menu_options=self.menu_options,
            on_quit=self.on_quit_callback,
            default_menu_index=0,
        )

        # try to load config.ini
        self.config = ConfigParser()
        self.load_config(self.name)

    def create_method(self, device_name):
        def method(_systray):
            self.load_config(device_name)

        method.__name__ = device_name
        setattr(self, method.__name__, method)

    def load_config(self, device_name):
        self.config.read(Path(CONFIG_FOLDER, "config.ini"))
        try:
            if self.config.has_option("general", "block_list"):
                self.block_list = self.block_list.union(eval(self.config["general"]["block_list"]))

            if self.config.has_option("general", "block_if_active"):
                self.block_if_active = eval(self.config["general"]["block_if_active"])

            self.name = device_name
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

        self.pause_resume(force="pause") if self.name == "NONE" else self.pause_resume(force="resume")
        print(self.name, self.vid, self.pid)

        if not AutoLayers.selected_device == self.name:
            AutoLayers.selected_device = self.name
            self.reboot = True

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
            self.config.write(configfile)
        print("config.ini saved")

    def remove(self, _systray):
        time.sleep(4)
        active_window = active_window_process_name()
        for _field in fields(self.matches):
            getattr(self.matches, _field.name)["apps"].discard(active_window)
        print(active_window, "removed")
        self.save_config()
        self.icon_update(seconds=2, icon=ICONS.remove)

    def grab(self, _systray):
        current_state = self.pause
        self.pause = True
        time.sleep(4)
        current_layer = send_raw_report(REQUEST_IDS.id_current_layer, self.vid, self.pid)
        active_window = active_window_process_name()
        if active_window in self.block_list | self.block_if_active:
            self.pause = False
            return
        if not current_layer == "0" and not current_layer is None:
            for _field in fields(self.matches):
                getattr(self.matches, _field.name)["apps"].discard(active_window)
            getattr(self.matches, f"layer_{current_layer}")["apps"].add(active_window)
            print(getattr(self.matches, f"layer_{current_layer}"))
            self.save_config()
            self.icon_update(seconds=2, icon=ICONS.grab)
        self.pause = current_state
        self.icon_update()

    def pause_resume(self, *_args, force=None):
        if not force:
            self.pause = not self.pause
        else:
            self.pause = True if force == "pause" else False

        if self.name == "NONE":
            self.pause = True

        self.icon_update()

    def icon_update(self, seconds=None, icon=None):
        if self.icon_change_skip:
            return
        if seconds and icon:
            self.systray.update(icon=icon)
            self.icon_change_skip = True
            time.sleep(seconds)
            self.icon_change_skip = False
        if self.pause:
            self.systray.update(icon=ICONS.paused)
        else:
            self.systray.update(icon=ICONS.running)

    def on_quit_callback(self, _systray):
        if not self.quit:  # self.systray._destroy fires 2 times on reboot
            self.save_config()
        self.quit = True

    def layer_change(self):
        current_layer = send_raw_report(REQUEST_IDS.id_current_layer, self.vid, self.pid)
        if current_layer is None:
            return
        active_window = active_window_process_name()
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

    def run(self):
        self.systray.start()
        timer = time.monotonic()
        while not self.quit:
            time.sleep(0.5)
            if self.reboot:
                self.systray.shutdown()
                return True
            if (
                any(app in self.block_list for app in list_all_processes())
                or active_window_process_name() in self.block_if_active
            ):
                self.systray.update(icon=ICONS.blocked)
                continue
            if active_window_process_name() is None:
                print("no active window")
                continue
            if not self.pause:
                self.layer_change()
            self.icon_update()
            if int(time.monotonic() - timer) <= 5:
                continue
            timer = time.monotonic()
            if not self.devices == list_qmk_devices():
                print("devices changed")
                self.reboot = True
        # return to default layer on quit
        send_raw_report(REQUEST_IDS.id_layer_0, self.vid, self.pid)
        return False


if __name__ == "__main__":
    # this is needed to find icons after using pyinstaller and not saving config.ini in temp
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        os.chdir(sys._MEIPASS)
        CONFIG_FOLDER = os.path.dirname(sys.executable)
    else:
        CONFIG_FOLDER = "."

    while True:
        auto_layers = AutoLayers()
        if not auto_layers.run():
            break
