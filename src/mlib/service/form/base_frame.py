from typing import Optional

import wx


class BaseFrame(wx.Frame):
    def __init__(
        self,
        app: wx.App,
        title: str,
        size: wx.Size,
        *args,
        parent: Optional["BaseFrame"] = None,
        **kw,
    ):
        wx.Frame.__init__(
            self,
            None,
            title=title,
            size=size,
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL | wx.FULL_REPAINT_ON_RESIZE,
        )
        self.app = app
        self.parent = parent
        self.size = size
