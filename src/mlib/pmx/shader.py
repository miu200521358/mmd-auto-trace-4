import os
from enum import IntEnum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import OpenGL.GL as gl
import OpenGL.GLU as glu

from mlib.core.exception import MViewerException
from mlib.core.math import MMatrix4x4, MQuaternion, MVector3D, MVector4D


class VsLayout(IntEnum):
    POSITION_ID = 0
    NORMAL_ID = 1
    UV_ID = 2
    EXTEND_UV_ID = 3
    EDGE_ID = 4
    BONE_ID = 5
    WEIGHT_ID = 6
    MORPH_POS_ID = 7
    MORPH_UV_ID = 8
    MORPH_UV1_ID = 9
    MORPH_AFTER_POS_ID = 10


class ProgramType(IntEnum):
    MODEL = 0
    EDGE = 1
    BONE = 2
    AXIS = 3


class Msaa:
    """
    MSAA(アンチエイリアス)
    https://blog.techlab-xe.net/opengl%E3%81%A7msaa/
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.msaa_samples = 4

        # MSAA用のフレームバッファオブジェクトを作成する
        self.msaa_buffer = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.msaa_buffer)

        # カラーバッファと深度バッファをMSAAで使うテクスチャに割り当てる
        self.msaa_color_buffer = gl.glGenRenderbuffers(1)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.msaa_color_buffer)
        gl.glRenderbufferStorageMultisample(
            gl.GL_RENDERBUFFER, self.msaa_samples, gl.GL_RGBA, self.width, self.height
        )
        gl.glFramebufferRenderbuffer(
            gl.GL_FRAMEBUFFER,
            gl.GL_COLOR_ATTACHMENT0,
            gl.GL_RENDERBUFFER,
            self.msaa_color_buffer,
        )

        self.msaa_depth_buffer = gl.glGenRenderbuffers(1)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.msaa_depth_buffer)
        gl.glRenderbufferStorageMultisample(
            gl.GL_RENDERBUFFER,
            self.msaa_samples,
            gl.GL_DEPTH_COMPONENT,
            self.width,
            self.height,
        )
        gl.glFramebufferRenderbuffer(
            gl.GL_FRAMEBUFFER,
            gl.GL_DEPTH_ATTACHMENT,
            gl.GL_RENDERBUFFER,
            self.msaa_depth_buffer,
        )

        # 描画先テクスチャのバインドを解除しておく
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

    def bind(self) -> None:
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # フレームバッファオブジェクトをバインドする
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.msaa_buffer)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

    def unbind(self) -> None:
        # フレームバッファオブジェクトの内容を画面に描画する
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self.msaa_buffer)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, 0)
        gl.glBlitFramebuffer(
            0,
            0,
            self.width,
            self.height,
            0,
            0,
            self.width,
            self.height,
            gl.GL_COLOR_BUFFER_BIT,
            gl.GL_NEAREST,
        )


class MShader:
    INITIAL_VERTICAL_DEGREES = 40.0
    INITIAL_CAMERA_POSITION_Y = 11.0
    INITIAL_CAMERA_POSITION_Z = -40.0
    INITIAL_LOOK_AT_CENTER_Y = INITIAL_CAMERA_POSITION_Y
    INITIAL_CAMERA_POSITION_X = 40.0
    LIGHT_AMBIENT4 = MVector4D(154 / 255, 154 / 255, 154 / 255, 1)
    INITIAL_CAMERA_POSITION = MVector3D(
        0.0,
        INITIAL_CAMERA_POSITION_Y,
        INITIAL_CAMERA_POSITION_Z,
    )
    INITIAL_CAMERA_OFFSET_POSITION = MVector3D()
    INITIAL_LOOK_AT_CENTER_POSITION = MVector3D(0.0, INITIAL_LOOK_AT_CENTER_Y, 0.0)

    def __init__(
        self,
        width: int,
        height: int,
        camera_position: MVector3D,
        camera_offset_position: MVector3D,
        camera_degrees: MVector3D,
        look_at_center: MVector3D,
        vertical_degrees: float,
        aspect_ratio: float,
    ) -> None:
        self.width = width
        self.height = height
        self.near_plane = 1
        self.far_plane = 100

        # light position
        self.light_position = MVector3D(
            -20, self.INITIAL_CAMERA_POSITION_Y * 2, self.INITIAL_CAMERA_POSITION_Z * 2
        )
        self.light_direction = (
            self.light_position * MVector3D(-1, -1, -1)
        ).normalized()

        self.bone_matrix_texture_uniform: dict[int, Any] = {}
        self.bone_matrix_texture_id: dict[int, Any] = {}
        self.bone_matrix_texture_width: dict[int, Any] = {}
        self.bone_matrix_texture_height: dict[int, Any] = {}
        self.model_view_matrix_uniform: dict[int, Any] = {}
        self.model_view_projection_matrix_uniform: dict[int, Any] = {}
        self.light_direction_uniform: dict[int, Any] = {}
        self.camera_vec_uniform: dict[int, Any] = {}
        self.diffuse_uniform: dict[int, Any] = {}
        self.ambient_uniform: dict[int, Any] = {}
        self.specular_uniform: dict[int, Any] = {}
        self.edge_color_uniform: dict[int, Any] = {}
        self.select_bone_color_uniform: dict[int, Any] = {}
        self.unselect_bone_color_uniform: dict[int, Any] = {}
        self.edge_size_uniform: dict[int, Any] = {}
        self.use_texture_uniform: dict[int, Any] = {}
        self.texture_uniform: dict[int, Any] = {}
        self.texture_factor_uniform: dict[int, Any] = {}
        self.use_toon_uniform: dict[int, Any] = {}
        self.toon_uniform: dict[int, Any] = {}
        self.toon_factor_uniform: dict[int, Any] = {}
        self.use_sphere_uniform: dict[int, Any] = {}
        self.sphere_mode_uniform: dict[int, Any] = {}
        self.sphere_uniform: dict[int, Any] = {}
        self.sphere_factor_uniform: dict[int, Any] = {}
        self.bone_count_uniform: dict[int, Any] = {}
        self.is_show_bone_weight_uniform: dict[int, Any] = {}
        self.show_bone_indexes_uniform: dict[int, Any] = {}

        # モデル描画シェーダー ------------------
        self.model_program = gl.glCreateProgram()
        self.compile(self.model_program, "model.vert", "model.frag", ProgramType.MODEL)

        # 初期化
        self.use(ProgramType.MODEL)
        self.initialize(self.model_program, ProgramType.MODEL)
        self.unuse()

        # エッジ描画シェーダー ------------------
        self.edge_program = gl.glCreateProgram()
        self.compile(self.edge_program, "edge.vert", "edge.frag", ProgramType.EDGE)

        # 初期化
        self.use(ProgramType.EDGE)
        self.initialize(self.edge_program, ProgramType.EDGE)
        self.unuse()

        # ボーン描画シェーダー ------------------
        self.bone_program = gl.glCreateProgram()
        self.compile(self.bone_program, "bone.vert", "bone.frag", ProgramType.BONE)

        # 初期化
        self.use(ProgramType.BONE)
        self.initialize(self.bone_program, ProgramType.BONE)
        self.unuse()

        # ローカル軸描画シェーダー ------------------
        self.axis_program = gl.glCreateProgram()
        self.compile(self.axis_program, "axis.vert", "axis.frag", ProgramType.AXIS)

        # 初期化
        self.use(ProgramType.AXIS)
        self.initialize(self.axis_program, ProgramType.AXIS)
        self.unuse()

        # フィット（両方）
        self.fit(
            self.width,
            self.height,
            camera_position,
            camera_offset_position,
            camera_degrees,
            look_at_center,
            vertical_degrees,
            aspect_ratio,
        )

    def __del__(self) -> None:
        if self.model_program:
            try:
                gl.glDeleteProgram(self.model_program)
            except Exception as e:
                raise MViewerException(
                    f"MShader glDeleteProgram Failure\n{self.model_program}", e
                )

        if self.edge_program:
            try:
                gl.glDeleteProgram(self.edge_program)
            except Exception as e:
                raise MViewerException(
                    f"MShader glDeleteProgram Failure\n{self.edge_program}", e
                )

        if self.bone_program:
            try:
                gl.glDeleteProgram(self.bone_program)
            except Exception as e:
                raise MViewerException(
                    f"MShader glDeleteProgram Failure\n{self.bone_program}", e
                )

    def load_shader(self, src: str, shader_type) -> int:
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, src)
        gl.glCompileShader(shader)
        error = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if error != gl.GL_TRUE:
            info = gl.glGetShaderInfoLog(shader)
            gl.glDeleteShader(shader)
            raise Exception(info)
        return shader

    def compile(
        self,
        program: Any,
        vertex_shader_name: str,
        fragments_shader_name: str,
        program_type: ProgramType,
    ) -> None:
        vertex_shader_src = Path(
            os.path.join(os.path.dirname(__file__), "glsl", vertex_shader_name)
        ).read_text(encoding="utf-8")
        if program_type in [ProgramType.MODEL, ProgramType.EDGE]:
            vertex_shader_src = vertex_shader_src % (
                VsLayout.POSITION_ID.value,
                VsLayout.NORMAL_ID.value,
                VsLayout.UV_ID.value,
                VsLayout.EXTEND_UV_ID.value,
                VsLayout.EDGE_ID.value,
                VsLayout.BONE_ID.value,
                VsLayout.WEIGHT_ID.value,
                VsLayout.MORPH_POS_ID.value,
                VsLayout.MORPH_UV_ID.value,
                VsLayout.MORPH_UV1_ID.value,
                VsLayout.MORPH_AFTER_POS_ID.value,
            )

        fragments_shader_src = Path(
            os.path.join(os.path.dirname(__file__), "glsl", fragments_shader_name)
        ).read_text(encoding="utf-8")

        vs = self.load_shader(vertex_shader_src, gl.GL_VERTEX_SHADER)
        if not vs:
            return
        fs = self.load_shader(fragments_shader_src, gl.GL_FRAGMENT_SHADER)
        if not fs:
            return
        gl.glAttachShader(program, vs)
        gl.glAttachShader(program, fs)
        gl.glLinkProgram(program)
        error = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
        if error != gl.GL_TRUE:
            info = gl.glGetShaderInfoLog(program)
            raise MViewerException(info)
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

    def initialize(self, program: Any, program_type: ProgramType) -> None:
        # light color
        # MMD Light Diffuse は必ず0
        self.light_diffuse = MVector3D()
        # MMDの照明色そのまま
        self.light_specular = self.LIGHT_AMBIENT4.xyz
        # light_diffuse == MMDのambient
        self.light_ambient4 = self.LIGHT_AMBIENT4

        # モデルビュー行列
        self.model_view_matrix_uniform[program_type.value] = gl.glGetUniformLocation(
            program, "modelViewMatrix"
        )

        # MVP行列
        self.model_view_projection_matrix_uniform[
            program_type.value
        ] = gl.glGetUniformLocation(program, "modelViewProjectionMatrix")

        # ボーン変形行列用テクスチャ

        # テクスチャを作成する
        self.bone_matrix_texture_id[program_type.value] = gl.glGenTextures(1)
        self.bone_matrix_texture_uniform[program_type.value] = gl.glGetUniformLocation(
            program, "boneMatrixTexture"
        )
        self.bone_matrix_texture_width[program_type.value] = gl.glGetUniformLocation(
            program, "boneMatrixWidth"
        )
        self.bone_matrix_texture_height[program_type.value] = gl.glGetUniformLocation(
            program, "boneMatrixHeight"
        )

        self.msaa = Msaa(self.width, self.height)

        if program_type == ProgramType.EDGE:
            # エッジシェーダーへの割り当て

            # エッジ設定
            self.edge_color_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "edgeColor"
            )
            self.edge_size_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "edgeSize"
            )
        if program_type == ProgramType.BONE:
            # 選択ボーン色
            self.select_bone_color_uniform[
                program_type.value
            ] = gl.glGetUniformLocation(program, "selectBoneColor")
            # 非選択ボーン色
            self.unselect_bone_color_uniform[
                program_type.value
            ] = gl.glGetUniformLocation(program, "unselectBoneColor")
            self.bone_count_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "boneCount"
            )
        else:
            # モデルシェーダーへの割り当て

            self.light_direction_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "lightDirection"
            )
            gl.glUniform3f(
                self.light_direction_uniform[program_type.value],
                *self.light_direction.vector,
            )

            # カメラの位置
            self.camera_vec_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "cameraPos"
            )

            # --------

            # マテリアル設定
            self.diffuse_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "diffuse"
            )
            self.ambient_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "ambient"
            )
            self.specular_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "specular"
            )

            # --------

            # テクスチャの設定
            self.use_texture_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "useTexture"
            )
            self.texture_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "textureSampler"
            )
            self.texture_factor_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "textureFactor"
            )

            # Toonの設定
            self.use_toon_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "useToon"
            )
            self.toon_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "toonSampler"
            )
            self.toon_factor_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "toonFactor"
            )

            # Sphereの設定
            self.use_sphere_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "useSphere"
            )
            self.sphere_mode_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "sphereMode"
            )
            self.sphere_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "sphereSampler"
            )
            self.sphere_factor_uniform[program_type.value] = gl.glGetUniformLocation(
                program, "sphereFactor"
            )

            # ウェイトの描写
            self.is_show_bone_weight_uniform[
                program_type.value
            ] = gl.glGetUniformLocation(program, "isShowBoneWeight")
            self.show_bone_indexes_uniform[
                program_type.value
            ] = gl.glGetUniformLocation(program, "showBoneIndexes")

    def update_camera(
        self,
        camera_position: MVector3D,
        camera_offset_position: MVector3D,
        camera_degrees: MVector3D,
        look_at_center: MVector3D,
        vertical_degrees: float,
        aspect_ratio: float,
        result_camera_position: Optional[MVector3D] = None,
    ) -> None:
        # 視野領域の決定
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        glu.gluPerspective(
            vertical_degrees,
            aspect_ratio,
            self.near_plane,
            self.far_plane,
        )

        self.projection_matrix = np.array(
            gl.glGetFloatv(gl.GL_PROJECTION_MATRIX), dtype=np.float32
        )
        camera_rotation = MQuaternion.from_euler_degrees(camera_degrees)

        # カメラ位置
        if result_camera_position is None:
            camera_mat = MMatrix4x4()
            camera_mat.translate(camera_offset_position)
            camera_mat.rotate(camera_rotation)
            camera_mat.translate(camera_position)
            result_camera_position = camera_mat * MVector3D()

            # カメラの上方向
            look_at_right = (camera_rotation * MVector3D(1, 0, 0)).normalized()
            look_at_up = look_at_right.cross(
                result_camera_position - look_at_center
            ).normalized()
        else:
            look_at_right = MVector3D(1, 0, 0)
            look_at_up = MVector3D(0, 1, 0)
        # print(
        #     f"camera_pos: {camera_pos}, camera_degrees: {self.camera_degrees}, camera_rotation: {camera_rotation.to_euler_degrees()}"
        #     + f", look_at_right: {look_at_right}, look_at_up: {look_at_up}, look_at_center: {self.look_at_center}"
        # )

        # 視点位置の決定
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        glu.gluLookAt(
            *result_camera_position.vector, *look_at_center.vector, *look_at_up.vector
        )

        model_view_matrix = np.array(
            gl.glGetFloatv(gl.GL_MODELVIEW_MATRIX), dtype=np.float32
        )
        model_view_projection_matrix = np.matmul(
            model_view_matrix, self.projection_matrix
        )

        for program_type in ProgramType:
            self.use(program_type)

            if result_camera_position is not None and program_type == ProgramType.MODEL:
                gl.glUniform3f(
                    self.camera_vec_uniform[program_type.value],
                    *result_camera_position.vector,
                )

            gl.glUniformMatrix4fv(
                self.model_view_matrix_uniform[program_type.value],
                1,
                gl.GL_FALSE,
                model_view_matrix,
            )

            gl.glUniformMatrix4fv(
                self.model_view_projection_matrix_uniform[program_type.value],
                1,
                gl.GL_FALSE,
                model_view_projection_matrix,
            )

            self.unuse()

    def fit(
        self,
        width: int,
        height: int,
        camera_position: MVector3D,
        camera_offset_position: MVector3D,
        camera_degrees: MVector3D,
        look_at_center: MVector3D,
        vertical_degrees: float,
        aspect_ratio: float,
    ) -> None:
        self.width = width
        self.height = height

        # MSAAも作り直し
        self.msaa = Msaa(width, height)

        # ビューポートの設定
        gl.glViewport(0, 0, self.width, self.height)

        self.update_camera(
            camera_position,
            camera_offset_position,
            camera_degrees,
            look_at_center,
            vertical_degrees,
            aspect_ratio,
        )

    def use(self, program_type: ProgramType) -> None:
        if program_type == ProgramType.MODEL:
            gl.glUseProgram(self.model_program)
        elif program_type == ProgramType.EDGE:
            gl.glUseProgram(self.edge_program)
        elif program_type == ProgramType.BONE:
            gl.glUseProgram(self.bone_program)
        elif program_type == ProgramType.AXIS:
            gl.glUseProgram(self.axis_program)

    def unuse(self) -> None:
        gl.glUseProgram(0)
