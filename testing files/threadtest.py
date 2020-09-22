import threading
import os
import time
import ctypes


class PowerThreadTest(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while True:
            print('running')
            time.sleep(1)

    def kill(self):
        print('trying to kill')
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(self.ident,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(self.ident, 0)
            print('Exception raise failure')


def starto():
    thd = PowerThreadTest()
    thd.start()
    time.sleep(6)
    thd.kill()
    thd.join()
    print("ded")
    print(thd, thd.is_alive())


starto()
