import os
from typing import Optional

import wx

from mlib.core.logger import MLogger

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


class FloatSliderCtrl:
    def __init__(
        self,
        parent,
        value: float,
        min_value: float,
        max_value: float,
        increment: float,
        spin_increment: float,
        border: int,
        position: wx.Position = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        change_event=None,
        tooltip: Optional[str] = None,
    ) -> None:
        self._min = min_value
        self._max = max_value
        self._increment = increment
        self._spin_increment = spin_increment
        self._change_event = change_event
        self._initial_value = value
        i_value, i_min, i_max = [
            round(v / increment) for v in (value, min_value, max_value)
        ]

        self._value_ctrl = wx.TextCtrl(
            parent,
            wx.ID_ANY,
            str(f"{value:.2f}"),
            wx.DefaultPosition,
            wx.Size(50, -1),
            style=wx.TE_PROCESS_ENTER,
        )
        self._value_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_change_value)
        if tooltip:
            self._value_ctrl.SetToolTip(
                tooltip + __("\nEnterキーを押下したタイミングで値が反映されます。")
            )

        self._slider = wx.Slider(
            parent, wx.ID_ANY, i_value, i_min, i_max, position, size, wx.SL_HORIZONTAL
        )
        self._slider.Bind(wx.EVT_SCROLL, self._on_scroll)
        self._slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self._on_scroll_release)
        self._slider.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel_spin)
        if tooltip:
            self._slider.SetToolTip(tooltip)

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self._value_ctrl, 0, wx.LEFT | wx.TOP | wx.BOTTOM, border)
        self.sizer.Add(self._slider, 0, wx.TOP | wx.RIGHT | wx.BOTTOM, border)

    def _on_scroll(self, event: wx.Event):
        tv, sv = self.get_value_by_slider(self._slider.GetValue())
        self._value_ctrl.ChangeValue(tv)

    def _on_scroll_release(self, event: wx.Event):
        self.Enable(False)

        tv, sv = self.get_value_by_slider(self._slider.GetValue())
        self._value_ctrl.ChangeValue(tv)

        if self._change_event:
            self._change_event(event)

        self.Enable(True)

    def _on_change_value(self, event: wx.Event):
        self.Enable(False)
        tv, sv = self.get_value_by_text(self._value_ctrl.GetValue())
        self._value_ctrl.ChangeValue(tv)
        self._slider.SetValue(sv)

        if self._change_event:
            self._change_event(event)

        self.Enable(True)

    def _on_wheel_spin(self, event: wx.MouseEvent):
        """マウスホイールによるスピンコントロール"""
        tv, sv = self.get_value_by_slider(self._slider.GetValue())
        if event.GetWheelRotation() > 0:
            v = float(tv) - self._spin_increment
        else:
            v = float(tv) + self._spin_increment
        tv, sv = self.get_value_by_text(str(v))
        self._value_ctrl.ChangeValue(tv)
        self._slider.SetValue(sv)

    def SetValue(self, v: float):
        tv, sv = self.get_value_by_text(str(v))
        self._slider.SetValue(sv)
        self._value_ctrl.SetValue(tv)

    def SetMax(self, v: float) -> None:
        self._max = v
        self.change_limit()

    def SetMin(self, v: float) -> None:
        self._min = v
        self.change_limit()

    def change_limit(self) -> None:
        i_min, i_max = [round(v / self._increment) for v in (self._min, self._max)]

        self._slider.SetMin(i_min)
        self._slider.SetMax(i_max)

    def ChangeValue(self, v: float):
        tv, sv = self.get_value_by_text(str(v))
        self._value_ctrl.ChangeValue(tv)
        self._slider.SetValue(sv)

    def GetValue(self):
        return float(self._value_ctrl.GetValue())

    def Add(
        self,
        parent_sizer: wx.Sizer,
        proportion: int,
        flag: int,
        border: int,
    ):
        self.sizer.Add(parent_sizer, proportion, flag, border)

    def get_value_by_text(self, s: str) -> tuple[str, float]:
        """範囲内に収まる数値を返す"""
        try:
            v = float(s)
        except Exception:
            v = self._initial_value

        v = max(self._min, min(self._max, v))
        sv = round(v / self._increment)
        return f"{v:.2f}", sv

    def get_value_by_slider(self, f: float) -> tuple[str, float]:
        """範囲内に収まる数値を返す"""
        v = max(self._min, min(self._max, f * self._increment))
        sv = round(v / self._increment)
        return f"{v:.2f}", sv

    def Enable(self, enable: bool):
        self._value_ctrl.Enable(enable)
        self._slider.Enable(enable)
