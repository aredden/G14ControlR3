
import threading
import psutil
import ctypes
import time
from threading import Thread
from G14RunCommands import RunCommands


class PowerCheckThread(threading.Thread):

    def __init__(self, current_plan, default_ac_plan, default_dc_plan, config, main_cmds: RunCommands):
        threading.Thread.__init__(self)
        self.current_plan = current_plan
        self.default_ac_plan = default_ac_plan
        self.default_dc_plan = default_dc_plan
        self.config = config
        self.main_cmds = main_cmds

    def update_info(self, current_plan):
        if current_plan is not None:
            self.current_plan = current_plan

    def run(self):
        current_plan = self.current_plan
        default_ac_plan = self.default_ac_plan
        default_dc_plan = self.default_dc_plan
        main_cmds = self.main_cmds
        config = self.config
        # Only run while loop on startup if auto_power_switch is On (True)
        while True:
            # Check to user hasn't disabled auto_power_switch (i.e. by manually switching plans)
            ac = psutil.sensors_battery().power_plugged  # Get the current AC power status
            # If on AC power, and not on the default_ac_plan, switch to that plan
            if ac and current_plan != default_ac_plan:
                for plan in config['plans']:
                    if plan['name'] == default_ac_plan:
                        main_cmds.apply_plan(plan)
                        break
            # If on DC power, and not on the default_dc_plan, switch to that plan
            if not ac and current_plan != default_dc_plan:
                for plan in config['plans']:
                    if plan['name'] == default_dc_plan:
                        main_cmds.apply_plan(plan)
                        break
            time.sleep(10)

    def kill(self):
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(self.ident,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(self.ident, 0)
            print('Exception raise failure')


fans = psutil.sensors_fans()
print(fans.values())
