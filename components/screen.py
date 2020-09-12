import os
from components.yaml_config import get_config
import re
config = get_config()

def check_screen():  # Checks to see if the G14 has a 120Hz capable screen or not
    check_screen_ref = str(os.path.join(config['temp_dir'] + 'ChangeScreenResolution.exe'))
    screen = os.popen(check_screen_ref + " /m /d=0")  # /m lists all possible resolutions & refresh rates
    output = screen.readlines()
    for line in output:
        if re.search("@120Hz", line):
            return True
    else:
        return False


def get_screen():  # Gets the current screen resolution
    get_screen_ref = str(os.path.join(config['temp_dir'] + 'ChangeScreenResolution.exe'))
    screen = os.popen(get_screen_ref + " /l /d=0")  # /l lists current resolution & refresh rate
    output = screen.readlines()
    for line in output:
        if re.search("@120Hz", line):
            return True
    else:
        return False


def set_screen(refresh, notification=True):
    ttime = config['notification_time']
    if check_screen():  # Before trying to change resolution, check that G14 is capable of 120Hz resolution
        if refresh is None:
            set_screen(120)  # If screen refresh rate is null (not set), set to default refresh rate of 120Hz
        check_screen_ref = str(os.path.join(config['temp_dir'] + 'ChangeScreenResolution.exe'))
        os.popen(
            check_screen_ref + " /d=0 /f=" + str(refresh)
        )
        return notification  
    else:
        return
