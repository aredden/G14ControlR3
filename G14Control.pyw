import ctypes
import os
import re
import subprocess
import sys
import threading
import time
import winreg
from threading import Thread
import winreg
import psutil
import pystray
from pystray._base import Icon, Menu, MenuItem
import yaml
from PIL import Image
import resources
from pywinusb import hid
from G14RunCommands import RunCommands
from win10toast import ToastNotifier

# import pickle
# from io import FileIO

toaster = ToastNotifier()

main_cmds: RunCommands

run_gaming_thread = True
run_power_thread = True
power_thread = None
gaming_thread = None
showFlash = False
config_loc: str
current_boost_mode = 0
current_windows_plan = "Balanced"
active_plan_map: dict = {}


def readData(data):
    if data[1] == 56:
        os.startfile(config['rog_key'])
    return None


def get_power_plans():
    global dpp_GUID, app_GUID
    all_plans = subprocess.check_output(["powercfg", "/l"])
    for i in str(all_plans).split('\\n'):
        print(i)
        if i.find(config['default_power_plan']) != -1:
            dpp_GUID = i.split(' ')[3]
        if i.find(config['alt_power_plan']) != -1:
            app_GUID = i.split(' ')[3]


def get_windows_plans():
    global config, active_plan_map, current_windows_plan
    windows_power_options = re.findall(
        r"([0-9a-f\-]{36}) *\((.*)\) *\*?\n", os.popen("powercfg /l").read())
    active_plan_map = {x[1]: False for x in windows_power_options}
    active_plan_map[current_windows_plan] = True
    return windows_power_options


def get_active_plan_map():
    """
    Cannot be run before @get_windows_plans()

    Prepares active windows plans map for icon_app menu *checked* statuses.
    """
    global windows_plans, active_plan_map
    try:
        active_plan_map["Balanced"]
        return active_plan_map
    except Exception:
        active_plan_map = {x[1]: False for x in windows_plans}
        active_plan_map[current_windows_plan] = True
        return active_plan_map


def get_windows_plan_map():
    global windows_plans, windows_plan_map
    windows_plan_map = {x[1]: x[0] for x in windows_plans}
    return windows_plan_map


def get_app_path():
    global G14dir
    G14Dir = ""
    # Sets the path accordingly whether it is a python script or a frozen .exe
    if getattr(sys, 'frozen', False):
        G14dir = os.path.dirname(os.path.realpath(sys.executable))
    elif __file__:
        G14dir = os.path.dirname(os.path.realpath(__file__))
    return G14Dir


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
        key, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
    # Taskbar (where icon is displayed) uses the 'System' light theme key. Index 0 is the value, index 1 is the type of key
    value = winreg.QueryValueEx(sub_key, "SystemUsesLightTheme")[0]
    return value  # 1 for light theme, 0 for dark theme


def create_icon():
    if get_windows_theme() == 0:  # We will create the icon based on current windows theme
        return Image.open(os.path.join(config['temp_dir'], 'icon_light.png'))
    else:
        return Image.open(os.path.join(config['temp_dir'], 'icon_dark.png'))


def activate_powerswitching():
    global auto_power_switch, run_power_thread, run_gaming_thread, power_thread, gaming_thread, config
    auto_power_switch = True
    if power_thread is None:
        power_thread = power_check_thread()
        power_thread.start()
        notify('Power switching has been activated.')
    elif not power_thread.is_alive():
        power_thread = power_check_thread()
        power_thread.start()
        notify('Power switching has been activated.')
    if config['default_gaming_plan'] is not None and config['default_gaming_plan_games'] is not None:
        if gaming_thread is None:
            gaming_thread = gaming_thread_impl('gaming-thread')
            gaming_thread.start()
        elif not gaming_thread.is_alive():
            gaming_thread = gaming_thread_impl('gaming-thread')
            gaming_thread.start()


def deactivate_powerswitching(should_notify=True):
    global auto_power_switch, run_gaming_thread, run_power_thread, power_thread, gaming_thread
    auto_power_switch = False

    if power_thread is not None and power_thread.is_alive():
        power_thread.raise_exception()
    if gaming_thread is not None and gaming_thread.is_alive():
        gaming_thread.raise_exception()
      # Plan change notifies first, so this needs to be on a delay to prevent simultaneous notifications
    if(should_notify):
        notify("Auto power switching has been disabled.", wait=1)


