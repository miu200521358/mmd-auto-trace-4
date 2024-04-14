import wx


class WheelSpinCtrl(wx.SpinCtrl):
    def __init__(self, *args, **kw) -> None:
        change_event = kw.pop("change_event", None)
        style = wx.TE_PROCESS_ENTER | kw.pop("style", 0)

        spin_event = kw.pop("spin_event", None)
        self.spin_event = spin_event

        enter_event = kw.pop("enter_event", None)
        self.enter_event = enter_event

        super().__init__(*args, **kw, style=style)
        self.change_event = change_event

        self.Bind(wx.EVT_SPINCTRL, self.on_spin)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter)

    def on_spin(self, event: wx.Event) -> None:
        if self.GetValue() >= 0:
            self.SetBackgroundColour("WHITE")
        else:
            self.SetBackgroundColour("TURQUOISE")

        if self.change_event:
            self.change_event(event)

        if self.spin_event:
            self.spin_event(event)

    def on_text_enter(self, event: wx.Event) -> None:
        self.SetFocus()
        if self.change_event:
            self.change_event(event)

        if self.enter_event:
            self.enter_event(event)


class WheelSpinCtrlDouble(wx.SpinCtrlDouble):
    def __init__(self, *args, **kw) -> None:
        change_event = kw.pop("change_event", None)
        style = wx.TE_PROCESS_ENTER | kw.pop("style", 0)

        super().__init__(*args, **kw, style=style)
        self.change_event = change_event

        spin_event = kw.pop("spin_event", None)
        self.spin_event = spin_event

        enter_event = kw.pop("enter_event", None)
        self.enter_event = enter_event

        self.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_spin)
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_wheel_spin)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_text_enter)

    def on_wheel_spin(self, event: wx.MouseEvent) -> None:
        """マウスホイールによるスピンコントロール"""
        if event.GetWheelRotation() > 0:
            self.SetValue(self.GetValue() + self.GetIncrement())
        else:
            self.SetValue(self.GetValue() - self.GetIncrement())
        self.on_spin(event)

    def on_spin(self, event: wx.Event) -> None:
        if self.GetValue() >= 0:
            self.SetBackgroundColour("WHITE")
        else:
            self.SetBackgroundColour("TURQUOISE")

        if self.change_event:
            self.change_event(event)

        if self.spin_event:
            self.spin_event(event)

    def on_text_enter(self, event: wx.Event) -> None:
        self.SetFocus()
        if self.change_event:
            self.change_event(event)

        if self.enter_event:
            self.enter_event(event)
