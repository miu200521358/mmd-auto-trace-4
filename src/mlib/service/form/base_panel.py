import wx

from mlib.service.form.base_frame import BaseFrame


class BasePanel(wx.Panel):
    def __init__(self, frame: BaseFrame, *args, **kw) -> None:
        self.frame = frame
        super().__init__(
            self.frame, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL
        )
        self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT))

        self.active_background_color = wx.Colour("PINK")
        """ボタンの何かの設定が入ってる時の背景色"""

        self.selectable_background_color = wx.Colour("MEDIUM GOLDENROD")
        """ボタンが有効になっている時の背景色"""

        self.default_background_color = wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_BTNFACE
        )
        """デフォルトボタン背景色"""

        self.root_sizer = wx.BoxSizer(wx.VERTICAL)
        self.is_fix_tab = False

        self.SetSizer(self.root_sizer)
        self.root_sizer.Layout()
        self.root_sizer.Fit(self)

    def Enable(self, enable: bool) -> None:
        pass