class power_check_thread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self, daemon=True)

    def run(self):
        global auto_power_switch, ac, current_plan, default_ac_plan, default_dc_plan, config
        # Only run while loop on startup if auto_power_switch is On (True)
        if auto_power_switch:
            while run_power_thread:
                # Check to user hasn't disabled auto_power_switch (i.e. by manually switching plans)
                if auto_power_switch:
                    ac = psutil.sensors_battery().power_plugged  # Get the current AC power status
                    # If on AC power, and not on the default_ac_plan, switch to that plan
                    if ac and current_plan != default_ac_plan:
                        for plan in config['plans']:
                            if plan['name'] == default_ac_plan:
                                apply_plan(plan)
                                break
                    # If on DC power, and not on the default_dc_plan, switch to that plan
                    if not ac and current_plan != default_dc_plan:
                        for plan in config['plans']:
                            if plan['name'] == default_dc_plan:
                                apply_plan(plan)
                                break
                time.sleep(10)
        else:
            self.raise_exception()

    def raise_exception(self):
        thread_id = self.ident
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')


class gaming_thread_impl(threading.Thread):

    def __init__(self, name):
        self.name = name
        threading.Thread.__init__(self, daemon=True)

    def run(self):  # Checks if user specified games/programs are running, and sw`itches to user defined plan, then switches back once closed
        global default_gaming_plan_games, run_gaming_thread
        previous_plan = None  # Define the previous plan to switch back to
        if auto_power_switch:
            while run_gaming_thread:  # Continuously check every 10 seconds
                output = os.popen(
                    'wmic process get description, processid').read()
                process = output.split("\n")
                processes = set(i.split(" ")[0] for i in process)
                # List of user defined processes
                targets = set(default_gaming_plan_games)
                if processes & targets:  # Compare 2 lists, if ANY overlap, set game_running to true
                    game_running = True
                else:
                    game_running = False
                # If game is running and not on the desired gaming plan, switch to that plan
                if game_running and current_plan != default_gaming_plan:
                    previous_plan = current_plan
                    for plan in config['plans']:
                        if plan['name'] == default_gaming_plan:
                            apply_plan(plan)
                            notify(plan['name'])
                            break
                # If game is no longer running, and not on previous plan already (if set), then switch back to previous plan
                if not game_running and previous_plan is not None and previous_plan != current_plan:
                    for plan in config['plans']:
                        if plan['name'] == previous_plan:
                            apply_plan(plan)
                            notify(plan['name'])
                            break
                # Check for programs every 10 sec
                time.sleep(config['check_power_every'])

    def raise_exception(self):
        thread_id = self.ident
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')


def notify(message, toast_time=5, wait=0):
    Thread(target=do_notify, args=(
        message, toast_time, wait), daemon=True).start()


def do_notify(message, toast_time, wait):
    global icon_app
    if wait > 0:
        time.sleep(wait)
    toaster.show_toast("G14ControlR3", msg=message,
                       icon_path="res/icon.ico", duration=toast_time, threaded=True)


def get_current():
    global ac, current_plan, current_boost_mode, config, main_cmds
    plan_idx = next(i for i, e in enumerate(
        config['plans']) if e['name'] == current_plan)
    tdp = str(config['plans'][plan_idx]['cpu_tdp'])

    toast_time = config['notification_time']

    boost_type = ["Disabled", "Enabled", "Aggressive",
                  "Efficient Enabled", "Efficient Aggressive"]
    dGPUstate = (["Off", "On"][main_cmds.get_dgpu()])
    batterystate = (["Battery", "AC"][bool(ac)])
    autoswitching = (["Off", "On"][auto_power_switch])
    boost_state = (boost_type[int(main_cmds.get_boost()[2:])])
    refresh_state = (["60Hz", "120Hz"][main_cmds.get_screen()])

    notify(
        "Plan: " + current_plan + "  dGPU: " + dGPUstate + "\n" +
        "Boost: " + boost_state + "  Screen: " + refresh_state + "\n" +
        "Power: " + batterystate + "  Auto Switching: " + autoswitching + "\n" +
        "CPU TDP: " + tdp,
        toast_time
    )  # Let's print the current values


