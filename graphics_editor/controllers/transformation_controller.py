# graphics_editor/controllers/transformation_controller.py
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QDialog, QWidget

from typing import Union, Optional, Dict, Any

# Importações relativas
from ..models.point import Point
from ..models.line import Line
from ..models.polygon import Polygon
from ..dialogs.transformation_dialog import TransformationDialog
from .. import transformations as tf  # Módulo com funções de matriz

# Alias para tipos de dados transformáveis
TransformableObject = Union[Point, Line, Polygon]


class TransformationController(QObject):
    """
    Controlador para aplicar transformações 2D aos objetos de dados.
    """

    # Sinal emitido com o objeto de dados *modificado* após a transformação
    # Usa 'object' genérico devido a limitações do pyqtSignal com Union complexos
    # O slot receptor deve verificar o tipo real.
    object_transformed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parent_widget = parent  # Para diálogos modais

    def request_transformation(self, data_object: TransformableObject) -> None:
        """
        Inicia o processo de transformação para um objeto.
        Abre o diálogo e, se confirmado, chama _perform_transformation.
        """
        # Validação inicial do tipo de objeto
        if not isinstance(data_object, (Point, Line, Polygon)):
            QMessageBox.warning(
                self._parent_widget,
                "Tipo Inválido",
                f"Objeto '{type(data_object).__name__}' não suportado.",
            )
            return

        dialog = TransformationDialog(self._parent_widget)
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_transformation_parameters()
            if params:
                # Passa o objeto original para ser modificado
                self._perform_transformation(data_object, params)

    def _perform_transformation(
        self, data_object: TransformableObject, params: Dict[str, Any]
    ) -> None:
        """Aplica a transformação geométrica ao objeto de dados."""
        transform_type = params.get("type", "desconhecido")

        try:
            # 1. Extrai vértices
            try:
                # Point.get_coords retorna Tuple, Line/Polygon retorna List[Tuple]
                vertices_data = data_object.get_coords()
                vertices: List[Tuple[float, float]] = []
                if isinstance(vertices_data, tuple):  # É um Point
                    vertices = [vertices_data]
                elif isinstance(vertices_data, list):  # É Line ou Polygon
                    vertices = vertices_data
                else:
                    raise TypeError("Método get_coords() retornou tipo inesperado.")

                if not vertices:
                    raise ValueError("Objeto sem vértices válidos.")

            except AttributeError:
                raise ValueError(
                    f"Objeto '{type(data_object).__name__}' não tem 'get_coords'."
                )

            # 2. Calcula centro (se necessário)
            center_x, center_y = 0.0, 0.0
            if transform_type in ["scale_center", "rotate_center"]:
                try:
                    center = data_object.get_center()  # Usa método do modelo
                    if not isinstance(center, tuple) or len(center) != 2:
                        raise ValueError("Método get_center() retornou valor inválido.")
                    center_x, center_y = center
                except AttributeError:
                    raise ValueError(
                        f"Objeto '{type(data_object).__name__}' não tem 'get_center'."
                    )

            # 3. Constrói matriz de transformação
            matrix = np.identity(3, dtype=float)  # Começa com identidade
            T_to_origin = T_back = R = S = None  # Inicializa matrizes parciais

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
                matrix = T_back @ S @ T_to_origin  # Aplica da direita para esquerda
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
                    f"Tipo de transformação não implementado: '{transform_type}'"
                )

            # 4. Aplica transformação aos vértices
            new_vertices = tf.apply_transformation(vertices, matrix)

            if len(new_vertices) != len(vertices):
                raise ValueError(
                    "Transformação resultou em número diferente de vértices."
                )

            # 5. Atualiza o objeto de dados original (modificação in-place)
            if isinstance(data_object, Point):
                if new_vertices:
                    data_object.x, data_object.y = new_vertices[0]
                else:
                    raise ValueError("Transformação de Ponto falhou.")
            elif isinstance(data_object, Line):
                if len(new_vertices) == 2:
                    data_object.start.x, data_object.start.y = new_vertices[0]
                    data_object.end.x, data_object.end.y = new_vertices[1]
                else:
                    raise ValueError("Transformação de Linha falhou.")
            elif isinstance(data_object, Polygon):
                if len(new_vertices) == len(data_object.points):
                    for i, p_obj in enumerate(data_object.points):
                        p_obj.x, p_obj.y = new_vertices[i]
                else:
                    raise ValueError("Transformação de Polígono falhou.")

            # 6. Emite sinal com o objeto modificado
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
                f"Falha ao aplicar '{transform_type}':\n{e}",
            )
        except Exception as e:  # Erro inesperado
            QMessageBox.critical(
                self._parent_widget,
                "Erro Inesperado",
                f"Erro durante a transformação:\n{e}",
            )
