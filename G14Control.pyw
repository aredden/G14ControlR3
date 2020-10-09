from G14Data import G14_Data, load_config
import ctypes
import os
import sys
import threading
import time
from threading import Thread
import psutil
import pystray
from pystray._base import Icon, Menu, MenuItem
import resources
from G14RunCommands import RunCommands
from G14Utils import (
    create_icon,
    is_admin,
    get_app_path,
    rog_keyset,
    startup_checks,
    get_active_windows_plan,
)
from win10toast import ToastNotifier

toaster = ToastNotifier()
main_cmds: RunCommands


def activate_powerswitching():
    global data
    data.auto_power_switch = True
    if data.power_thread is None:
        data.power_thread = power_check_thread()
        data.power_thread.start()
        notify("Power switching has been activated.")
    elif not data.power_thread.is_alive():
        data.power_thread = power_check_thread()
        data.power_thread.start()
        notify("Power switching has been activated.")
    if (
        data.default_gaming_plan is not None
        and data.default_gaming_plan_games is not None
    ):
        if data.gaming_thread is None:
            data.gaming_thread = gaming_check_thread()
            data.gaming_thread.start()
        elif not data.gaming_thread.is_alive():
            data.gaming_thread = gaming_check_thread()
            data.gaming_thread.start()


def deactivate_powerswitching(should_notify=True):
    global data
    data.auto_power_switch = False
    if data.power_thread is not None and data.power_thread.is_alive():
        data.power_thread.kill()
    if data.gaming_thread is not None and data.gaming_thread.is_alive():
        data.gaming_thread.kill()

    # Plan change notifies first, so this needs to be
    # on a delay to prevent simultaneous notifications
    if should_notify:
        notify("Auto power switching has been disabled.", wait=1)


class power_check_thread(threading.Thread):
    def __init__(
        self,
    ):
        threading.Thread.__init__(self, daemon=True)

    def run(self):
        global data
        # Only run while loop on startup if auto_power_switch is On (True)
        if data.auto_power_switch:
            while data.run_power_thread:
                # Check to user hasn't disabled auto_power_switch
                # (i.e. by manually switching plans)
                if data.auto_power_switch:
                    ac = (
                        psutil.sensors_battery().power_plugged
                    )  # Get the current AC power status
                    # If on AC power, and not on the default_ac_plan, switch to that plan
                    if ac and data.current_plan != data.default_ac_plan:
                        for plan in data.config["plans"]:
                            if plan["name"] == data.default_ac_plan:
                                apply_plan(plan)
                                break
                    # If on DC power, and not on the default_dc_plan, switch to that plan
                    if not ac and data.current_plan != data.default_dc_plan:
                        for plan in data.config["plans"]:
                            if plan["name"] == data.default_dc_plan:
                                apply_plan(plan)
                                break
                time.sleep(10)
        else:
            self.kill()

    def kill(self):
        thread_id = self.ident
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            thread_id, ctypes.py_object(SystemExit)
        )
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print("Exception raise failure")


class gaming_check_thread(threading.Thread):
    def __init__(
        self,
    ):
        threading.Thread.__init__(self, daemon=True)

    def run(
        self,
    ):  # Checks if user specified games/programs are running,
        # and switches to user defined plan, then switches back once closed
        global data
        previous_plan = None  # Define the previous plan to switch back to
        if data.auto_power_switch:
            while data.run_gaming_thread:  # Continuously check every 10 seconds
                if data.auto_power_switch:
                    output = os.popen("wmic process get description, processid").read()
                    process = output.split("\n")
                    processes = set(i.split(" ")[0] for i in process)
                    # List of user defined processes
                    targets = set(data.default_gaming_plan_games)
                    if (
                        processes & targets
                    ):  # Compare 2 lists, if ANY overlap, set game_running to true
                        game_running = True
                    else:
                        game_running = False
                    # If game is running and not on the desired gaming plan, switch to that plan
                    if game_running and data.current_plan != data.default_gaming_plan:
                        previous_plan = data.current_plan
                        for plan in data.config["plans"]:
                            if plan["name"] == data.default_gaming_plan:
                                apply_plan(plan)
                                notify(plan["name"])
                                break
                    # If game is no longer running, and not on previous plan
                    #  already (if set), then switch back to previous plan
                    if (
                        not game_running
                        and previous_plan is not None
                        and previous_plan != data.current_plan
                    ):
                        for plan in data.config["plans"]:
                            if plan["name"] == previous_plan:
                                apply_plan(plan)
                                notify(plan["name"])
                                break
                    # Check for programs every 10 sec
                time.sleep(config["check_power_every"])
        else:
            self.kill()

    def kill(self):
        thread_id = self.ident
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            thread_id, ctypes.py_object(SystemExit)
        )
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print("Exception raise failure")


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


