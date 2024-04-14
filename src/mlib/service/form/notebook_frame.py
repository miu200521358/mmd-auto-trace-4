import os
import sys
from threading import Thread

import wx

from mlib.service.form.base_frame import BaseFrame
from mlib.service.form.base_notebook import BaseNotebook
from mlib.utils.file_utils import read_histories


class NotebookFrame(BaseFrame):
    def __init__(
        self,
        app: wx.App,
        title: str,
        history_keys: list[str],
        size: wx.Size,
        is_saving: bool,
        *args,
        **kw,
    ):
        super().__init__(app, title, size)

        self.is_saving = is_saving
        self.history_keys = history_keys
        self.histories = read_histories(self.history_keys)

        self._initialize_ui()
        self._initialize_event()

        self.fit()

    def _initialize_ui(self) -> None:
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW))
        self.notebook = BaseNotebook(self, self.is_saving)

    def _initialize_event(self) -> None:
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_change_tab)

    def on_change_tab(self, event: wx.Event) -> None:
        pass

    def on_close(self, event: wx.Event) -> None:
        self.Destroy()
        sys.exit(0)

    def on_sound(self) -> None:
        Thread(target=self.sound_finish_thread).start()

    def sound_finish_thread(self) -> None:
        """Windowsのみ終了音を鳴らす"""
        if os.name == "nt":
            try:
                from winsound import SND_ALIAS, PlaySound

                PlaySound("SystemAsterisk", SND_ALIAS)
            except Exception:
                pass

    def fit(self) -> None:
        self.Centre(wx.BOTH)
        self.Layout()
        self.Refresh()
