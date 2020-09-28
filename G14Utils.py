import winreg
import os


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
    G14exe = "G14Control.exe"
    G14dir = str(G14dir)
    G14fileloc = os.path.join(G14dir, G14exe)
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
