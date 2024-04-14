import wx

from mlib.service.form.base_panel import BasePanel
from mlib.service.form.notebook_frame import NotebookFrame


class NotebookPanel(BasePanel):
    def __init__(self, frame: NotebookFrame, tab_idx: int, *args, **kw) -> None:
        super().__init__(
            frame.notebook,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.DefaultSize,
            wx.TAB_TRAVERSAL,
        )
        self.tab_idx = tab_idx
        self.frame = frame
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT))

        self.active_background_color = wx.Colour("PINK")
        """ボタンが有効になっている時の背景色"""

        self.root_sizer = wx.BoxSizer(wx.VERTICAL)
        self.is_fix_tab = False

        self.SetSizer(self.root_sizer)
        self.root_sizer.Layout()
        self.root_sizer.Fit(self)

    def Enable(self, enable: bool) -> None:
        pass
