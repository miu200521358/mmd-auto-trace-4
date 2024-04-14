import os
from multiprocessing import Queue
from typing import Callable, Optional

import numpy as np
import OpenGL.GL as gl
import wx
from PIL import Image
from wx import glcanvas

from mlib.core.exception import MViewerException
from mlib.core.logger import MLogger
from mlib.core.math import MQuaternion, MVector3D
from mlib.core.process import MProcess
from mlib.pmx.pmx_collection import PmxModel
from mlib.pmx.pmx_part import ShaderMaterial
from mlib.pmx.shader import MShader
from mlib.service.form.base_frame import BaseFrame
from mlib.service.form.base_panel import BasePanel
from mlib.service.form.notebook_frame import NotebookFrame
from mlib.service.form.notebook_panel import NotebookPanel
from mlib.utils.file_utils import get_root_dir
from mlib.vmd.vmd_collection import VmdMotion
from mlib.vmd.vmd_tree import VmdBoneFrameTrees

logger = MLogger(os.path.basename(__file__), level=0)
__ = logger.get_text


class CanvasPanel(NotebookPanel):
    def __init__(
        self,
        frame: NotebookFrame,
        tab_idx: int,
        canvas_width_ratio: float,
        canvas_height_ratio: float,
        *args,
        **kw,
    ):
        super().__init__(frame, tab_idx)
        self.index = 0
        self.canvas_width_ratio = canvas_width_ratio
        self.canvas_height_ratio = canvas_height_ratio
        self.canvas = PmxCanvas(self, False)

    @property
    def fno(self) -> int:
        return self.index

    @fno.setter
    def fno(self, v: int) -> None:
        self.index = v

    def stop_play(self) -> None:
        pass

    def start_play(self) -> None:
        pass

    def get_canvas_size(self) -> wx.Size:
        w, h = self.frame.GetClientSize()
        canvas_width = w * self.canvas_width_ratio
        if canvas_width % 2 != 0:
            # 2で割り切れる値にする
            canvas_width += 1
        canvas_height = h * self.canvas_height_ratio
        return wx.Size(int(canvas_width), int(canvas_height))

    def on_resize(self, event: wx.Event):
        pass


def animate(queue: Queue, fno: int, max_fno: int, model_set: "ModelSet"):
    while fno < max_fno:
        fno += 1
        queue.put(MotionSet(model_set.model, model_set.motion, fno))
    queue.put(None)


MODEL_BONE_SELECT_COLORS = [
    np.array([0.6, 0, 1, 1]),
    np.array([0, 1, 0.6, 1]),
    np.array([1, 0.6, 0, 1]),
]


MODEL_BONE_UNSELECT_COLORS = [
    np.array([0.6, 0, 0, 1]),
    np.array([0, 0, 0.6, 1]),
    np.array([0, 0.6, 0, 1]),
]


class ModelSet:
    def __init__(
        self,
        model: PmxModel,
        motion: VmdMotion,
        bone_alpha: float = 1.0,
        is_sub: bool = False,
    ):
        self.model = model
        self.motion = motion
        self.bone_alpha = bone_alpha
        model.init_draw(is_sub)