def apply_plan(plan):
    global current_plan, main_cmds, icon_app
    current_plan = plan['name']
    main_cmds.set_windows_and_active_plans(windows_plans, active_plan_map)
    main_cmds.set_atrofac(plan['plan'], plan['cpu_curve'], plan['gpu_curve'])
    main_cmds.set_boost(plan['boost'], False)
    main_cmds.set_dgpu(plan['dgpu_enabled'], False)
    main_cmds.set_screen(plan['screen_hz'], False)
    main_cmds.set_ryzenadj(plan['cpu_tdp'])
    notify("Applied plan " + plan['name'])


def quit_app():
    global device, run_power_thread, run_gaming_thread, power_thread, gaming_thread
    # This will destroy the the tray icon gracefully.
    # with FileIO('./config.DAT', mode='w') as fileio:
    #     pickle.dump(config, fileio)
    #     fileio.close()

    run_power_thread = False
    run_gaming_thread = False
    if power_thread is not None and power_thread.is_alive():
        power_thread.raise_exception()
        print('Power thread was alive, and now is dead.')

    if gaming_thread is not None and gaming_thread.is_alive():
        gaming_thread.raise_exception()
        print('Gaming thread was alive, and now is dead.')
    if device is not None:
        device.close()
    try:
        icon_app.stop()
    except SystemExit:
        print('System Exit')
        sys.exit()


def apply_plan_deactivate_switching(plan):
    global current_plan
    current_plan = plan['name']
    main_cmds.apply_plan(plan)
    deactivate_powerswitching()


def set_windows_plan(plan):
    global active_plan_map, current_windows_plan, windows_plans, config
    if config['debug']:
        print(plan)
    active_plan_map[current_windows_plan] = False
    current_windows_plan = plan[1]
    active_plan_map[current_windows_plan] = True
    main_cmds.set_windows_and_active_plans(windows_plans, active_plan_map)
    main_cmds.set_power_plan(plan[0], do_notify=True)


def power_options_menu():
    global current_windows_plan, active_plan_map, windows_plans
    winplan = None
    # option = lambda winplan: (MenuItem(winplan[1],lambda: set_windows_plan(winplan),checked=active_plan_map[winplan[1]]))
    return list(map(lambda winplan: (MenuItem(winplan[1], lambda: set_windows_plan(winplan),
                                              checked=lambda menu_itm: active_plan_map[winplan[1]])), windows_plans))


