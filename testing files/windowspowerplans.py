import os
import re


windows_power_options = list(map(lambda to_break: tuple(re.sub(r"^ +| +$", "", to_break).split(" ", maxsplit=1)), list(
    map(lambda x: re.sub(r"Power Scheme GUID: |[*()]|\n", "", x).replace("  ", " "), os.popen('powercfg /l').readlines()[3:]))))


windows_power_options_cleaner = re.findall(
    r"([0-9a-f\-]{36}) *\((.*)\) *\*?\n", os.popen("powercfg /l").read())

startspace = re.compile("^ ")
endspace = re.compile(' $')
lines = os.popen('powercfg /l').readlines()[3:]

print(windows_power_options)