class MotionSet:
    def __init__(self, model: PmxModel, motion: VmdMotion, fno: int) -> None:
        self.selected_bone_indexes: list[int] = []
        self.is_show_bone_weight: bool = False

        if motion is not None:
            (
                self.fno,
                self.gl_matrixes,
                self.bone_matrixes,
                self.vertex_morph_poses,
                self.after_vertex_morph_poses,
                self.uv_morph_poses,
                self.uv1_morph_poses,
                self.material_morphs,
            ) = motion.animate(fno, model)
        else:
            self.fno = 0
            self.gl_matrixes = np.array([np.eye(4) for _ in range(len(model.bones))])
            self.bone_matrixes = VmdBoneFrameTrees()
            self.vertex_morph_poses = np.array(
                [np.zeros(3) for _ in range(len(model.vertices))]
            )
            self.after_vertex_morph_poses = np.array(
                [np.zeros(3) for _ in range(len(model.vertices))]
            )
            self.uv_morph_poses = np.array(
                [np.zeros(4) for _ in range(len(model.vertices))]
            )
            self.uv1_morph_poses = np.array(
                [np.zeros(4) for _ in range(len(model.vertices))]
            )
            self.material_morphs = [
                ShaderMaterial(m, MShader.LIGHT_AMBIENT4) for m in model.materials
            ]

    def update_morphs(self, model: PmxModel, motion: VmdMotion, fno: int):
        self.vertex_morph_poses = motion.morphs.animate_vertex_morphs(fno, model)
        self.after_vertex_morph_poses = motion.morphs.animate_after_vertex_morphs(
            fno, model
        )
        self.uv_morph_poses = motion.morphs.animate_uv_morphs(fno, model, 0)
        self.uv1_morph_poses = motion.morphs.animate_uv_morphs(fno, model, 1)
        self.material_morphs = motion.morphs.animate_material_morphs(fno, model)

        (
            group_vertex_morph_poses,
            group_morph_bone_frames,
            group_materials,
        ) = motion.morphs.animate_group_morphs(fno, model, self.material_morphs)
        self.vertex_morph_poses += group_vertex_morph_poses
        self.material_morphs = group_materials