def apply_plan(plan):
    global data
    data.current_plan = plan["name"]
    data.main_cmds.set_windows_and_active_plans(
        data.windows_plans, data.active_plan_map
    )
    data.main_cmds.set_atrofac(plan["plan"], plan["cpu_curve"], plan["gpu_curve"])
    data.main_cmds.set_boost(plan["boost"], False)
    data.main_cmds.set_dgpu(plan["dgpu_enabled"], False)
    data.main_cmds.set_screen(plan["screen_hz"], False)
    data.main_cmds.set_ryzenadj(plan["cpu_tdp"])
    notify("Applied plan " + plan["name"])


def quit_app():
    global device, data, icon_app

    data.run_power_thread = False
    data.run_gaming_thread = False
    if data.power_thread is not None and data.power_thread.is_alive():
        data.power_thread.kill()
        while data.power_thread.isAlive():
            print("Waiting for power thread to die...")
            time.sleep(0.25)
        print("Power thread was alive, and now is dead.")

    if data.gaming_thread is not None and data.gaming_thread.is_alive():
        data.gaming_thread.kill()
        while data.gaming_thread.isAlive():
            print("Waiting for power thread to die...")
            time.sleep(0.25)
        print("Gaming thread was alive, and now is dead.")
    if device is not None:
        device.close()
    try:
        icon_app.stop()
    except SystemExit:
        print("System Exit")
        sys.exit()


def apply_plan_deactivate_switching(plan):
    global data
    data.current_plan = plan["name"]
    apply_plan(plan)
    deactivate_powerswitching()


def set_windows_plan(plan):
    global data
    if config["debug"]:
        print(plan)
    data.current_windows_plan = plan[1]
    data.update_win_plan(plan[1])
    data.main_cmds.set_windows_and_active_plans(
        data.windows_plans, data.active_plan_map
    )
    data.main_cmds.set_power_plan(plan[0], do_notify=True)


def power_options_menu():
    global data
    return list(
        map(
            lambda winplan: (
                MenuItem(
                    winplan[1],
                    lambda: set_windows_plan(winplan),
                    checked=lambda menu_itm: winplan[1]
                    == list(get_active_windows_plan().keys())[0],
                )
            ),
            data.windows_plans,
        )
    )


def create_menu(
    main_cmds, windows_plans, icon_app, device
):  # This will create the menu in the tray app
    global data
    opts_menu = power_options_menu()

    menu = Menu(
        # The default setting will make the action run on left click
        MenuItem(
            "CPU Boost",
            Menu(  # The "Boost" submenu
                MenuItem(
                    "Boost OFF",
                    lambda: main_cmds.set_boost(0),
                    checked=lambda menu_itm: True
                    if int(main_cmds.get_boost()[2:]) == 0
                    else False,
                ),
                MenuItem(
                    "Boost Efficient Aggressive",
                    lambda: main_cmds.set_boost(4),
                    checked=lambda menu_itm: True
                    if int(main_cmds.get_boost()[2:]) == 4
                    else False,
                ),
                MenuItem(
                    "Boost Aggressive",
                    lambda: main_cmds.set_boost(2),
                    checked=lambda menu_itm: True
                    if int(main_cmds.get_boost()[2:]) == 2
                    else False,
                ),
            ),
        ),
        MenuItem(
            "dGPU",
            Menu(
                MenuItem(
                    "dGPU ON",
                    lambda: main_cmds.set_dgpu(True),
                    checked=lambda menu_itm: (
                        True if bool(main_cmds.get_dgpu()) else False
                    ),
                ),
                MenuItem(
                    "dGPU OFF",
                    lambda: main_cmds.set_dgpu(False),
                    checked=lambda menu_itm: (
                        False if bool(main_cmds.get_dgpu()) else True
                    ),
                ),
            ),
        ),
        MenuItem(
            "Screen Refresh",
            Menu(
                MenuItem(
                    "120Hz",
                    lambda: main_cmds.set_screen(120),
                    checked=lambda menu_itm: True
                    if main_cmds.get_screen() == 1
                    else False,
                ),
                MenuItem(
                    "60Hz",
                    lambda: main_cmds.set_screen(60),
                    checked=lambda menu_itm: True
                    if main_cmds.get_screen() == 0
                    else False,
                ),
            ),
            visible=main_cmds.check_screen(),
        ),
        Menu.SEPARATOR,
        MenuItem("Windows Power Options", Menu(*opts_menu)),
        Menu.SEPARATOR,
        MenuItem(
            "Disable Auto Power Switching",
            lambda: deactivate_powerswitching(True),
            checked=lambda menu_itm: False if data.auto_power_switch else True,
        ),
        MenuItem(
            "Enable Auto Power Switching",
            lambda: activate_powerswitching(),
            checked=lambda menu_itm: data.auto_power_switch,
        ),
        Menu.SEPARATOR,
        # I have no idea of what I am doing, fo real, man.y
        # MenuItem('Stuff',*list(map((lambda win_plan: ))))
        *list(
            map(
                lambda plan: MenuItem(
                    plan["name"],
                    lambda: apply_plan_deactivate_switching(plan),
                    checked=lambda menu_itm: True
                    if data.current_plan == plan["name"]
                    else False,
                ),
                data.config["plans"],
            )
        ),  # Blame @dedo1911 for this. You can find him on github.
        Menu.SEPARATOR,
        MenuItem("Edit config", main_cmds.edit_config),
        MenuItem("Reload config", lambda: reload_config(icon_app, device)),
        Menu.SEPARATOR,
        MenuItem("Quit", quit_app)  # This to close the app, we will need it.
    )
    return menu


