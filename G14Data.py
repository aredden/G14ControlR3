from threading import Thread
from G14RunCommands import RunCommands
from G14Utils import (
    get_app_path,
    get_active_plan_map,
    get_windows_plans,
    get_windows_theme,
    get_power_plans,
    get_windows_plan_map,
)
import sys
import os
import yaml
import time

from win10toast import ToastNotifier

toaster = ToastNotifier()


def load_config(
    G14dir,
):  # Small function to load the config and return it after parsing
    config_loc = ""
    # Sets the path accordingly whether it is a python script or a frozen .exe
    if getattr(sys, "frozen", False):
        # Set absolute path for config.yaml
        config_loc = os.path.join(str(G14dir), "config.yml")
    elif __file__:
        # Set absolute path for config.yaml
        config_loc = os.path.join(str(G14dir), "data/config.yml")

    with open(config_loc, "r") as config_file:
        return yaml.load(config_file, Loader=yaml.FullLoader)


def notify(message, toast_time=5, wait=0):
    Thread(target=do_notify, args=(message, toast_time, wait), daemon=True).start()


def do_notify(message, toast_time, wait):
    if wait > 0:
        time.sleep(wait)
    toaster.show_toast(
        "G14ControlR3",
        msg=message,
        icon_path="res/icon.ico",
        duration=toast_time,
        threaded=True,
    )


class G14_Data:
    def __init__(self):
        self.G14dir = get_app_path()
        self.config = load_config(self.G14dir)
        self.theme = get_windows_theme()
        self.windows_plans = get_windows_plans()
        self.dpp_GUID, self.app_GUID = get_power_plans(self.config)
        self.windows_plan_map = get_windows_plan_map(self.windows_plans)
        self.default_starting_plan = self.config["default_starting_plan"]
        self.default_power_plan = self.config["default_power_plan"]
        self.active_plan_map = get_active_plan_map(
            self.windows_plans, self.default_power_plan
        )
        self.default_ac_plan = self.config["default_ac_plan"]
        self.default_dc_plan = self.config["default_dc_plan"]
        self.power_switch_enabled = self.config["power_switch_enabled"]
        self.default_gaming_plan = self.config["default_gaming_plan"]
        self.default_gaming_plan_games = self.config["default_gaming_plan_games"]
        self.auto_power_switch = self.power_switch_enabled
        self.rog_key = self.config["rog_key"]
        self.current_plan = self.default_starting_plan
        self.current_windows_plan = self.default_power_plan
        self.main_cmds = RunCommands(
            self.config,
            self.G14dir,
            self.app_GUID,
            self.dpp_GUID,
            notify,
            self.windows_plans,
            self.active_plan_map,
        )
        self.registry_key_loc = r"Software\Microsoft\Windows\CurrentVersion\Run"

        self.run_gaming_thread = None
        self.run_power_thread = None
        self.power_thread = None
        self.gaming_thread = None

    def update_win_plan(self, new_win_plan_name):
        mp = self.active_plan_map
        self.active_plan_map = {
            key: (new_win_plan_name == key) for key, val in mp.items()
        }
