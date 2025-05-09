"""
Módulo que implementa o controlador de transformações do editor gráfico.

Este módulo contém:
- TransformationController: Controlador responsável por aplicar transformações
  geométricas aos objetos gráficos (translação, escala, rotação)
"""

# graphics_editor/controllers/transformation_controller.py
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QDialog, QWidget

from typing import Union, Optional, Dict, Any, List, Tuple

# Importações relativas
from ..models import Point, Line, Polygon, BezierCurve  # Use __init__
from ..dialogs.transformation_dialog import TransformationDialog
from ..utils import transformations as tf

# Alias for types that can be transformed
TransformableObject = Union[Point, Line, Polygon, BezierCurve]
# Tuple of actual types for isinstance checks
TRANSFORMABLE_TYPES = (Point, Line, Polygon, BezierCurve)


class TransformationController(QObject):
    """
    Controlador responsável por aplicar transformações geométricas aos objetos.
    
    Este controlador gerencia:
    - Aplicação de transformações 2D (translação, escala, rotação)
    - Interação com o usuário para obter parâmetros de transformação
    - Validação e tratamento de erros durante as transformações
    - Sinalização de objetos transformados
    """

    object_transformed = pyqtSignal(object)  # Emits the modified DataObject

    def __init__(self, parent: Optional[QWidget] = None):
        """
        Inicializa o controlador de transformações.
        
        Args:
            parent: Widget pai para diálogos (opcional)
        """
        super().__init__(parent)
        self._parent_widget = parent

    def request_transformation(self, data_object: TransformableObject) -> None:
        """
        Inicia o processo de transformação para um objeto.
        
        Abre um diálogo para o usuário configurar os parâmetros da transformação
        e aplica a transformação se o usuário confirmar.
        
        Args:
            data_object: Objeto a ser transformado
        """
        # Validate object type using the tuple for cleaner check
        if not isinstance(data_object, TRANSFORMABLE_TYPES):
            QMessageBox.warning(
                self._parent_widget,
                "Tipo Inválido",
                f"Objeto '{type(data_object).__name__}' não suportado para transformação.",
            )
            return

        dialog = TransformationDialog(self._parent_widget)
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_transformation_parameters()
            if params:
                self._perform_transformation(data_object, params)

    def _perform_transformation(
        self, data_object: TransformableObject, params: Dict[str, Any]
    ) -> None:
        """
        Aplica uma transformação geométrica ao objeto.
        
        Args:
            data_object: Objeto a ser transformado
            params: Dicionário com os parâmetros da transformação:
                - type: Tipo de transformação ('translate', 'scale_center', 'rotate_origin', 'rotate_center', 'rotate_arbitrary')
                - dx, dy: Deslocamentos para translação
                - sx, sy: Fatores de escala
                - angle: Ângulo de rotação em graus
                - px, py: Ponto de rotação para rotação arbitrária
        """
        transform_type = params.get("type", "desconhecido")

        try:
            # 1. Extract vertices/control points
            try:
                vertices_data = data_object.get_coords()
                vertices: List[Tuple[float, float]] = []
                if isinstance(vertices_data, tuple):
                    vertices = [vertices_data]  # Point
                elif isinstance(vertices_data, list):
                    vertices = vertices_data  # Line/Polygon/Bezier
                else:
                    raise TypeError("get_coords() returned unexpected type.")
                if not vertices:
                    raise ValueError("Object has no vertices/control points.")
            except AttributeError:
                raise ValueError(
                    f"Object '{type(data_object).__name__}' missing 'get_coords'."
                )

            # 2. Calculate center (if needed)
            center_x, center_y = 0.0, 0.0
            if transform_type in ["scale_center", "rotate_center"]:
                try:
                    center = data_object.get_center()
                except AttributeError:  # Fallback if get_center is missing
                    if vertices:
                        center = (
                            sum(v[0] for v in vertices) / len(vertices),
                            sum(v[1] for v in vertices) / len(vertices),
                        )
                    else:
                        raise ValueError(
                            f"Cannot get center for object {type(data_object).__name__}."
                        )
                if not isinstance(center, tuple) or len(center) != 2:
                    raise ValueError("get_center() returned invalid value.")
                center_x, center_y = center

            # 3. Build transformation matrix
            matrix = np.identity(3, dtype=float)
            if transform_type == "translate":
                matrix = tf.create_translation_matrix(
                    params.get("dx", 0.0), params.get("dy", 0.0)
                )
            elif transform_type == "scale_center":
                T_to_origin = tf.create_translation_matrix(-center_x, -center_y)
                S = tf.create_scaling_matrix(
                    params.get("sx", 1.0), params.get("sy", 1.0)
                )
                T_back = tf.create_translation_matrix(center_x, center_y)
                matrix = T_back @ S @ T_to_origin
            elif transform_type == "rotate_origin":
                matrix = tf.create_rotation_matrix(params.get("angle", 0.0))
            elif transform_type == "rotate_center":
                T_to_origin = tf.create_translation_matrix(-center_x, -center_y)
                R = tf.create_rotation_matrix(params.get("angle", 0.0))
                T_back = tf.create_translation_matrix(center_x, center_y)
                matrix = T_back @ R @ T_to_origin
            elif transform_type == "rotate_arbitrary":
                px, py = params.get("px", 0.0), params.get("py", 0.0)
                T_to_point = tf.create_translation_matrix(-px, -py)
                R = tf.create_rotation_matrix(params.get("angle", 0.0))
                T_back_from_point = tf.create_translation_matrix(px, py)
                matrix = T_back_from_point @ R @ T_to_point
            else:
                raise ValueError(
                    f"Transformation type '{transform_type}' not implemented."
                )

            # 4. Apply transformation
            new_vertices = tf.apply_transformation(vertices, matrix)
            if len(new_vertices) != len(vertices):
                raise ValueError("Vertex count mismatch after transformation.")

            # 5. Update DataObject in-place
            if isinstance(data_object, Point):
                if new_vertices:
                    data_object.x, data_object.y = new_vertices[0]
            elif isinstance(data_object, Line):
                if len(new_vertices) == 2:
                    data_object.start.x, data_object.start.y = new_vertices[0]
                    data_object.end.x, data_object.end.y = new_vertices[1]
            elif isinstance(
                data_object, (Polygon, BezierCurve)
            ):  # Both store points in .points list
                if len(new_vertices) == len(data_object.points):
                    for i, p_obj in enumerate(data_object.points):
                        p_obj.x, p_obj.y = new_vertices[i]
                else:
                    raise ValueError(
                        f"Vertex count mismatch for {type(data_object).__name__}."
                    )

            # 6. Emit signal with the modified object
            self.object_transformed.emit(data_object)

        except (
            ValueError,
            TypeError,
            IndexError,
            KeyError,
            np.linalg.LinAlgError,
        ) as e:
            QMessageBox.critical(
                self._parent_widget,
                "Erro na Transformação",
                f"Falha ao aplicar '{transform_type}' em {type(data_object).__name__}:\n{e}",
            )
        except Exception as e:
            QMessageBox.critical(
                self._parent_widget,
                "Erro Inesperado",
                f"Erro durante a transformação de {type(data_object).__name__}:\n{e}",
            )
