import unittest
import os
import re
from G14RunCommands import RunCommands
import yaml
import pathlib
import subprocess as sp
import subprocess
import sys

config = {}
windows_plans = []
current_windows_plan = ""
app_GUID = ""
dpp_GUID = ""
active_plan_map = dict()
G14dir = ""


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


"""
Cannot be run before @get_windows_plans()
"""


def get_active_plan_map():
    global windows_plans, active_plan_map
    try:
        active_plan_map["Balanced"]
        return active_plan_map
    except Exception:
        active_plan_map = {x[1]: False for x in windows_plans}
        active_plan_map[current_windows_plan] = True
        return active_plan_map


def get_app_path():
    global G14dir
    G14Dir = ""
    # Sets the path accordingly whether it is a python script or a frozen .exe
    if getattr(sys, 'frozen', False):
        G14dir = os.path.dirname(os.path.realpath(sys.executable))
    elif __file__:
        G14dir = os.path.dirname(os.path.realpath(__file__))


def loadConfig():
    config = {}
    with open('data/config.yml') as file:
        config = yaml.load(file.read())
    return config


class RunCommandsTests(unittest.TestCase):

    def setUp(self):
        global config, windows_plans, active_plan_map, config, dpp_GUID, app_GUID, G14dir
        self.config = loadConfig()
        config = self.config
        get_power_plans()
        get_app_path()
        get_windows_plans()
        get_active_plan_map()
        self.main_cmds = RunCommands(self.config,
                                     G14dir=G14dir,
                                     app_GUID=app_GUID,
                                     dpp_GUID=dpp_GUID,
                                     notify=lambda x: print(x),
                                     windows_plans=windows_plans,
                                     active_plan_map=active_plan_map)

    def boost_test(self):
        startboost = self.main_cmds.get_boost()
        self.main_cmds.do_boost(2)
        boost = self.main_cmds.get_boost()
        self.assertEqual(
            2, int(boost, 16), "Boost not equal to boost that was set (2)")
        self.main_cmds.do_boost(4)
        boost = self.main_cmds.get_boost()
        self.assertEqual(4, int(boost, 16))

        self.main_cmds.do_boost(0)
        boost = self.main_cmds.get_boost()
        self.assertEqual(0, int(boost, 16))

        self.main_cmds.do_boost(int(startboost, 16))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(RunCommandsTests('boost_test'))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