def create_menu():  # This will create the menu in the tray app
    global dpp_GUID, app_GUID, main_cmds, auto_power_switch, current_plan
    plan = None
    winplan = None
    opts_menu = power_options_menu()
    menu = Menu(
        MenuItem("Current Config", get_current, default=True),
        # The default setting will make the action run on left click
        MenuItem("CPU Boost",
                 Menu(  # The "Boost" submenu
                     MenuItem("Boost OFF", lambda: main_cmds.set_boost(0),
                              checked=lambda menu_itm: True if int(main_cmds.get_boost()[2:]) == 0 else False),
                     MenuItem("Boost Efficient Aggressive", lambda: main_cmds.set_boost(4),
                              checked=lambda menu_itm: True if int(main_cmds.get_boost()[2:]) == 4 else False),
                     MenuItem("Boost Aggressive", lambda: main_cmds.set_boost(2),
                              checked=lambda menu_itm: True if int(main_cmds.get_boost()[2:]) == 2 else False),
                 )),
        MenuItem("dGPU",
                 Menu(
                     MenuItem("dGPU ON", lambda: main_cmds.set_dgpu(True),
                              checked=lambda menu_itm: (True if bool(main_cmds.get_dgpu()) else False)),
                     MenuItem("dGPU OFF", lambda: main_cmds.set_dgpu(False),
                              checked=lambda menu_itm: (False if bool(main_cmds.get_dgpu()) else True)),
                 )),
        MenuItem("Screen Refresh",
                 Menu(
                     MenuItem("120Hz", lambda: main_cmds.set_screen(120),
                              checked=lambda menu_itm: True if main_cmds.get_screen() == 1 else False),
                     MenuItem("60Hz", lambda: main_cmds.set_screen(60),
                              checked=lambda menu_itm: True if main_cmds.get_screen() == 0 else False),
                 ), visible=main_cmds.check_screen()),
        Menu.SEPARATOR,
        MenuItem("Windows Power Options",
                 Menu(*opts_menu)),
        Menu.SEPARATOR,
        MenuItem("Disable Auto Power Switching", deactivate_powerswitching,
                 checked=lambda menu_itm: False if auto_power_switch else True),
        MenuItem("Enable Auto Power Switching", activate_powerswitching,
                 checked=lambda menu_itm: auto_power_switch),
        Menu.SEPARATOR,
        # I have no idea of what I am doing, fo real, man.y
        # MenuItem('Stuff',*list(map((lambda win_plan: ))))
        *list(map(lambda plan:
                  MenuItem(plan['name'], lambda: apply_plan_deactivate_switching(plan),
                           checked=lambda menu_itm: True if current_plan == plan['name'] else False),
                  config['plans'])),  # Blame @dedo1911 for this. You can find him on github.
        Menu.SEPARATOR,
        MenuItem("Edit config", main_cmds.edit_config),
        MenuItem("Reload config", reload_config),
        Menu.SEPARATOR,
        MenuItem("Quit", quit_app)  # This to close the app, we will need it.
    )
    return menu


def load_config():  # Small function to load the config and return it after parsing
    global G14dir, config_loc
    # Sets the path accordingly whether it is a python script or a frozen .exe
    if getattr(sys, 'frozen', False):
        # Set absolute path for config.yaml
        config_loc = os.path.join(str(G14dir), "config.yml")
    elif __file__:
        # Set absolute path for config.yaml
        config_loc = os.path.join(str(G14dir), "data/config.yml")

    with open(config_loc, 'r') as config_file:
        return yaml.load(config_file, Loader=yaml.FullLoader)


def registry_check():  # Checks if G14Control registry entry exists already
    global registry_key_loc, G14dir
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


def registry_add():  # Adds G14Control.exe to the windows registry to start on boot/login
    global registry_key_loc, G14dir
    G14exe = "G14Control.exe"
    G14dir = str(G14dir)
    G14fileloc = os.path.join(G14dir, G14exe)
    G14Key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            registry_key_loc, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(G14Key, "G14Control", 1, winreg.REG_SZ, G14fileloc)


def registry_remove():  # Removes G14Control.exe from the windows registry
    global registry_key_loc, G14dir
    G14exe = "G14Control.exe"
    G14dir = str(G14dir)
    G14fileloc = os.path.join(G14dir, G14exe)
    G14Key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            registry_key_loc, 0, winreg.KEY_ALL_ACCESS)
    winreg.DeleteValue(G14Key, 'G14Control')


def startup_checks():
    global default_ac_plan, auto_power_switch
    # Only enable auto_power_switch on boot if default power plans are enabled (not set to null):
    if default_ac_plan is not None and default_dc_plan is not None and config['power_switch_enabled'] is True:
        auto_power_switch = True
    else:
        auto_power_switch = False
    # Adds registry entry if enabled in config, but not when in debug mode.
    # if not registry entry is already existing,
    # removes registry entry if registry exists but setting is disabled:
    reg_run_enabled = registry_check()

    if config['start_on_boot'] and not config['debug'] and not reg_run_enabled:
        registry_add()
    if not config['start_on_boot'] and not config['debug'] and reg_run_enabled:
        registry_remove()


