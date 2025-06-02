# graphics_editor/utils/transformations_3d.py
import numpy as np
import math
from typing import List, Tuple, Optional
from PyQt5.QtGui import QVector3D, QMatrix4x4, QQuaternion
from PyQt5.QtCore import QPointF

EPSILON = 1e-9


def create_identity_matrix_3d() -> np.ndarray:
    return np.identity(4, dtype=float)


def create_translation_matrix_3d(dx: float, dy: float, dz: float) -> np.ndarray:
    return np.array(
        [
            [1.0, 0.0, 0.0, dx],
            [0.0, 1.0, 0.0, dy],
            [0.0, 0.0, 1.0, dz],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def create_scaling_matrix_3d(sx: float, sy: float, sz: float) -> np.ndarray:
    if abs(sx) < EPSILON or abs(sy) < EPSILON or abs(sz) < EPSILON:
        return np.identity(4, dtype=float)
    return np.array(
        [
            [sx, 0.0, 0.0, 0.0],
            [0.0, sy, 0.0, 0.0],
            [0.0, 0.0, sz, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def create_rotation_matrix_3d_x(angle_degrees: float) -> np.ndarray:
    rad = math.radians(angle_degrees)
    c, s = math.cos(rad), math.sin(rad)
    return np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, c, -s, 0.0],
            [0.0, s, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def create_rotation_matrix_3d_y(angle_degrees: float) -> np.ndarray:
    rad = math.radians(angle_degrees)
    c, s = math.cos(rad), math.sin(rad)
    return np.array(
        [
            [c, 0.0, s, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [-s, 0.0, c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def create_rotation_matrix_3d_z(angle_degrees: float) -> np.ndarray:
    rad = math.radians(angle_degrees)
    c, s = math.cos(rad), math.sin(rad)
    return np.array(
        [
            [c, -s, 0.0, 0.0],
            [s, c, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def create_rotation_matrix_3d_arbitrary_axis(
    axis_vector: np.ndarray, angle_degrees: float
) -> np.ndarray:
    if not isinstance(axis_vector, np.ndarray) or axis_vector.shape != (3,):
        raise ValueError("axis_vector deve ser um array NumPy (3,)")
    norm = np.linalg.norm(axis_vector)
    if norm < EPSILON:
        return np.identity(4, dtype=float)
    ax, ay, az = axis_vector / norm
    q_axis = QVector3D(ax, ay, az)
    quaternion = QQuaternion.fromAxisAndAngle(q_axis, angle_degrees)
    m3x3_qt = quaternion.toRotationMatrix()
    np_rot3x3 = np.array(
        [
            [m3x3_qt.data()[0], m3x3_qt.data()[1], m3x3_qt.data()[2]],
            [m3x3_qt.data()[3], m3x3_qt.data()[4], m3x3_qt.data()[5]],
            [m3x3_qt.data()[6], m3x3_qt.data()[7], m3x3_qt.data()[8]],
        ],
        dtype=float,
    )
    rot4x4 = np.identity(4, dtype=float)
    rot4x4[:3, :3] = np_rot3x3
    return rot4x4


def apply_transformation_3d(
    vertices: List[Tuple[float, float, float]], matrix: np.ndarray
) -> List[Tuple[float, float, float]]:
    if not vertices:
        return []
    vertex_array = np.array(vertices, dtype=float)
    homogeneous_coords = np.hstack(
        [vertex_array, np.ones((len(vertices), 1), dtype=float)]
    )
    transformed_h = matrix @ homogeneous_coords.T
    transformed_h = transformed_h.T
    w_coords = transformed_h[:, 3]
    w_divisor = np.where(np.abs(w_coords) < EPSILON, 1.0, w_coords)
    transformed_cartesian = transformed_h[:, :3] / w_divisor[:, np.newaxis]
    return [tuple(coord) for coord in transformed_cartesian]


def create_view_matrix(vrp: QVector3D, target: QVector3D, vup: QVector3D) -> np.ndarray:
    z_axis_cam = (vrp - target).normalized()
    x_axis_cam = QVector3D.crossProduct(vup, z_axis_cam).normalized()
    y_axis_cam = QVector3D.crossProduct(z_axis_cam, x_axis_cam)
    R_view = np.array(
        [
            [x_axis_cam.x(), x_axis_cam.y(), x_axis_cam.z(), 0.0],
            [y_axis_cam.x(), y_axis_cam.y(), y_axis_cam.z(), 0.0],
            [z_axis_cam.x(), z_axis_cam.y(), z_axis_cam.z(), 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    T_view = np.array(
        [
            [1.0, 0.0, 0.0, -vrp.x()],
            [0.0, 1.0, 0.0, -vrp.y()],
            [0.0, 0.0, 1.0, -vrp.z()],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    view_matrix = R_view @ T_view
    return view_matrix


def create_orthographic_projection_matrix(
    left: float, right: float, bottom: float, top: float, near: float, far: float
) -> np.ndarray:
    if (
        abs(right - left) < EPSILON
        or abs(top - bottom) < EPSILON
        or abs(far - near) < EPSILON
    ):
        return np.identity(4, dtype=float)
    m = np.identity(4, dtype=float)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    return m


def create_perspective_projection_matrix(
    fov_y_degrees: float, aspect_ratio: float, near: float, far: float
) -> np.ndarray:
    if (
        near <= EPSILON
        or far <= EPSILON
        or abs(near - far) < EPSILON
        or aspect_ratio <= EPSILON
        or not (EPSILON < fov_y_degrees < 180.0 - EPSILON)
    ):
        return np.identity(4, dtype=float)
    tan_half_fov_y = math.tan(math.radians(fov_y_degrees) / 2.0)
    m = np.zeros((4, 4), dtype=float)
    m[0, 0] = 1.0 / (aspect_ratio * tan_half_fov_y)
    m[1, 1] = 1.0 / tan_half_fov_y
    m[2, 2] = -(far + near) / (far - near)
    m[2, 3] = -(2.0 * far * near) / (far - near)
    m[3, 2] = -1.0
    return m


def viewport_transform_matrix(
    scene_origin_x: float,
    scene_origin_y: float,
    scene_width: float,
    scene_height: float,
) -> np.ndarray:
    sx = scene_width / 2.0
    sy = -scene_height / 2.0
    tx = scene_origin_x + scene_width / 2.0
    ty = scene_origin_y + scene_height / 2.0
    sz = 0.5
    tz = 0.5
    return np.array(
        [
            [sx, 0.0, 0.0, tx],
            [0.0, sy, 0.0, ty],
            [0.0, 0.0, sz, tz],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def project_point_3d_to_qpointf(
    point3d_coords: Tuple[float, float, float],
    model_matrix: np.ndarray,
    view_matrix: np.ndarray,
    projection_matrix: np.ndarray,
    viewport_rect_params: Tuple[float, float, float, float],
) -> Optional[QPointF]:
    p_model_h = np.array(
        [point3d_coords[0], point3d_coords[1], point3d_coords[2], 1.0], dtype=float
    )
    p_world_h = model_matrix @ p_model_h
    p_view_h = view_matrix @ p_world_h
    p_clip_h = projection_matrix @ p_view_h
    w_clip = p_clip_h[3]
    if abs(w_clip) < EPSILON:
        return None
    ndc_x = p_clip_h[0] / w_clip
    ndc_y = p_clip_h[1] / w_clip
    ndc_z = p_clip_h[2] / w_clip
    if not (
        -1.0 - EPSILON <= ndc_x <= 1.0 + EPSILON
        and -1.0 - EPSILON <= ndc_y <= 1.0 + EPSILON
        and -1.0 - EPSILON <= ndc_z <= 1.0 + EPSILON
    ):
        if w_clip < -EPSILON:
            return None
        return None
    p_ndc_h_for_viewport = np.array([ndc_x, ndc_y, ndc_z, 1.0], dtype=float)
    vp_matrix = viewport_transform_matrix(
        viewport_rect_params[0],
        viewport_rect_params[1],
        viewport_rect_params[2],
        viewport_rect_params[3],
    )
    p_scene_h = vp_matrix @ p_ndc_h_for_viewport
    return QPointF(p_scene_h[0], p_scene_h[1])