def reload_config(icon_app, device):
    global data
    data = G14_Data()
    deactivate_powerswitching(False)
    if (
        data.default_ac_plan is not None
        and data.default_dc_plan is not None
        and data.config["power_switch_enabled"] is True
    ):
        data.auto_power_switch = True
    else:
        data.auto_power_switch = False

    if data.auto_power_switch and data.config["power_switch_enabled"]:
        data.power_thread = power_check_thread()
        data.power_thread.start()

    if (
        data.config["default_gaming_plan"] is not None
        and data.config["default_gaming_plan_games"] is not None
        and data.config["power_switch_enabled"] is True
    ):
        data.gaming_thread = gaming_check_thread()
        data.gaming_thread.start()

    if device is not None:
        device.close()
    device = rog_keyset(config)

    start_plan = {}
    for plan in data.config["plans"]:
        if data.current_plan == plan["name"]:
            start_plan = plan
            break

    apply_plan(start_plan)
    data.main_cmds.set_power_plan(data.windows_plan_map[data.current_windows_plan])
    updated_menu = create_menu(data.main_cmds, data.windows_plans, icon_app, device)
    icon_app.menu = updated_menu
    icon_app.update_menu()


def startup(config, icon_app):
    global data
    data = G14_Data()

    # Set variable before startup_checks decides what the value should be
    resources.extract(config["temp_dir"])

    startup_checks(data)
    # A process in the background will check for AC, autoswitch plan if enabled and detected
    # Instantiate command line tasks runners in G14RunCommands.py

    if data.power_switch_enabled:
        data.power_thread = power_check_thread()
        data.power_thread.start()

    if (
        data.default_gaming_plan is not None
        and data.default_gaming_plan_games is not None
        and data.power_switch_enabled
    ):
        data.gaming_thread = gaming_check_thread()
        data.gaming_thread.start()

    device = rog_keyset(config)

    # This is the displayed name when hovering on the icon
    icon_app.title = config["app_name"]
    icon_app.icon = create_icon(
        config
    )  # This will set the icon itself (the graphical icon)
    icon_app.menu = create_menu(
        data.main_cmds, data.windows_plans, icon_app, device
    )  # This will create the menu

    start_plan = {}
    for plan in data.config["plans"]:
        if data.current_plan == plan["name"]:
            start_plan = plan
            break
    data.main_cmds.set_power_plan(data.windows_plan_map[data.current_windows_plan])
    apply_plan(start_plan)
    icon_app.run()  # This runs the icon. Is single threaded, blocking.


if __name__ == "__main__":
    global icon_app
    device = None
    G14dir = get_app_path()
    config = load_config(G14dir)  # Make the config available to the whole script
    # Initialize the icon app and set its name
    icon_app: Icon = pystray.Icon(config["app_name"])
    # If running as admin or in debug mode, launch program
    if is_admin() or config["debug"]:
        startup(config, icon_app)
    else:  # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
