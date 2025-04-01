# controllers/transformation_controller.py
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QDialog

from models.point import Point
from models.line import Line
from models.polygon import Polygon
from dialogs.transformation_dialog import TransformationDialog
import transformations as tf

class TransformationController(QObject):
    """Gerencia a lógica para aplicar transformações aos objetos de dados."""

    object_transformed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

    def request_transformation(self, data_object: object):
        """
        Inicia o processo de transformação para o objeto de dados fornecido.
        Abre o diálogo para obter parâmetros e então aplica a transformação.
        """
        if not isinstance(data_object, (Point, Line, Polygon)):
            QMessageBox.warning(None, "Erro", "Tipo de objeto não suportado para transformação.")
            return

        dialog = TransformationDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_transformation_parameters()
            if params:
                self._perform_transformation(data_object, params)

    def _perform_transformation(self, data_object: object, params: dict):
        """Aplica a transformação baseada nos parâmetros ao objeto de dados."""
        try:
            if isinstance(data_object, Point):
                vertices = [data_object.get_coords()]
            elif isinstance(data_object, Line):
                vertices = data_object.get_coords()
            elif isinstance(data_object, Polygon):
                vertices = data_object.get_coords()
            else:
                return

            if not vertices:
                 raise ValueError("Objeto não possui vértices para transformar.")

            matrix = np.identity(3)
            transform_type = params.get('type')

            cx, cy = 0, 0
            if transform_type in ['scale_center', 'rotate_center']:
                 center = data_object.get_center()
                 if center is None:
                     raise ValueError("Não foi possível calcular o centro do objeto.")
                 cx, cy = center


            if transform_type == 'translate':
                matrix = tf.create_translation_matrix(params['dx'], params['dy'])
            elif transform_type == 'scale_center':
                T_to_origin = tf.create_translation_matrix(-cx, -cy)
                S = tf.create_scaling_matrix(params['sx'], params['sy'])
                T_back = tf.create_translation_matrix(cx, cy)
                matrix = T_back @ S @ T_to_origin
            elif transform_type == 'rotate_origin':
                matrix = tf.create_rotation_matrix(params['angle'])
            elif transform_type == 'rotate_center':
                T_to_origin = tf.create_translation_matrix(-cx, -cy)
                R = tf.create_rotation_matrix(params['angle'])
                T_back = tf.create_translation_matrix(cx, cy)
                matrix = T_back @ R @ T_to_origin
            elif transform_type == 'rotate_arbitrary':
                px, py = params['px'], params['py']
                T_to_origin = tf.create_translation_matrix(-px, -py)
                R = tf.create_rotation_matrix(params['angle'])
                T_back = tf.create_translation_matrix(px, py)
                matrix = T_back @ R @ T_to_origin
            else:
                 raise ValueError(f"Tipo de transformação desconhecido: {transform_type}")

            new_vertices = tf.apply_transformation(vertices, matrix)

            if isinstance(data_object, Point):
                if not new_vertices:
                    raise ValueError("A transformação resultou em vértices vazios para Ponto.")
                try:
                    new_x, new_y = new_vertices[0]
                    data_object.x = float(new_x)
                    data_object.y = float(new_y)
                except (IndexError, TypeError, ValueError) as e:
                    raise ValueError(f"Falha ao desempacotar vértices transformados para Ponto: {new_vertices}. Erro: {e}")
            elif isinstance(data_object, Line):
                data_object.start.x, data_object.start.y = new_vertices[0]
                data_object.end.x, data_object.end.y = new_vertices[1]
            elif isinstance(data_object, Polygon):
                if len(new_vertices) != len(data_object.points):
                     raise ValueError("Número de vértices transformados não corresponde ao original.")
                for i, p in enumerate(data_object.points):
                    p.x, p.y = new_vertices[i]

            self.object_transformed.emit(data_object)

        except Exception as e:
            QMessageBox.critical(None, "Erro na Transformação", f"Falha ao aplicar transformação: {e}")