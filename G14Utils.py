import ctypes
import re

from PIL import Image
from pywinusb import hid
import sys
import winreg
import os
import subprocess as sp


# Adds G14Control.exe to the windows registry to start on boot/login
def registry_add(registry_key_loc, G14dir):
    G14exe = "G14Control.exe"
    G14dir = str(G14dir)
    G14fileloc = os.path.join(G14dir, G14exe)
    G14Key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, registry_key_loc, 0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(G14Key, "G14Control", 1, winreg.REG_SZ, G14fileloc)


# Removes G14Control.exe from the windows registry
def registry_remove(registry_key_loc, G14dir):
    G14dir = str(G14dir)
    G14Key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, registry_key_loc, 0, winreg.KEY_ALL_ACCESS
    )
    winreg.DeleteValue(G14Key, "G14Control")


# Checks if G14Control registry entry exists already
def registry_check(registry_key_loc, G14dir):
    G14exe = "G14Control.exe"
    G14dir = str(G14dir)
    G14fileloc = os.path.join(G14dir, G14exe)
    G14Key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key_loc)
    try:
        i = 0
        while 1:
            name, value, enumtype = winreg.EnumValue(G14Key, i)
            if name == "G14Control" and value == G14fileloc:
                return True
            i += 1
    except WindowsError:
        return False


def get_app_path():
    global G14dir
    G14dir = ""
    # Sets the path accordingly whether it is a python script or a frozen .exe
    if getattr(sys, "frozen", False):
        G14dir = os.path.dirname(os.path.realpath(sys.executable))
    elif __file__:
        G14dir = os.path.dirname(os.path.realpath(__file__))
    return G14dir


def startup_checks(data):
    # Only enable auto_power_switch on boot if default power plans are enabled (not set to null):
    if (
        data.default_ac_plan is not None
        and data.default_dc_plan is not None
        and data.config["power_switch_enabled"] is True
    ):
        data.auto_power_switch = True
    else:
        data.auto_power_switch = False
    # Adds registry entry if enabled in config, but not when in debug mode.
    # if not registry entry is already existing,
    # removes registry entry if registry exists but setting is disabled:
    reg_run_enabled = registry_check(data.registry_key_loc, G14dir)

    if (
        data.config["start_on_boot"]
        and not data.config["debug"]
        and not reg_run_enabled
    ):
        registry_add(data.registry_key_loc, G14dir)
    if (
        not data.config["start_on_boot"]
        and not data.config["debug"]
        and reg_run_enabled
    ):
        registry_remove(data.registry_key_loc, data.G14dir)
    return data.auto_power_switch


def change_target_brightness(target_guid, level):
    video = "SUB_VIDEEO"
    brightness_guid = "aded5e82-b909-4619-9949-f5d71dac0bcb"
    setacval = "/setacvalueindex"
    setdcval = "/setdcvalueindex"
    pcfg = "powercfg"
    sp.Popen([pcfg, setacval, target_guid, video, brightness_guid, level])
    sp.Popen([pcfg, setdcval, target_guid, video, brightness_guid, level])
    return


def rog_keyset(config):
    if config["rog_key"] is not None:
        hid_filter = hid.HidDeviceFilter(vendor_id=0x0B05, product_id=0x1866)
        hid_device = hid_filter.get_devices()
        for i in hid_device:
            if str(i).find("col01"):
                device = i
                device.open()
                device.set_raw_data_handler(config, readData)
                return device


def readData(config, data):
    if data[1] == 56:
        os.startfile(config["rog_key"])
    return None


def get_power_plans(config):
    dpp_GUID = ""
    app_GUID = ""
    all_plans = sp.check_output(["powercfg", "/l"])
    for i in str(all_plans).split("\\n"):
        print(i)
        if i.find(config["default_power_plan"]) != -1:
            dpp_GUID = i.split(" ")[3]
        if i.find(config["alt_power_plan"]) != -1:
            app_GUID = i.split(" ")[3]
    return dpp_GUID, app_GUID


def get_windows_plans():
    windows_power_options = re.findall(
        r"([0-9a-f\-]{36}) *\((.*)\) *\*?\n", os.popen("powercfg /l").read()
    )
    return windows_power_options


def get_active_plan_map(windows_plans, current_windows_plan):
    """
    Cannot be run before @get_windows_plans()

    Prepares active windows plans map for icon_app menu *checked* statuses.
    """
    active_plan_map = {x[1]: False for x in windows_plans}
    active_plan_map[current_windows_plan] = True
    return active_plan_map


def get_windows_plan_map(windows_plans):
    windows_plan_map = {}
    windows_plan_map = {x[1]: x[0] for x in windows_plans}
    return windows_plan_map


def is_admin():
    try:
        # Returns true if the user launched the app as admin
        return ctypes.windll.shell32.IsUserAnAdmin()
    except OSError or WindowsError:
        return False


def get_windows_theme():
    # By default, this is the local registry
    key = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    # Let's open the subkey
    sub_key = winreg.OpenKey(
        key, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    )
    # Taskbar (where icon is displayed) uses the 'System' light theme key. Index 0 is the value, index 1 is the type of key
    value = winreg.QueryValueEx(sub_key, "SystemUsesLightTheme")[0]
    return value  # 1 for light theme, 0 for dark theme


def create_icon(config):
    if (
        get_windows_theme() == 0
    ):  # We will create the icon based on current windows theme
        return Image.open(os.path.join(config["temp_dir"], "icon_light.png"))
    else:
        return Image.open(os.path.join(config["temp_dir"], "icon_dark.png"))
