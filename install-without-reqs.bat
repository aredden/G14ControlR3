python setup.py build
xcopy build\exe.win32-3.8\ C:\G14control\ /E /C
xcopy data\ C:\G14control\ /E /C
xcopy pywinusb\ C:\G14control\lib\pywinusb\ /E /C