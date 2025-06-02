# graphics_editor/controllers/transformation_controller.py
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QDialog, QWidget
from typing import Union, Optional, Dict, Any, List, Tuple

from ..models import Point, Line, Polygon, BezierCurve, BSplineCurve  # Modelos 2D
from ..models.ponto3d import Ponto3D  # Modelo 3D
from ..models.objeto3d import Objeto3D  # Modelo 3D
from ..dialogs.transformation_dialog import TransformationDialog
from ..utils import transformations as tf2d  # Transformações 2D
from ..utils import transformations_3d as tf3d  # Transformações 3D

# Tipos de objetos transformáveis
TransformableObject2D = Union[Point, Line, Polygon, BezierCurve, BSplineCurve]
TransformableObject3D = Union[Ponto3D, Objeto3D]  # Objeto3D contém Ponto3D
AnyTransformableObject = Union[TransformableObject2D, TransformableObject3D]

# Tuplas de tipos para checagem com isinstance
TRANSFORMABLE_TYPES_2D = (Point, Line, Polygon, BezierCurve, BSplineCurve)
TRANSFORMABLE_TYPES_3D = (Ponto3D, Objeto3D)


class TransformationController(QObject):
    """
    Controlador responsável por aplicar transformações geométricas a objetos 2D e 3D.
    """

    object_transformed = pyqtSignal(object)  # Emite o DataObject modificado

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parent_widget = parent

    def request_transformation(
        self, data_object: AnyTransformableObject, is_3d: bool
    ) -> None:
        """
        Inicia o processo de transformação para um objeto.
        Abre um diálogo para o usuário configurar os parâmetros e aplica a transformação.

        Args:
            data_object: Objeto (2D ou 3D) a ser transformado.
            is_3d: True se o objeto for 3D, False se for 2D.
        """
        valid_types = TRANSFORMABLE_TYPES_3D if is_3d else TRANSFORMABLE_TYPES_2D
        if not isinstance(data_object, valid_types):
            dim_str = "3D" if is_3d else "2D"
            QMessageBox.warning(
                self._parent_widget,
                "Tipo Inválido",
                f"Objeto '{type(data_object).__name__}' não suportado para transformação {dim_str}.",
            )
            return

        dialog = TransformationDialog(self._parent_widget, is_3d=is_3d)
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_transformation_parameters()
            if params:
                if is_3d:
                    self._perform_transformation_3d(data_object, params)
                else:
                    self._perform_transformation_2d(data_object, params)

    def _perform_transformation_2d(
        self, data_object: TransformableObject2D, params: Dict[str, Any]
    ) -> None:
        """Aplica uma transformação geométrica 2D ao objeto."""
        transform_type = params.get("type", "desconhecido")
        try:
            vertices_data = data_object.get_coords()
            vertices: List[Tuple[float, float]] = []
            if isinstance(vertices_data, tuple):
                vertices = [vertices_data]  # Ponto
            elif isinstance(vertices_data, list):
                vertices = vertices_data  # Linha/Polígono/Curva
            else:
                raise TypeError("get_coords() retornou tipo inesperado para 2D.")
            if not vertices:
                raise ValueError("Objeto 2D sem vértices.")

            center_x, center_y = 0.0, 0.0
            if transform_type in [
                "scale_center_2d",
                "rotate_center_2d",
                "rotate_arbitrary_2d",
            ]:
                center = data_object.get_center()
                if not isinstance(center, tuple) or len(center) != 2:
                    raise ValueError("get_center() retornou valor inválido para 2D.")
                center_x, center_y = center

            matrix = np.identity(3, dtype=float)  # Matriz homogênea 2D (3x3)
            if transform_type == "translate_2d":
                matrix = tf2d.create_translation_matrix(
                    params.get("dx", 0.0), params.get("dy", 0.0)
                )
            elif transform_type == "scale_center_2d":
                T_orig = tf2d.create_translation_matrix(-center_x, -center_y)
                S = tf2d.create_scaling_matrix(
                    params.get("sx", 1.0), params.get("sy", 1.0)
                )
                T_back = tf2d.create_translation_matrix(center_x, center_y)
                matrix = T_back @ S @ T_orig
            elif transform_type == "rotate_origin_2d":
                matrix = tf2d.create_rotation_matrix(params.get("angle", 0.0))
            elif transform_type == "rotate_center_2d":
                T_orig = tf2d.create_translation_matrix(-center_x, -center_y)
                R = tf2d.create_rotation_matrix(params.get("angle", 0.0))
                T_back = tf2d.create_translation_matrix(center_x, center_y)
                matrix = T_back @ R @ T_orig
            elif transform_type == "rotate_arbitrary_2d":
                px, py = params.get("px", 0.0), params.get("py", 0.0)
                T_pt = tf2d.create_translation_matrix(-px, -py)
                R = tf2d.create_rotation_matrix(params.get("angle", 0.0))
                T_back_pt = tf2d.create_translation_matrix(px, py)
                matrix = T_back_pt @ R @ T_pt
            else:
                raise ValueError(
                    f"Tipo de transformação 2D '{transform_type}' não implementado."
                )

            new_vertices = tf2d.apply_transformation(vertices, matrix)
            if len(new_vertices) != len(vertices):
                raise ValueError(
                    "Contagem de vértices 2D incompatível após transformação."
                )

            # Atualiza o DataObject 2D no local
            if isinstance(data_object, Point):
                if new_vertices:
                    data_object.x, data_object.y = new_vertices[0]
            elif isinstance(data_object, Line):
                if len(new_vertices) == 2:
                    data_object.start.x, data_object.start.y = new_vertices[0]
                    data_object.end.x, data_object.end.y = new_vertices[1]
            elif isinstance(data_object, (Polygon, BezierCurve, BSplineCurve)):
                if len(new_vertices) == len(data_object.points):
                    for i, p_obj in enumerate(data_object.points):
                        p_obj.x, p_obj.y = new_vertices[i]
                else:
                    raise ValueError(
                        f"Contagem de vértices incompatível para {type(data_object).__name__}."
                    )

            self.object_transformed.emit(data_object)

        except Exception as e:
            QMessageBox.critical(
                self._parent_widget,
                "Erro na Transformação 2D",
                f"Falha ao aplicar '{transform_type}' em {type(data_object).__name__}:\n{e}",
            )

    def _perform_transformation_3d(
        self, data_object: TransformableObject3D, params: Dict[str, Any]
    ) -> None:
        """Aplica uma transformação geométrica 3D ao objeto."""
        transform_type = params.get("type", "desconhecido")
        try:
            matrix = tf3d.create_identity_matrix_3d()  # Matriz homogênea 3D (4x4)

            if transform_type == "translate_3d":
                matrix = tf3d.create_translation_matrix_3d(
                    params.get("dx", 0.0), params.get("dy", 0.0), params.get("dz", 0.0)
                )

            elif transform_type == "scale_center_3d":
                center = (
                    data_object.get_center()
                )  # Assume que Objeto3D e Ponto3D têm get_center() -> Tuple[x,y,z]
                T_orig = tf3d.create_translation_matrix_3d(
                    -center[0], -center[1], -center[2]
                )
                S = tf3d.create_scaling_matrix_3d(
                    params.get("sx", 1.0), params.get("sy", 1.0), params.get("sz", 1.0)
                )
                T_back = tf3d.create_translation_matrix_3d(
                    center[0], center[1], center[2]
                )
                matrix = T_back @ S @ T_orig

            elif transform_type == "rotate_x_3d":
                matrix = tf3d.create_rotation_matrix_3d_x(params.get("angle", 0.0))
            elif transform_type == "rotate_y_3d":
                matrix = tf3d.create_rotation_matrix_3d_y(params.get("angle", 0.0))
            elif transform_type == "rotate_z_3d":
                matrix = tf3d.create_rotation_matrix_3d_z(params.get("angle", 0.0))

            elif transform_type == "rotate_arbitrary_axis_point_3d":
                angle = params.get("angle", 0.0)
                axis_vec = params.get(
                    "axis_vector", np.array([0, 0, 1.0])
                )  # Eixo Z como padrão
                px, py, pz = (
                    params.get("px", 0.0),
                    params.get("py", 0.0),
                    params.get("pz", 0.0),
                )

                T_to_pt_origin = tf3d.create_translation_matrix_3d(-px, -py, -pz)
                R_arb = tf3d.create_rotation_matrix_3d_arbitrary_axis(axis_vec, angle)
                T_back_from_pt_origin = tf3d.create_translation_matrix_3d(px, py, pz)
                matrix = T_back_from_pt_origin @ R_arb @ T_to_pt_origin
            else:
                raise ValueError(
                    f"Tipo de transformação 3D '{transform_type}' não implementado."
                )

            # Aplica a transformação
            if isinstance(data_object, Ponto3D):
                hom_coords = data_object.get_homogeneous_coords()
                transformed_hom_coords = matrix @ hom_coords
                data_object.set_from_homogeneous_coords(transformed_hom_coords)
            elif isinstance(data_object, Objeto3D):
                # Objeto3D tem um método para aplicar a matriz a todos os seus Ponto3D
                data_object.apply_transformation_matrix(matrix)

            self.object_transformed.emit(data_object)

        except Exception as e:
            QMessageBox.critical(
                self._parent_widget,
                "Erro na Transformação 3D",
                f"Falha ao aplicar '{transform_type}' em {type(data_object).__name__}:\n{e}",
            )