def reload_config():
    global config, windows_plans, current_windows_plan, auto_power_switch, default_ac_plan, default_dc_plan
    global default_gaming_plan, default_gaming_plan_games, main_cmds, power_thread, gaming_thread, device
    config = load_config()
    windows_plans = get_windows_plans()
    windows_plan_map = get_windows_plan_map()
    get_power_plans()
    deactivate_powerswitching(False)
    current_windows_plan = config['default_power_plan']

    current_plan = config['default_starting_plan']
    default_ac_plan = config['default_ac_plan']
    default_dc_plan = config['default_dc_plan']
    deactivate_powerswitching(False)
    if default_ac_plan is not None and default_dc_plan is not None and config['power_switch_enabled'] is True:
        auto_power_switch = True
    else:
        auto_power_switch = False
    active_plan_map = get_active_plan_map()

    main_cmds = RunCommands(config, G14dir, app_GUID,
                            dpp_GUID, notify, windows_plans, active_plan_map)

    if config['power_switch_enabled']:
        power_thread = power_check_thread()
        power_thread.start()

    if config['default_gaming_plan'] is not None and config['default_gaming_plan_games'] is not None and config['power_switch_enabled'] is True:
        gaming_thread = gaming_thread_impl('gaming-thread')
        gaming_thread.start()
    default_gaming_plan = config['default_gaming_plan']
    default_gaming_plan_games = config['default_gaming_plan_games']
    if device is not None:
        device.close()
    if config['rog_key'] != None:
        filter = hid.HidDeviceFilter(vendor_id=0x0b05, product_id=0x1866)
        hid_device = filter.get_devices()
        for i in hid_device:
            if str(i).find("col01"):
                device = i
                device.open()
                device.set_raw_data_handler(readData)

    start_plan = {}
    for plan in config['plans']:
        if current_plan == plan['name']:
            start_plan = plan
            break

    main_cmds.apply_plan(start_plan)
    main_cmds.set_power_plan(windows_plan_map[current_windows_plan])


if __name__ == "__main__":

    device = None
    G14dir = None
    G14Dir = get_app_path()
    config = load_config()  # Make the config available to the whole script
    dpp_GUID = None
    app_GUID = None
    get_power_plans()
    windows_plans = get_windows_plans()
    current_windows_plan = config['default_power_plan']
    # If running as admin or in debug mode, launch program
    if is_admin() or config['debug']:
        current_plan = config['default_starting_plan']
        default_ac_plan = config['default_ac_plan']
        default_dc_plan = config['default_dc_plan']
        registry_key_loc = r'Software\Microsoft\Windows\CurrentVersion\Run'
        # Set variable before startup_checks decides what the value should be
        auto_power_switch = False
        ac = psutil.sensors_battery().power_plugged  # Set AC/battery status on start
        resources.extract(config['temp_dir'])
        startup_checks()

        active_plan_map = get_active_plan_map()
        # A process in the background will check for AC, autoswitch plan if enabled and detected
        # Instantiate command line tasks runners in G14RunCommands.py
        main_cmds = RunCommands(config, G14dir, app_GUID,
                                dpp_GUID, notify, windows_plans, active_plan_map)

        if config['power_switch_enabled']:
            power_thread = power_check_thread()
            power_thread.start()

        if config['default_gaming_plan'] is not None and config['default_gaming_plan_games'] is not None and config['power_switch_enabled'] is True:
            gaming_thread = gaming_thread_impl('gaming-thread')
            gaming_thread.start()
        default_gaming_plan = config['default_gaming_plan']
        default_gaming_plan_games = config['default_gaming_plan_games']

        if config['rog_key'] != None:
            filter = hid.HidDeviceFilter(vendor_id=0x0b05, product_id=0x1866)
            hid_device = filter.get_devices()
            for i in hid_device:
                if str(i).find("col01"):
                    device = i
                    device.open()
                    device.set_raw_data_handler(readData)

        # Initialize the icon app and set its name
        icon_app: Icon = pystray.Icon(config['app_name'])
        # This is the displayed name when hovering on the icon
        icon_app.title = config['app_name']
        icon_app.icon = create_icon()  # This will set the icon itself (the graphical icon)
        icon_app.menu = create_menu()  # This will create the menu

        start_plan = {}
        for plan in config['plans']:
            if current_plan == plan['name']:
                start_plan = plan
                break
        windows_plan_map = get_windows_plan_map()
        main_cmds.set_power_plan(windows_plan_map[current_windows_plan])
        main_cmds.apply_plan(start_plan)
        icon_app.run()  # This runs the icon. Is single threaded, blocking.
    else:  # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1)
