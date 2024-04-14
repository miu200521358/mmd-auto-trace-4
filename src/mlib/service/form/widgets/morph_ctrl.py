import os
from typing import Any, Callable, Optional

import wx

from mlib.core.logger import MLogger

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


class MorphChoiceCtrl:
    def __init__(
        self,
        parent: Any,
        window: wx.Window,
        target_name: str,
        choice_width: int,
        choice_tooltip: str = "",
        choice_event: Optional[Callable] = None,
    ) -> None:
        """MMDのモーフのように左右ボタン付きのCHOICE"""
        self.parent = parent
        self.window = window
        self.type_name = target_name
        self.choice_event = choice_event

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.left_ctrl = wx.Button(
            self.window,
            wx.ID_ANY,
            "<",
            wx.DefaultPosition,
            wx.Size(20, -1),
        )
        self.left_ctrl.SetToolTip(
            __(f"{target_name}のプルダウンの選択肢を上方向に移動できます。")
        )
        self.left_ctrl.Bind(wx.EVT_BUTTON, self.on_change_morph_left)
        self.sizer.Add(self.left_ctrl, 0, wx.ALL, 3)

        self.choice_ctrl = wx.Choice(
            self.window,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.Size(choice_width, -1),
            choices=[],
        )
        self.choice_ctrl.SetToolTip(
            __(f"調整対象となる{target_name}の選択肢\n{choice_tooltip}")
        )
        self.choice_ctrl.Bind(wx.EVT_CHOICE, self.on_change_morph)
        self.sizer.Add(self.choice_ctrl, 1, wx.ALL, 3)

        self.right_ctrl = wx.Button(
            self.window,
            wx.ID_ANY,
            ">",
            wx.DefaultPosition,
            wx.Size(20, -1),
        )
        self.right_ctrl.SetToolTip(
            __(f"{target_name}のプルダウンの選択肢を下方向に移動できます。")
        )
        self.right_ctrl.Bind(wx.EVT_BUTTON, self.on_change_morph_right)
        self.sizer.Add(self.right_ctrl, 0, wx.ALL, 3)

    def initialize(self, morph_names: list[str]) -> None:
        self.choice_ctrl.Clear()
        self.choice_ctrl.AppendItems(morph_names)
        if 0 < len(morph_names):
            self.choice_ctrl.SetSelection(0)

    def on_change_morph(self, event: wx.Event) -> None:
        if self.choice_event:
            self.choice_event(event)

    def on_change_morph_right(self, event: wx.Event) -> None:
        selection = self.choice_ctrl.GetSelection()
        if selection == len(self.choice_ctrl.Items) - 1:
            selection = -1
        self.choice_ctrl.SetSelection(selection + 1)
        if self.choice_event:
            self.choice_event(event)

    def on_change_morph_left(self, event: wx.Event) -> None:
        selection = self.choice_ctrl.GetSelection()
        if selection == 0:
            selection = len(self.choice_ctrl.Items)
        self.choice_ctrl.SetSelection(selection - 1)
        if self.choice_event:
            self.choice_event(event)

    def Enable(self, enable: bool) -> None:
        self.choice_ctrl.Enable(enable)
        self.left_ctrl.Enable(enable)
        self.right_ctrl.Enable(enable)
