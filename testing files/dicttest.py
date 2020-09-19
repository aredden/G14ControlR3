import os, re

win_opts = re.findall(r"([0-9a-f\-]{36}) *\((.*)\) *\*?\n", os.popen("powercfg /l").read())

names:dict




def thing():
    global names
    print(names)

    
    
def thing0():

    names = {x[1]:False for x in win_opts}
    names['Balanced'] = True
    
thing0()

thing()