
import os
import subprocess
import time
import re

class RunCommands():
        
    def __init__(self,config, G14dir, app_GUID, dpp_GUID, notify, windows_plans, active_plan_map):
        self.config = config
        self.G14dir = G14dir
        self.app_GUID = app_GUID
        self.dpp_GUID = dpp_GUID
        self.notify = notify
        self.windows_plans = windows_plans
        self.active_plan_map = active_plan_map
        self.windows_plan_map = {name:guid for guid,name in iter(windows_plans)}

    def set_windows_and_active_plans(self,winplns,activeplns):
        self.active_plan_map = activeplns
        self.windows_plans = winplns
        

        # noinspection PyBroadException
    def parse_boolean(self, parse_string):  # Small utility to convert windows HEX format to a boolean.
        try:
            if parse_string == "0x00000000":  # We will consider this as False
                return False
            else:  # We will consider this as True
                return True
        except Exception:
            return None  # Just in case™


    def get_boost(self):
        current_pwr = os.popen("powercfg /GETACTIVESCHEME")  # I know, it's ugly, but no other way to do that from py.
        pwr_guid = current_pwr.readlines()[0].rsplit(": ")[1].rsplit(" (")[0].lstrip("\n")  # Parse the GUID
        SUB_PROCESSOR = " 54533251-82be-4824-96c1-47b60b740d00"
        PERFBOOSTMODE = " be337238-0d82-4146-a960-4f3749d470c7"
        pwr_settings = os.popen("powercfg /Q " + pwr_guid + SUB_PROCESSOR + PERFBOOSTMODE)  # Let's get the boost option in the currently active power scheme
        output = pwr_settings.readlines()  # We save the output to parse it afterwards
        ac_boost = output[-3].rsplit(": ")[1].strip("\n")  # Parsing AC, assuming the DC is the same setting
        # battery_boost = parse_boolean(output[-2].rsplit(": ")[1].strip("\n"))  # currently unused, we will set both
        return ac_boost


    def do_boost(self, state):
        CURRENT_SCHEME = os.popen("powercfg /GETACTIVESCHEME")  # Just to be safe, let's get the current power scheme
        SUB_PROCESSOR = "54533251-82be-4824-96c1-47b60b740d00"
        PERFBOOSTMODE = "be337238-0d82-4146-a960-4f3749d470c7"
        set_ac = "powercfg /setacvalueindex"
        set_dc = "powercfg /setdcvalueindex"
        pwr_guid = CURRENT_SCHEME.readlines()[0].rsplit(": ")[1].rsplit(" (")[0].lstrip("\n")  # Parse the GUID
        if state is False:
            state = 0
        SET_AC_VAL = "{0} {1} {2} {3} {4}".format(set_ac,pwr_guid,SUB_PROCESSOR,PERFBOOSTMODE,str(state))
        SET_DC_VAL = "{0} {1} {2} {3} {4}".format(set_dc,pwr_guid,SUB_PROCESSOR,PERFBOOSTMODE,str(state))
        subprocess.Popen(SET_AC_VAL,shell=True,creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen(SET_DC_VAL,shell=True,creationflags=subprocess.CREATE_NO_WINDOW)
        print(SET_AC_VAL)
        print(SET_DC_VAL)


    def set_boost(self, state, notification=True):
        current_boost_mode = state
        win_plans = self.windows_plans
        active_plans = self.active_plan_map
        windows_plan_map = self.windows_plan_map
        CURRENT_SCHEME = os.popen("powercfg /GETACTIVESCHEME") 
        pwr_guid = CURRENT_SCHEME.readlines()[0].rsplit(": ")[1].rsplit(" (")[0].lstrip("\n").replace(" ","")  # Parse the GUID
        switch_to = list({val for key,val in windows_plan_map.items() if val!=pwr_guid})[0]
        switch_to_guid = win_plans
        print(switch_to, "switch to guid")
        print(pwr_guid, "power guid")
        print(self.active_plan_map)
        self.set_power_plan(switch_to)
        time.sleep(.25)
        self.set_power_plan(pwr_guid)
        if state is True:  # Activate boost
            self.do_boost(state)
            if notification is True:
                self.notify("Boost ENABLED")  # Inform the user
        elif state is False:  # Deactivate boost
            self.do_boost(state)
            if notification is True:
                self.notify("Boost DISABLED")  # Inform the user
        elif state == 0:
            self.do_boost(state)
            if notification is True:
                self.notify("Boost DISABLED")  # Inform the user
        elif state == 4:
            self.do_boost(state)
            if notification is True:
                self.notify("Boost set to Efficient Aggressive")  # Inform the user
        elif state == 2:
            self.do_boost(state)
            if notification is True:
                self.notify("Boost set to Aggressive")  # Inform the user
        self.set_power_plan(switch_to)
        time.sleep(0.25)
        self.set_power_plan(pwr_guid)


    def get_dgpu(self):
        current_pwr = os.popen("powercfg /GETACTIVESCHEME")  # I know, it's ugly, but no other way to do that from py.
        pwr_guid = current_pwr.readlines()[0].rsplit(": ")[1].rsplit(" (")[0].lstrip("\n")  # Parse the GUID
        pwr_settings = os.popen(
            "powercfg /Q " + pwr_guid + " e276e160-7cb0-43c6-b20b-73f5dce39954 a1662ab2-9d34-4e53-ba8b-2639b9e20857"
        )  # Let's get the dGPU status in the current power scheme
        output = pwr_settings.readlines()  # We save the output to parse it afterwards
        dgpu_ac = self.parse_boolean(output[-3].rsplit(": ")[1].strip("\n"))  # Convert to boolean for "On/Off"
        if dgpu_ac is None:
            return False
        else:
            return True


    def set_dgpu(self, state, notification=True):
        config = self.config
        G14dir = self.G14dir
        current_pwr = os.popen("powercfg /GETACTIVESCHEME")  # Just to be safe, let's get the current power scheme
        pwr_guid = current_pwr.readlines()[0].rsplit(": ")[1].rsplit(" (")[0].lstrip("\n")  # Parse the GUID
        if state is True:  # Activate dGPU
            os.popen(
                "powercfg /setacvalueindex " + pwr_guid + " e276e160-7cb0-43c6-b20b-73f5dce39954 a1662ab2-9d34-4e53-ba8b-2639b9e20857 2"
            )
            os.popen(
                "powercfg /setdcvalueindex " + pwr_guid + " e276e160-7cb0-43c6-b20b-73f5dce39954 a1662ab2-9d34-4e53-ba8b-2639b9e20857 2"
            )
            if notification is True:
                self.notify("dGPU ENABLED")  # Inform the user
        elif state is False:  # Deactivate dGPU
            os.popen(
                "powercfg /setacvalueindex " + pwr_guid + " e276e160-7cb0-43c6-b20b-73f5dce39954 a1662ab2-9d34-4e53-ba8b-2639b9e20857 0"
            )
            os.popen(
                "powercfg /setdcvalueindex " + pwr_guid + " e276e160-7cb0-43c6-b20b-73f5dce39954 a1662ab2-9d34-4e53-ba8b-2639b9e20857 0"
            )
            os.system("\"" + str(G14dir) + "\\restartGPUcmd.bat" + "\"")
            if notification is True:
                self.notify("dGPU DISABLED")  # Inform the user


    def check_screen(self):  # Checks to see if the G14 has a 120Hz capable screen or not
        config = self.config
        check_screen_ref = str(os.path.join(config['temp_dir'] + 'ChangeScreenResolution.exe'))
        screen = os.popen(check_screen_ref + " /m /d=0")  # /m lists all possible resolutions & refresh rates
        output = screen.readlines()
        for line in output:
            if re.search("@120Hz", line):
                return True
        else:
            return False


    def get_screen(self):  # Gets the current screen resolution
        config = self.config
        get_screen_ref = str(os.path.join(config['temp_dir'] + 'ChangeScreenResolution.exe'))
        screen = os.popen(get_screen_ref + " /l /d=0")  # /l lists current resolution & refresh rate
        output = screen.readlines()
        for line in output:
            if re.search("@120Hz", line):
                return True
        else:
            return False


    def set_screen(self, refresh: str or int, notification=True):
        config = self.config
        if self.check_screen():  # Before trying to change resolution, check that G14 is capable of 120Hz resolution
            if refresh is None:
                self.set_screen(120)  # If screen refresh rate is null (not set), set to default refresh rate of 120Hz  
            check_screen_ref = str(os.path.join(config['temp_dir'] + 'ChangeScreenResolution.exe'))
            os.popen(
                check_screen_ref + " /d=0 /f=" + str(refresh)
            )
            if notification is True:
                self.notify("Screen refresh rate set to: " + str(refresh) + "Hz")
        else:
            return


    def set_atrofac(self, asus_plan, cpu_curve=None, gpu_curve=None):
        config = self.config
        atrofac = str(os.path.join(config['temp_dir'] + "atrofac-cli.exe"))
        cmdargs = ""
        if cpu_curve is not None and gpu_curve is not None:
            cmdargs = atrofac + " fan --cpu " + cpu_curve + " --gpu " + gpu_curve + " --plan " + asus_plan
        elif cpu_curve is not None and gpu_curve is None:
            cmdargs = atrofac + " fan --cpu " + cpu_curve + " --plan " + asus_plan
        elif cpu_curve is None and gpu_curve is not None:
            cmdargs = atrofac + " fan --gpu " + gpu_curve + " --plan " + asus_plan
        else:
            cmdargs = atrofac + " plan " + asus_plan
        subprocess.Popen(cmdargs,shell=True,creationflags=subprocess.CREATE_NO_WINDOW)


    def set_ryzenadj(self, tdp):
        config = self.config
        ryzenadj = str(os.path.join(config['temp_dir'] + "ryzenadj.exe"))
        if tdp is None:
            pass
        else:
            subprocess.Popen(ryzenadj + " -a " + str(tdp) + " -b " + str(tdp),shell=True,creationflags=subprocess.CREATE_NO_WINDOW)

    
    def set_power_plan(self,GUID):
        print("setting power plan GUID to: ", GUID)
        subprocess.check_output(["powercfg", "/s", GUID],shell=True,creationflags=subprocess.CREATE_NO_WINDOW)


    def apply_plan(self,plan):
        current_plan = plan['name']
        self.set_atrofac(plan['plan'], plan['cpu_curve'], plan['gpu_curve'])
        self.set_boost(plan['boost'], False)
        self.set_dgpu(plan['dgpu_enabled'], False)
        self.set_screen(plan['screen_hz'], False)
        self.set_ryzenadj(plan['cpu_tdp'])
        self.notify("Applied plan " + plan['name'])
        return current_plan
