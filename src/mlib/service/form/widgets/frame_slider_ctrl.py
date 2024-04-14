import os
from typing import Optional

import wx

from mlib.core.logger import MLogger
from mlib.service.form.widgets.spin_ctrl import WheelSpinCtrl

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


class FrameSliderCtrl:
    def __init__(
        self,
        parent,
        border: int,
        position: wx.Position = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        change_event=None,
        tooltip: Optional[str] = None,
    ) -> None:
        self._min = 0
        self._max = 10000
        self.key_fnos = [f for f in range(self._max + 1)]
        self._change_event = change_event
        self._initial_value = 0

        self._fno_ctrl = WheelSpinCtrl(
            parent,
            initial=0,
            min=0,
            max=10000,
            size=wx.Size(70, -1),
            change_event=self._on_change_value,
        )
        if tooltip:
            self._fno_ctrl.SetToolTip(
                tooltip + __("\nEnterキーを押下したタイミングで値が反映されます。")
            )

        self._slider = wx.Slider(
            parent, wx.ID_ANY, 0, 0, self._max, position, size, wx.SL_HORIZONTAL
        )
        self._slider.Bind(wx.EVT_SCROLL, self._on_scroll)
        self._slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self._on_scroll_release)
        self._slider.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel_spin)
        if tooltip:
            self._slider.SetToolTip(
                tooltip
                + "\n"
                + __(
                    "マウスホイールでのスクロールは変更のあったキーフレに次々に飛びます"
                )
            )

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self._fno_ctrl, 0, wx.LEFT | wx.TOP | wx.BOTTOM, border)
        self.sizer.Add(self._slider, 0, wx.TOP | wx.RIGHT | wx.BOTTOM, border)

    def _on_scroll(self, event: wx.Event) -> None:
        self._fno_ctrl.SetValue(self._slider.GetValue())

    def _on_scroll_release(self, event: wx.Event) -> None:
        self.Enable(False)
        self._fno_ctrl.SetValue(self._slider.GetValue())

        if self._change_event:
            self._change_event(event)

        self.Enable(True)

    def _on_change_value(self, event: wx.Event) -> None:
        self.Enable(False)
        self._slider.SetValue(self._fno_ctrl.GetValue())

        if self._change_event:
            self._change_event(event)

        self.Enable(True)

    def _on_wheel_spin(self, event: wx.MouseEvent) -> None:
        """マウスホイールによるスピンコントロール"""
        if event.GetWheelRotation() > 0:
            vs = [f for f in self.key_fnos if f > self._slider.GetValue()]
            v = vs[0] if vs else self._max
        else:
            vs = [f for f in self.key_fnos if f < self._slider.GetValue()]
            v = vs[-1] if vs else 0
        self._fno_ctrl.SetValue(v)
        self._slider.SetValue(v)

    def SetValue(self, v: int) -> None:
        self._fno_ctrl.SetValue(v)
        self._on_change_value(wx.EVT_MOUSEWHEEL)

    def ChangeValue(self, v: int) -> None:
        self._fno_ctrl.SetValue(v)
        self._slider.SetValue(v)

    def GetValue(self) -> int:
        return self._slider.GetValue()

    def SetMaxFrameNo(self, fno: int) -> None:
        self._slider.SetMax(fno)

    def SetKeyFrames(self, key_fnos: list[int]) -> None:
        self.key_fnos = key_fnos

    def Add(
        self,
        parent_sizer: wx.Sizer,
        proportion: int,
        flag: int,
        border: int,
    ) -> None:
        self.sizer.Add(parent_sizer, proportion, flag, border)

    def Enable(self, enable: bool):
        self._fno_ctrl.Enable(enable)
        self._slider.Enable(enable)
