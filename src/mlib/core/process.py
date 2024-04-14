import os
import sys
from multiprocessing import Process
from multiprocessing.popen_spawn_win32 import Popen


class _Popen(Popen):
    def __init__(self, *args, **kw):
        if hasattr(sys, "frozen") and hasattr(sys, "_MEIPASS"):
            # We have to set original _MEIPASS2 value from sys._MEIPASS
            # to get --onefile mode working.
            os.putenv("_MEIPASS2", sys._MEIPASS)
        try:
            super(_Popen, self).__init__(*args, **kw)
        finally:
            if hasattr(sys, "frozen"):
                # On some platforms (e.g. AIX) 'os.unsetenv()' is not
                # available. In those cases we cannot delete the variable
                # but only set it to the empty string. The bootloader
                # can handle this case.
                if hasattr(os, "unsetenv"):
                    os.unsetenv("_MEIPASS2")
                else:
                    os.putenv("_MEIPASS2", "")


class MProcess(Process):
    _Popen = _Popen
