import os
import sys
import yaml
import pathlib
from pathlib import Path
G14dir: str
config_loc: str = ''


def _get_app_path():
    global G14dir
    if getattr(sys, 'frozen', False):  # Sets the path accordingly whether it is a python script or a frozen .exe
        G14dir = str(Path(os.path.realpath(sys.executable)).parent)
    elif __file__:
        G14dir = str(Path(pathlib.os.curdir).parent)


def get_config():
    global config_loc
    _get_app_path()
    if getattr(sys, 'frozen', False):  # Sets the path accordingly whether it is a python script or a frozen .exe
        config_loc = os.path.join(str(G14dir), "config.yml")  # Set absolute path for config.yaml
    elif __file__:
        config_loc = os.path.join(str(G14dir), "data\config.yml")  # Set absolute path for config.yaml

    with open(config_loc, 'r') as config_file:
        return yaml.load(config_file, Loader=yaml.FullLoader)