class PmxCanvas(glcanvas.GLCanvas):
    def __init__(self, parent: CanvasPanel, is_sub: bool, *args, **kw):
        attribList = (
            glcanvas.WX_GL_RGBA,
            glcanvas.WX_GL_DOUBLEBUFFER,
            glcanvas.WX_GL_DEPTH_SIZE,
            16,
            0,
        )
        self.parent = parent
        self.is_sub = is_sub
        self.size = self.parent.get_canvas_size()

        glcanvas.GLCanvas.__init__(
            self, parent, wx.ID_ANY, size=self.size, attribList=attribList
        )
        self.context = glcanvas.GLContext(self)
        self.last_pos = wx.Point(0, 0)
        self.now_pos = wx.Point(0, 0)
        self.fps = 30
        self.max_fno = 0
        self.color = [0, 0, 0]
        self.color_changed_event: Optional[Callable] = None

        self.set_context()

        self._initialize_ui()
        self._initialize_event()

        # カメラの位置
        self.camera_position = MShader.INITIAL_CAMERA_POSITION.copy()
        # カメラの補正位置
        self.camera_offset_position = MShader.INITIAL_CAMERA_OFFSET_POSITION.copy()
        # カメラの回転(eulerで扱う)
        self.camera_degrees = MVector3D()
        # 視野角
        self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
        # カメラの中央
        self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
        # 計算済みのカメラ位置
        self.result_camera_position: Optional[MVector3D] = None

        self.shader = MShader(
            self.size.width,
            self.size.height,
            self.camera_position,
            self.camera_offset_position,
            self.camera_degrees,
            self.look_at_center,
            self.vertical_degrees,
            self.aspect_ratio,
        )
        self.model_sets: list[ModelSet] = []
        self.animations: list[MotionSet] = []

        self.queues: list[Queue] = []
        self.processes: list[MProcess] = []

        # マウスドラッグフラグ
        self.is_drag = False

        # 再生中かどうかを示すフラグ
        self.playing = False
        # 録画中かどうかを示すフラグ
        self.recording = False

    @property
    def aspect_ratio(self) -> float:
        return float(self.size.width) / float(self.size.height)

    def _initialize_ui(self) -> None:
        gl.glClearColor(0.7, 0.7, 0.7, 1)

        # 再生タイマー
        self.play_timer = wx.Timer(self)

    def _initialize_event(self) -> None:
        # ペイントイベントをバインド
        self.Bind(wx.EVT_PAINT, self.on_paint)

        # ウィンドウサイズ変更イベントをバインド
        self.Bind(wx.EVT_SIZE, self.on_resize)

        # 背景を消すイベントをバインド
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)

        # タイマーイベントをバインド
        self.Bind(wx.EVT_TIMER, self.on_play_timer, self.play_timer)

        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mouse_wheel)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_mouse_left_down)
        self.Bind(wx.EVT_MIDDLE_DOWN, self.on_mouse_right_down)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_mouse_right_down)
        self.Bind(wx.EVT_MOTION, self.on_mouse_motion)
        self.Bind(wx.EVT_MIDDLE_UP, self.on_mouse_right_up)
        self.Bind(wx.EVT_RIGHT_UP, self.on_mouse_right_up)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def on_erase_background(self, event: wx.Event):
        # Do nothing, to avoid flashing on MSW (これがないとチラつくらしい）
        pass

    def on_resize(self, event: wx.Event):
        self.size = self.parent.get_canvas_size()
        self.SetSize(self.size)
        self.shader.fit(
            self.size.width,
            self.size.height,
            self.camera_position,
            self.camera_offset_position,
            self.camera_degrees,
            self.look_at_center,
            self.vertical_degrees,
            self.aspect_ratio,
        )
        self.parent.on_resize(event)

    def on_paint(self, event: wx.Event):
        try:
            self.draw()
            self.SwapBuffers()
        except MViewerException:
            error_msg = "ビューワーの描画に失敗しました。\n一度ツールを立ち上げ直して再度実行していただき、それでも解決しなかった場合、作者にご連絡下さい。"
            logger.critical(error_msg)

            self.clear_model_set()

            dialog = wx.MessageDialog(
                self.parent,
                __(error_msg),
                style=wx.OK,
            )
            dialog.ShowModal()
            dialog.Destroy()

            self.SwapBuffers()

    def set_context(self) -> None:
        self.SetCurrent(self.context)
        logger.test(f"parent: {self.parent}, canvas: {self}, context: {self.context}")

    def append_model_set(
        self,
        model: PmxModel,
        motion: VmdMotion,
        bone_alpha: float = 1.0,
        is_sub: bool = False,
    ):
        logger.test("append_model_set: model_sets")
        self.model_sets.append(ModelSet(model, motion, bone_alpha, is_sub))
        logger.test("append_model_set: animations")
        self.animations.append(MotionSet(model, motion, 0))
        logger.test("append_model_set: max_fno")
        self.max_fno = max([model_set.motion.max_fno for model_set in self.model_sets])

    def clear_model_set(self) -> None:
        if self.model_sets:
            del self.model_sets
            del self.animations
        self.model_sets = []
        self.animations = []

    def draw(self) -> None:
        logger.test(f"draw: parent: {self.parent}, canvas: {self} ------")
        self.set_context()
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        self.shader.update_camera(
            self.camera_position,
            self.camera_offset_position,
            self.camera_degrees,
            self.look_at_center,
            self.vertical_degrees,
            self.aspect_ratio,
            self.result_camera_position,
        )

        self.shader.msaa.bind()

        # 地面を描く
        self.draw_ground()

        # 透過度設定なしのメッシュを先に描画する
        for model_set, animation in zip(self.model_sets, self.animations):
            if model_set.model:
                logger.test(f"-- アニメーション描画(非透過): {model_set.model.name}")

                model_set.model.draw(
                    self.shader,
                    animation.gl_matrixes,
                    animation.vertex_morph_poses,
                    animation.after_vertex_morph_poses,
                    animation.uv_morph_poses,
                    animation.uv1_morph_poses,
                    animation.material_morphs,
                    False,
                    animation.is_show_bone_weight,
                    animation.selected_bone_indexes,
                    self.is_sub,
                )
        # その後透過度設定ありのメッシュを描画する
        for model_set, animation in zip(self.model_sets, self.animations):
            if model_set.model:
                logger.test(f"-- アニメーション描画(透過): {model_set.model.name}")

                model_set.model.draw(
                    self.shader,
                    animation.gl_matrixes,
                    animation.vertex_morph_poses,
                    animation.after_vertex_morph_poses,
                    animation.uv_morph_poses,
                    animation.uv1_morph_poses,
                    animation.material_morphs,
                    True,
                    animation.is_show_bone_weight,
                    animation.selected_bone_indexes,
                    self.is_sub,
                )
        self.shader.msaa.unbind()

        if not self.playing:
            # 再生中でなければボーン表示
            for model_set, animation, select_color, unselect_color in zip(
                self.model_sets,
                self.animations,
                MODEL_BONE_SELECT_COLORS,
                MODEL_BONE_UNSELECT_COLORS,
            ):
                if model_set.model:
                    logger.test(f"-- ボーン描画: {model_set.model.name}")

                    model_set.model.draw_bone(
                        self.shader,
                        animation.gl_matrixes,
                        select_color
                        * np.array([1, 1, 1, model_set.bone_alpha], dtype=np.float32),
                        unselect_color
                        * np.array([1, 1, 1, model_set.bone_alpha], dtype=np.float32),
                        np.array(
                            [
                                (
                                    1
                                    if bone_index in animation.selected_bone_indexes
                                    else 0
                                )
                                for bone_index in model_set.model.bones.indexes
                            ]
                        ),
                        self.is_sub,
                    )

    def draw_ground(self) -> None:
        """平面を描画する"""
        gl.glBegin(gl.GL_QUADS)
        gl.glColor4f(0.5, 0.5, 0.5, 0.5)
        gl.glVertex3f(-30.0, 0.0, -30.0)
        gl.glVertex3f(30.0, 0.0, -30.0)
        gl.glVertex3f(30.0, 0.0, 30.0)
        gl.glVertex3f(-30.0, 0.0, 30.0)
        gl.glEnd()

    def on_frame_forward(self, event: wx.Event):
        self.parent.fno = self.parent.fno + 1
        self.change_motion(event)

    def on_frame_back(self, event: wx.Event):
        self.parent.fno = max(0, self.parent.fno - 1)
        self.change_motion(event)

    def change_motion(
        self, event: wx.Event, is_bone_deform: bool = True, model_index: int = -1
    ):
        if is_bone_deform:
            if 0 > model_index:
                animations: list[MotionSet] = []
                for model_set in self.model_sets:
                    logger.test(f"change_motion: MotionSet: {model_set.model.name}")
                    animations.append(
                        MotionSet(
                            model_set.model,
                            model_set.motion,
                            self.parent.fno,
                        )
                    )
                self.animations = animations
            else:
                self.animations[model_index] = MotionSet(
                    self.model_sets[model_index].model,
                    self.model_sets[model_index].motion,
                    self.parent.fno,
                )
        else:
            for model_set, animation in zip(self.model_sets, self.animations):
                logger.test(f"change_motion: update_morphs: {model_set.model.name}")
                animation.update_morphs(
                    model_set.model, model_set.motion, self.parent.fno
                )

        if self.playing and self.max_fno <= self.parent.fno:
            # 最後まで行ったら止まる
            self.on_play(event)

        self.Refresh()

    def on_play(self, event: wx.Event, record: bool = False):
        self.playing = not self.playing
        if self.playing:
            logger.test("on_play ----------------------------------------")
            self.parent.start_play()
            self.max_fno = max(
                [model_set.motion.max_fno for model_set in self.model_sets]
            )
            self.recording = record
            logger.test(f"on_play model_sets[{len(self.model_sets)}]")
            for n, model_set in enumerate(self.model_sets):
                logger.test(f"on_play queue[{n}] append")
                self.queues.append(Queue())
                logger.test(f"on_play process[{n}] append")
                self.processes.append(
                    MProcess(
                        target=animate,
                        args=(
                            self.queues[-1],
                            self.parent.fno,
                            self.max_fno,
                            model_set,
                        ),
                        name="CalcProcess",
                    )
                )
            logger.test("on_play process start")
            for p in self.processes:
                p.start()
            logger.test("on_play timer start")
            self.play_timer.Start(1000 // self.fps)
        else:
            self.play_timer.Stop()
            self.recording = False
            self.clear_process()
            self.parent.stop_play()

    def clear_process(self) -> None:
        if 0 < len(self.processes):
            for p in self.processes:
                if p.is_alive():
                    p.terminate()
                del p
            self.processes = []
        if 0 < len(self.queues):
            for q in self.queues:
                del q
            self.queues = []

    def on_play_timer(self, event: wx.Event):
        logger.test(f"on_play_timer before: {self.parent.fno}")
        if 0 < len(self.queues):
            logger.test("on_play_timer wait")
            # 全てのキューが終わったら受け取る
            animations: list[MotionSet] = []
            for q in self.queues:
                animation = q.get()
                animations.append(animation)
            logger.test(f"on_play_timer append ({len(animations)})")

            if None in animations and self.processes:
                # アニメーションが終わったら再生をひっくり返す
                logger.test("reverse on_play")
                self.on_play(event)
                return

            if 0 < len(animations):
                logger.test(f"on_play_timer set animations ({len(animations)})")
                self.animations = animations

            if self.recording:
                self.on_capture(event)

            self.parent.fno = self.parent.fno + 1
            logger.test(f"on_play_timer after: {self.parent.fno}")
        self.Refresh()

    def on_reset(self, event: wx.Event):
        self.parent.fno = 0
        self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
        self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
        self.camera_degrees = MVector3D()
        self.camera_position = MShader.INITIAL_CAMERA_POSITION.copy()
        self.camera_offset_position = MShader.INITIAL_CAMERA_OFFSET_POSITION.copy()
        self.Refresh()

    def on_key_down(self, event: wx.Event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_NUMPAD1:
            # 真下から
            self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
            self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
            self.camera_degrees = MVector3D(-90, 0, 0)
            self.camera_offset_position = MVector3D(
                0, MShader.INITIAL_CAMERA_POSITION_Y, 0
            )
        elif keycode in [wx.WXK_NUMPAD2, wx.WXK_ESCAPE]:
            # 真正面から(=リセット)
            self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
            self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
            self.camera_degrees = MVector3D()
            self.camera_position = MShader.INITIAL_CAMERA_POSITION.copy()
            self.camera_offset_position = MShader.INITIAL_CAMERA_OFFSET_POSITION.copy()
        elif keycode == wx.WXK_NUMPAD6:
            # 左から
            self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
            self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
            self.camera_degrees = MVector3D(0, 90, 0)
            self.camera_offset_position = MVector3D()
        elif keycode == wx.WXK_NUMPAD4:
            # 右から
            self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
            self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
            self.camera_degrees = MVector3D(0, -90, 0)
            self.camera_offset_position = MVector3D()
        elif keycode == wx.WXK_NUMPAD8:
            # 真後ろから
            self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
            self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
            self.camera_degrees = MVector3D(0, 180, 0)
            self.camera_offset_position = MVector3D()
        elif keycode == wx.WXK_NUMPAD5:
            # 真上から
            self.vertical_degrees = MShader.INITIAL_VERTICAL_DEGREES
            self.look_at_center = MShader.INITIAL_LOOK_AT_CENTER_POSITION.copy()
            self.camera_degrees = MVector3D(90, 0, 0)
            self.camera_offset_position = MVector3D(
                0, MShader.INITIAL_CAMERA_POSITION_Y, -MShader.INITIAL_CAMERA_POSITION_Y
            )
        elif keycode in [
            wx.WXK_NUMPAD9,
            wx.WXK_RIGHT,
            wx.WXK_NUMPAD_RIGHT,
            wx.WXK_WINDOWS_RIGHT,
        ]:
            # キーフレを進める
            self.on_frame_forward(event)
        elif keycode in [
            wx.WXK_NUMPAD7,
            wx.WXK_LEFT,
            wx.WXK_NUMPAD_LEFT,
            wx.WXK_WINDOWS_LEFT,
        ]:
            # キーフレを戻す
            self.on_frame_back(event)
        elif keycode in [wx.WXK_NUMPAD7, wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN]:
            # キャプチャ
            self.on_capture(event)
        elif keycode in [wx.WXK_SPACE]:
            # 再生/停止
            self.on_play(event)
        else:
            event.Skip()
        self.Refresh()

    def on_capture(self, event: wx.Event):
        dc = wx.ClientDC(self)

        # キャプチャ画像のサイズを設定
        size = dc.GetSize()

        # キャプチャ用のビットマップを作成
        bitmap = wx.Bitmap(size[0], size[1])

        # キャプチャ
        memory_dc = wx.MemoryDC()
        memory_dc.SelectObject(bitmap)
        memory_dc.Blit(0, 0, size[0], size[1], dc, 0, 0)
        memory_dc.SelectObject(wx.NullBitmap)

        # PIL.Imageに変換
        pil_image = Image.new("RGB", (size[0], size[1]))
        pil_image.frombytes(bytes(bitmap.ConvertToImage().GetData()))

        # ImageをPNGファイルとして保存する
        file_path = os.path.join(
            get_root_dir(), "capture", f"{self.parent.fno:06d}.png"
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 画像をファイルに保存
        pil_image.save(file_path)

    def on_mouse_left_down(self, event: wx.MouseEvent):
        self.on_capture_color(event)

    def on_mouse_right_down(self, event: wx.MouseEvent):
        if not self.is_drag:
            self.now_pos = self.last_pos = event.GetPosition()
            self.is_drag = True
            self.CaptureMouse()

    def on_capture_color(self, event: wx.MouseEvent):
        x, y = event.GetPosition()

        # キャプチャ用のビットマップを作成
        dc = wx.ClientDC(self)
        bitmap = wx.Bitmap(1, 1)

        # キャプチャ
        memory_dc = wx.MemoryDC()
        memory_dc.SelectObject(bitmap)
        memory_dc.Blit(0, 0, 1, 1, dc, x, y)
        memory_dc.SelectObject(wx.NullBitmap)

        # PIL.Imageに変換
        pil_image = Image.new("RGB", (1, 1))
        pil_image.frombytes(bytes(bitmap.ConvertToImage().GetData()))
        self.color = np.array(pil_image).tolist()[0][0]
        if self.color_changed_event:
            self.color_changed_event()

    def on_mouse_right_up(self, event: wx.MouseEvent):
        if self.is_drag:
            self.is_drag = False
            self.ReleaseMouse()

    def on_mouse_motion(self, event: wx.MouseEvent) -> None:
        if self.is_drag and event.Dragging():
            self.now_pos = event.GetPosition()
            x = (self.now_pos.x - self.last_pos.x) * 0.02
            y = (self.now_pos.y - self.last_pos.y) * 0.02
            if event.MiddleIsDown():
                self.look_at_center += MQuaternion.from_euler_degrees(
                    self.camera_degrees
                ) * MVector3D(x, y, 0)

                self.camera_offset_position.x += x
                self.camera_offset_position.y += y
            elif event.RightIsDown():
                self.camera_degrees += MVector3D(y * 10, -x * 10, 0)
            self.last_pos = self.now_pos
            self.Refresh()

        elif event.LeftIsDown() and event.Dragging():
            self.on_capture_color(event)

    def on_mouse_wheel(self, event: wx.MouseEvent):
        unit_degree = 5.0 if event.ShiftDown() else 1.0 if event.ControlDown() else 2.5
        if 0 > event.GetWheelRotation():
            self.vertical_degrees += unit_degree
        else:
            self.vertical_degrees = max(1.0, self.vertical_degrees - unit_degree)
        self.Refresh()


class SyncSubCanvasWindow(BaseFrame):
    def __init__(
        self,
        parent: BaseFrame,
        parent_canvas: PmxCanvas,
        title: str,
        size: wx.Size,
        look_at_model_names: list[str],
        look_at_bone_names: list[list[str]],
        *args,
        **kw,
    ):
        super().__init__(parent.app, title, size, *args, parent=parent, **kw)
        self.panel = SyncSubCanvasPanel(
            self, parent_canvas, look_at_model_names, look_at_bone_names
        )

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event: wx.Event):
        # ウィンドウを破棄せずに非表示にする
        self.panel.timer.Stop()
        self.Hide()
        event.Skip()


class SyncSubCanvasPanel(BasePanel):
    def __init__(
        self,
        frame: BaseFrame,
        parent_canvas: PmxCanvas,
        look_at_model_names: list[str],
        look_at_bone_names: list[list[str]],
        *args,
        **kw,
    ):
        super().__init__(frame)
        self.canvas_width_ratio = 1.0
        self.canvas_height_ratio = 0.9

        self.canvas = PmxCanvas(self, True)
        self.parent_canvas = parent_canvas
        self.look_at_model_names = look_at_model_names
        self.look_at_bone_names = look_at_bone_names
        self.fno = -1

        self.canvas.vertical_degrees = 5

        self.root_sizer.Add(self.canvas, 0, wx.ALL, 0)

        self.canvas.clear_model_set()
        for model_set, animation in zip(
            self.parent_canvas.model_sets, self.parent_canvas.animations
        ):
            self.canvas.append_model_set(model_set.model, model_set.motion, 0.0, True)
            self.canvas.animations[-1] = animation

        self.btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.look_at_model_choice = wx.Choice(
            self,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.Size(150, -1),
            choices=look_at_model_names,
        )
        self.look_at_model_choice.Bind(wx.EVT_CHOICE, self.on_choice_model)
        self.look_at_model_choice.SetSelection(0)
        self.btn_sizer.Add(self.look_at_model_choice, 0, wx.ALL, 0)

        self.look_at_bone_choice = wx.Choice(
            self,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.Size(150, -1),
            choices=look_at_bone_names[0],
        )
        self.look_at_bone_choice.Bind(wx.EVT_CHOICE, self.on_choice_bone)
        self.btn_sizer.Add(self.look_at_bone_choice, 0, wx.ALL, 0)

        self.on_choice_model(wx.EVT_CHOICE)
        self.root_sizer.Add(self.btn_sizer, 0, wx.ALL, 0)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(100)

    def on_choice_model(self, event: wx.Event) -> None:
        model_idx = self.look_at_model_choice.GetSelection()

        self.look_at_bone_choice.Clear()
        self.look_at_bone_choice.AppendItems(self.look_at_bone_names[model_idx])

        initial_idxs = [
            i for i, n in enumerate(self.look_at_bone_names[model_idx]) if n == "頭"
        ]
        self.look_at_bone_choice.SetSelection(initial_idxs[0] if initial_idxs else 0)
        self.on_choice_bone(event)

    def on_choice_bone(self, event: wx.Event) -> None:
        self.refresh_animation(True)

    def on_timer(self, event) -> None:
        if self.frame.IsShown():
            self.refresh_animation(False)

    def refresh_animation(self, force: bool):
        for midx in range(len(self.canvas.model_sets)):
            self.canvas.animations[midx] = self.parent_canvas.animations[midx]
            if midx == self.look_at_model_choice.GetSelection():
                animation: MotionSet = self.canvas.animations[midx]
                if animation.fno != self.fno or force:
                    bone_name = self.look_at_bone_choice.GetStringSelection()
                    self.canvas.camera_degrees = (
                        animation.bone_matrixes[animation.fno, bone_name]
                        .global_matrix.inverse()
                        .to_quaternion()
                        .to_euler_degrees()
                    )
                    self.canvas.look_at_center = (
                        animation.bone_matrixes[animation.fno, bone_name].position
                    ).gl
                    self.canvas.result_camera_position = (
                        animation.bone_matrixes[animation.fno, bone_name].global_matrix
                        * MVector3D(0, 0, -30)
                    ).gl
                    self.fno = animation.fno
                    self.canvas.Refresh()

    def get_canvas_size(self) -> wx.Size:
        w, h = self.frame.GetClientSize()
        canvas_width = w * self.canvas_width_ratio
        if canvas_width % 2 != 0:
            # 2で割り切れる値にする
            canvas_width += 1
        canvas_height = h * self.canvas_height_ratio
        return wx.Size(int(canvas_width), int(canvas_height))

    def on_resize(self, event: wx.Event):
        pass


class AsyncSubCanvasWindow(BaseFrame):
    def __init__(
        self,
        parent: BaseFrame,
        title: str,
        size: wx.Size,
        look_at_model_names: list[str],
        look_at_bone_names: list[list[str]],
        *args,
        **kw,
    ):
        super().__init__(parent.app, title, size, *args, parent=parent, **kw)
        self.panel = AsyncSubCanvasPanel(self, look_at_model_names, look_at_bone_names)

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event: wx.Event):
        # ウィンドウを破棄せずに非表示にする
        self.Hide()
        event.Skip()


class AsyncSubCanvasPanel(BasePanel):
    def __init__(
        self,
        frame: BaseFrame,
        look_at_model_names: list[str],
        look_at_bone_names: list[list[str]],
        canvas_width_ratio: float = 1.0,
        canvas_height_ratio: float = 0.9,
        *args,
        **kw,
    ):
        super().__init__(frame)
        self.canvas_width_ratio = canvas_width_ratio
        self.canvas_height_ratio = canvas_height_ratio
        self.canvas = PmxCanvas(self, True)
        self.look_at_model_names = look_at_model_names
        self.look_at_bone_names = look_at_bone_names
        self.fno = -1

        self.canvas.vertical_degrees = 5

        self.root_sizer.Add(self.canvas, 0, wx.ALL, 0)

        self.btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.look_at_model_choice = wx.Choice(
            self,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.Size(150, -1),
            choices=look_at_model_names,
        )
        self.look_at_model_choice.Bind(wx.EVT_CHOICE, self.on_choice_model)
        self.look_at_model_choice.SetSelection(0)
        self.btn_sizer.Add(self.look_at_model_choice, 0, wx.ALL, 0)

        self.look_at_bone_choice = wx.Choice(
            self,
            wx.ID_ANY,
            wx.DefaultPosition,
            wx.Size(150, -1),
            choices=look_at_bone_names[0],
        )
        self.look_at_bone_choice.Bind(wx.EVT_CHOICE, self.on_choice_bone)
        self.btn_sizer.Add(self.look_at_bone_choice, 0, wx.ALL, 0)

        self.on_choice_model(wx.EVT_CHOICE)
        self.root_sizer.Add(self.btn_sizer, 0, wx.ALL, 0)

    def on_choice_model(self, event: wx.Event) -> None:
        model_idx = self.look_at_model_choice.GetSelection()

        self.look_at_bone_choice.Clear()
        self.look_at_bone_choice.AppendItems(self.look_at_bone_names[model_idx])

        initial_idxs = [
            i for i, n in enumerate(self.look_at_bone_names[model_idx]) if n == "頭"
        ]
        self.look_at_bone_choice.SetSelection(initial_idxs[0] if initial_idxs else 0)
        self.on_choice_bone(event)

    def on_choice_bone(self, event: wx.Event) -> None:
        for midx in range(len(self.canvas.model_sets)):
            if midx == self.look_at_model_choice.GetSelection():
                animation: MotionSet = self.canvas.animations[midx]
                bone_name = self.look_at_bone_choice.GetStringSelection()
                self.canvas.camera_degrees = (
                    animation.bone_matrixes[animation.fno, bone_name]
                    .global_matrix.inverse()
                    .to_quaternion()
                    .to_euler_degrees()
                )
                self.canvas.look_at_center = (
                    animation.bone_matrixes[animation.fno, bone_name].position
                ).gl
                self.canvas.result_camera_position = (
                    animation.bone_matrixes[animation.fno, bone_name].global_matrix
                    * MVector3D(0, 0, -30)
                ).gl
                self.fno = animation.fno
                self.canvas.Refresh()

    def get_canvas_size(self) -> wx.Size:
        w, h = self.frame.GetClientSize()
        canvas_width = w * self.canvas_width_ratio
        if canvas_width % 2 != 0:
            # 2で割り切れる値にする
            canvas_width += 1
        canvas_height = h * self.canvas_height_ratio
        return wx.Size(int(canvas_width), int(canvas_height))

    def on_resize(self, event: wx.Event):
        pass
