import os
from typing import Any

import wx

from mlib.core.logger import ConsoleHandler, MLogger
from mlib.service.form.notebook_frame import NotebookFrame
from mlib.service.form.notebook_panel import NotebookPanel

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


class ConsoleCtrl:
    def __init__(
        self,
        parent: Any,
        frame: NotebookFrame,
        panel: NotebookPanel,
        rows: int,
        *args,
        **kw,
    ):
        super().__init__(*args, **kw)

        self.parent = parent
        self.frame = frame
        self.panel = panel

        self.root_sizer = wx.BoxSizer(wx.VERTICAL)
        self.text_ctrl = wx.TextCtrl(
            self.parent,
            wx.ID_ANY,
            "",
            wx.DefaultPosition,
            wx.Size(-1, rows),
            wx.TE_READONLY | wx.TE_MULTILINE | wx.WANTS_CHARS,
        )
        self.text_ctrl.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
        )
        self.text_ctrl.SetMargins(3, 3)

        self.root_sizer.Add(self.text_ctrl, 1, wx.GROW | wx.HORIZONTAL, 3)
        MLogger.console_handler = ConsoleHandler(self.text_ctrl)

    def set_parent_sizer(self, parent_sizer: wx.Sizer):
        parent_sizer.Add(self.root_sizer, 0, wx.GROW | wx.HORIZONTAL, 0)

    def write(self, text: str):
        self.text_ctrl.AppendText(text + "\n")
