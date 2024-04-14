import os
from typing import Callable, Optional

import wx
from wx import adv as wx_adv

from mlib.core.logger import MLogger
from mlib.core.math import MVector2D
from mlib.utils.file_utils import get_path

logger = MLogger(os.path.basename(__file__))
__ = logger.get_text


class BezierCtrl:
    def __init__(
        self,
        frame: wx.Frame,
        parent: wx.Panel,
        size: wx.Size,
        change_event: Optional[Callable] = None,
    ):
        super().__init__()

        self.frame = frame
        self.parent = parent
        self.change_event = change_event

        self.sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 補間曲線パネル
        self.panel = BezierViewPanel(self.parent, size=size)
        self.sizer.Add(self.panel, 0, wx.ALL, 0)

        # 補間曲線値
        self.value_sizer = wx.GridBagSizer()

        # 開始X
        self.start_x_title = wx.StaticText(
            self.parent, wx.ID_ANY, __("開始X: "), wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.value_sizer.Add(self.start_x_title, (0, 0), (1, 1), wx.ALL, 3)
        self.start_x_ctrl = wx.SpinCtrl(
            self.parent,
            id=wx.ID_ANY,
            size=wx.Size(60, -1),
            value="20",
            min=0,
            max=127,
            initial=20,
        )
        self.start_x_ctrl.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.value_sizer.Add(self.start_x_ctrl, (0, 1), (1, 1), wx.ALL, 0)
        # 開始Y
        self.start_y_title = wx.StaticText(
            self.parent, wx.ID_ANY, __("開始Y: "), wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.value_sizer.Add(self.start_y_title, (1, 0), (1, 1), wx.ALL, 3)
        self.start_y_ctrl = wx.SpinCtrl(
            self.parent,
            id=wx.ID_ANY,
            size=wx.Size(60, -1),
            value="20",
            min=0,
            max=127,
            initial=20,
        )
        self.start_y_ctrl.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.value_sizer.Add(self.start_y_ctrl, (1, 1), (1, 1), wx.ALL, 0)
        # 終了X
        self.end_x_title = wx.StaticText(
            self.parent, wx.ID_ANY, __("終了X: "), wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.value_sizer.Add(self.end_x_title, (2, 0), (1, 1), wx.ALL, 3)
        self.end_x_ctrl = wx.SpinCtrl(
            self.parent,
            id=wx.ID_ANY,
            size=wx.Size(60, -1),
            value="107",
            min=0,
            max=127,
            initial=107,
        )
        self.end_x_ctrl.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.value_sizer.Add(self.end_x_ctrl, (2, 1), (1, 1), wx.ALL, 0)
        # 終了Y
        self.end_y_title = wx.StaticText(
            self.parent, wx.ID_ANY, __("終了Y: "), wx.DefaultPosition, wx.DefaultSize, 0
        )
        self.value_sizer.Add(self.end_y_title, (3, 0), (1, 1), wx.ALL, 3)
        self.end_y_ctrl = wx.SpinCtrl(
            self.parent,
            id=wx.ID_ANY,
            size=wx.Size(60, -1),
            value="107",
            min=0,
            max=127,
            initial=107,
        )
        self.end_y_ctrl.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.value_sizer.Add(self.end_y_ctrl, (3, 1), (1, 1), wx.ALL, 0)

        self.template_ctrl = wx_adv.BitmapComboBox(self.parent, style=wx.CB_READONLY)
        for i in range(1, 8):
            self.template_ctrl.Append(
                f"{i:02d}", self.create_bitmap(f"mlib/resources/bezier/{i:02d}.png")
            )
        self.template_ctrl.Bind(wx.EVT_COMBOBOX, self.on_select)
        self.template_ctrl.SetToolTip(__("選択された補間曲線をパネルに設定します"))
        self.value_sizer.Add(self.template_ctrl, (4, 0), (1, 2), wx.ALL, 0)

        self.sizer.Add(self.value_sizer, 0, wx.ALL, 0)

        # ベジェ曲線描画
        self.panel.Bind(wx.EVT_PAINT, self.on_paint)
        self.panel.Bind(wx.EVT_LEFT_DOWN, self.on_paint_bezier_mouse_left_down)
        self.panel.Bind(wx.EVT_LEFT_UP, self.on_paint_bezier_mouse_left_up)
        self.panel.Bind(wx.EVT_MOTION, self.on_paint_bezier_mouse_motion)

    def create_bitmap(self, path: str) -> wx.Bitmap:
        # 画像を読み込む
        image = wx.Image(os.path.abspath(get_path(path)), wx.BITMAP_TYPE_ANY)

        # リサイズした画像をビットマップに変換
        bitmap = image.ConvertToBitmap()

        return bitmap

    def on_select(self, event: wx.Event):
        template_idx = self.template_ctrl.GetSelection()
        if template_idx == 0:
            self.start_x_ctrl.SetValue(20)
            self.start_y_ctrl.SetValue(20)
            self.end_x_ctrl.SetValue(107)
            self.end_y_ctrl.SetValue(107)
        elif template_idx == 1:
            self.start_x_ctrl.SetValue(50)
            self.start_y_ctrl.SetValue(0)
            self.end_x_ctrl.SetValue(77)
            self.end_y_ctrl.SetValue(127)
        elif template_idx == 2:
            self.start_x_ctrl.SetValue(80)
            self.start_y_ctrl.SetValue(0)
            self.end_x_ctrl.SetValue(47)
            self.end_y_ctrl.SetValue(127)
        elif template_idx == 3:
            self.start_x_ctrl.SetValue(40)
            self.start_y_ctrl.SetValue(40)
            self.end_x_ctrl.SetValue(67)
            self.end_y_ctrl.SetValue(127)
        elif template_idx == 4:
            self.start_x_ctrl.SetValue(50)
            self.start_y_ctrl.SetValue(0)
            self.end_x_ctrl.SetValue(77)
            self.end_y_ctrl.SetValue(77)
        elif template_idx == 5:
            self.start_x_ctrl.SetValue(0)
            self.start_y_ctrl.SetValue(60)
            self.end_x_ctrl.SetValue(67)
            self.end_y_ctrl.SetValue(127)
        elif template_idx == 6:
            self.start_x_ctrl.SetValue(60)
            self.start_y_ctrl.SetValue(0)
            self.end_x_ctrl.SetValue(127)
            self.end_y_ctrl.SetValue(67)
        self.on_change(event)

    def on_change(self, event: wx.Event):
        self.frame.Refresh(False)  # 描画更新

        if self.change_event:
            self.change_event(event)

    # ベジェ曲線の描画 -------------------------
    def on_paint(self, event: wx.Event):
        # 画面に表示されないところで描画を行うためのデバイスコンテキストを作成
        dc = wx.BufferedDC(wx.PaintDC(self.panel))
        mapper = Mapper(self.panel.GetSize(), MVector2D(0, 0), MVector2D(127, 127))
        target_point = [
            MVector2D(0, 0),
            MVector2D(self.start_x_ctrl.GetValue(), self.start_y_ctrl.GetValue()),
            MVector2D(self.end_x_ctrl.GetValue(), self.end_y_ctrl.GetValue()),
            MVector2D(127, 127),
        ]

        self.clear_bezier(dc)
        # self.draw_grid(m, dc)
        self.draw_guide(
            target_point[0],
            target_point[1],
            self.start_x_ctrl,
            self.start_y_ctrl,
            mapper,
            dc,
        )
        self.draw_guide(
            target_point[2],
            target_point[3],
            self.end_x_ctrl,
            self.end_y_ctrl,
            mapper,
            dc,
        )
        self.draw_bezier(target_point, mapper, dc)
        self.draw_bezier_error(mapper, dc)

    def clear_bezier(self, dc: wx.BufferedDC):
        self.set_color(dc, "white")
        dc.DrawRectangle(0, 0, *self.panel.GetSize())

    def draw_bezier(
        self, target_point: list[MVector2D], mapper: "Mapper", dc: wx.BufferedDC
    ):
        # draw bezier cupper_right ve
        self.set_color(dc, "blue")
        # dc.DrawPointList([m.to_client(x, y) for x, y in Bezier(target_ctrl)])
        lines = list(BezierLine(target_point))
        dc.DrawLineList(
            [mapper.fit(p) + mapper.fit(q) for p, q in zip(lines, lines[1:])]
        )

    def draw_guide(
        self,
        target_ctrl_start: MVector2D,
        target_ctrl_end: MVector2D,
        target_x_ctrl: wx.SpinCtrl,
        target_y_ctrl: wx.SpinCtrl,
        mapper: "Mapper",
        dc: wx.BufferedDC,
    ):
        #
        self.set_color(dc, "black")
        dc.DrawLine(*mapper.fit(target_ctrl_start) + mapper.fit(target_ctrl_end))

        # draw control points
        self.set_color(dc, "red")
        pnt = BezierPoint(
            *mapper.fit(target_x_ctrl.GetValue(), target_y_ctrl.GetValue()),
            target_x_ctrl,
            target_y_ctrl,
            self.change_event,
        )
        self.panel.append_point(pnt)
        pnt.draw(dc, True)

    def draw_grid(self, mapper: "Mapper", dc: wx.BufferedDC):
        xs, ys = mapper.lower_left
        xe, ye = mapper.upper_right

        self.set_color(dc, "black")
        dc.DrawLine(*mapper.fit(xs, 0) + mapper.fit(xe, 0))
        dc.DrawLine(*mapper.fit(0, ys) + mapper.fit(0, ye))

        dc.SetFont(self.panel.GetFont())
        dc.DrawText("%+d" % xs, *mapper.fit(xs, 0))
        dc.DrawText("%+d" % ye, *mapper.fit(0, ye))

    def draw_bezier_error(self, mapper: "Mapper", dc: wx.BufferedDC):
        if self.panel.is_error:
            xe, ye = mapper.upper_right

            self.set_color(dc, "red", 5)
            dc.DrawLine(*mapper.fit(0, 0) + mapper.fit(xe, ye))
            dc.DrawLine(*mapper.fit(0, ye) + mapper.fit(xe, 0))

    def set_color(self, dc: wx.BufferedDC, color: str, width: int = 1):
        dc.SetPen(wx.Pen(wx.Colour(color), width))
        dc.SetBrush(wx.Brush(color))

    def on_paint_bezier_mouse_left_down(self, event: wx.MouseEvent):
        """マウスの左ボタンが押された時の処理"""
        position = event.GetPosition()  # マウス座標を取得
        bezier_point = self.find_bezier_point(
            position
        )  # マウス座標と重なってるオブジェクトを取得
        if bezier_point is not None:
            self.panel.drag_point = bezier_point  # ドラッグ移動するオブジェクトを記憶
            self.panel.drag_start_pos = position  # ドラッグ開始時のマウス座標を記録
            self.panel.drag_point.save_point_diff(position)

    def on_paint_bezier_mouse_left_up(self, event: wx.MouseEvent):
        """マウスの左ボタンが離された時の処理"""
        if self.panel.drag_point is not None:
            pos: wx.Point = event.GetPosition()
            self.panel.drag_point.point.x = pos.x + self.panel.drag_point.diff_point.x
            self.panel.drag_point.point.y = pos.y + self.panel.drag_point.diff_point.y
            self.panel.drag_point.update_position()

        self.panel.drag_point = None
        self.frame.Refresh(False)

    def on_paint_bezier_mouse_motion(self, event: wx.MouseEvent):
        """マウスカーソルが動いた時の処理"""
        if self.panel.drag_point is None:
            # ドラッグしてるオブジェクトが無いなら処理しない
            return

        # ドラッグしてるオブジェクトの座標値をマウス座標で更新
        pos: wx.Point = event.GetPosition()
        self.panel.drag_point.point.x = pos.x + self.panel.drag_point.diff_point.x
        self.panel.drag_point.point.y = pos.y + self.panel.drag_point.diff_point.y
        self.panel.drag_point.update_position()
        self.frame.Refresh(False)  # 描画更新

    def find_bezier_point(self, point: wx.Point) -> Optional["BezierPoint"]:
        """マウス座標と重なってるオブジェクトを返す"""
        result = None
        for panel_point in self.panel.points:
            if panel_point.hit_test(point):
                result = panel_point
        return result


def pt(p: MVector2D, q: MVector2D, t: float) -> MVector2D:
    assert 0 <= t <= 1
    return MVector2D(*[a + (b - a) * float(t) for a, b in zip(p.vector, q.vector)])


def mid(p: MVector2D, q: MVector2D) -> MVector2D:
    return pt(p, q, 0.5)


class BezierLine:
    def __init__(self, points: list[MVector2D], dt=3 * 1e-3):
        self.points = points
        self.dt = dt

    def __iter__(self):
        points = self.points
        dt = self.dt

        t = 0
        while t <= 1:
            x, y = self.walk_down(points, t).vector
            yield x, y
            t += dt

    def walk_down(self, points: list[MVector2D], t: float) -> MVector2D:
        if len(points) == 1:
            return points[0]
        else:
            ps = [pt(p, q, t) for p, q in zip(points, points[1:])]
            return self.walk_down(ps, t)


class Mapper:
    def __init__(
        self, size: wx.Size, lower_left: MVector2D, upper_right: MVector2D
    ) -> None:
        self.size = size
        self.lower_left = lower_left.vector
        self.upper_right = upper_right.vector

    def fit(self, vx: float | MVector2D, vy: float = 0.0) -> tuple[int, int]:
        w, h = self.size
        xs, ys = self.lower_left
        xe, ye = self.upper_right

        if isinstance(vx, MVector2D):
            x = vx.x
            y = vx.y
        elif isinstance(vx, tuple):
            x = vx[0]
            y = vx[1]
        else:
            x = vx
            y = vy

        xx, yy = x - xs, y - ys
        xp, yp = (xe - xs) / w, (ye - ys) / h
        xn, yn = xx / xp, h - yy / yp
        # print x,y,'=>',xn,yn
        return int(xn), int(yn)


class BezierPoint:
    """マウスドラッグで移動できるオブジェクト用のクラス"""

    def __init__(
        self,
        x: float,
        y: float,
        target_x_ctrl: wx.SpinCtrl,
        target_y_ctrl: wx.SpinCtrl,
        change_event: Optional[Callable] = None,
    ) -> None:
        """コンストラクタ"""
        self.size = 2
        self.point = MVector2D(x, y)  # 表示位置を記録
        self.diff_point = MVector2D(0, 0)
        self.target_x_ctrl = target_x_ctrl
        self.target_y_ctrl = target_y_ctrl
        self.change_event = change_event

    def hit_test(self, point: wx.Point) -> bool:
        """与えられた座標とアタリ判定して結果を返す"""
        rect = self.get_rect()  # 矩形領域を取得

        # 座標が矩形内に入ってるか調べる
        return rect.x - 5 <= point.x < (
            rect.x + rect.width + 5
        ) and rect.y - 5 <= point.y < (rect.y + rect.height + 5)

    def get_rect(self) -> wx.Rect:
        """矩形領域を返す"""
        return wx.Rect(int(self.point.x), int(self.point.y), self.size, self.size)

    def save_point_diff(self, point: wx.Point) -> None:
        """
        マウス座標と自分の座標の相対値を記録。MVector2D
        この情報がないと、画像をドラッグした時の表示位置がしっくりこない
        """
        self.diff_point.x = self.point.x - point.x
        self.diff_point.y = self.point.y - point.y

    def draw(self, dc: wx.BufferedDC, selectable: bool) -> None:
        rect = self.get_rect()  # 矩形領域を取得

        if selectable:
            # 丸を描画
            dc.DrawCircle(rect.x, rect.y, self.size)

    def update_position(self) -> None:
        self.target_x_ctrl.SetValue(int(self.point.x))
        self.target_y_ctrl.SetValue(int(127 - self.point.y))

        if self.change_event:
            self.change_event(wx.EVT_MOUSE_EVENTS)


class BezierViewPanel(wx.Panel):
    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.TAB_TRAVERSAL,
        name=wx.PanelNameStr,
    ) -> None:
        super(BezierViewPanel, self).__init__(
            parent, id=id, pos=pos, size=size, style=style, name=name
        )
        self.points: list[BezierPoint] = []
        self.drag_point: Optional[BezierPoint] = None
        self.drag_start_pos = MVector2D(0, 0)
        self.is_error = False

    def append_point(self, point: "BezierPoint") -> None:
        self.points.append(point)
