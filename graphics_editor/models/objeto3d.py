# graphics_editor/models/objeto3d.py
from typing import List, Tuple, Optional
from PyQt5.QtGui import QColor, QPainterPath, QPen
from PyQt5.QtCore import Qt, QLineF
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItem
import numpy as np

from .ponto3d import Ponto3D


class Objeto3D:
    """
    Representa um objeto 3D como um modelo de arame (wireframe).

    Esta classe é responsável por:
    - Armazenar uma lista de segmentos de reta, cada um definido por um par de Ponto3D.
    - Gerenciar o nome e a cor do objeto.
    - Aplicar transformações geométricas 3D ao objeto.
    - Criar uma representação gráfica 2D (QGraphicsPathItem) a partir de linhas projetadas.
    """

    GRAPHICS_LINE_WIDTH = 1.5  # Espessura das linhas projetadas na cena 2D

    def __init__(
        self,
        name: str,
        segments: List[Tuple[Ponto3D, Ponto3D]],
        color: Optional[QColor] = None,
    ):
        """
        Inicializa um Objeto3D.

        Args:
            name: Nome do objeto.
            segments: Lista de tuplas, onde cada tupla contém dois Ponto3D definindo um segmento.
            color: Cor do objeto (opcional, padrão é preto).
        """
        self.name: str = name
        self.segments: List[Tuple[Ponto3D, Ponto3D]] = segments
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def get_all_points(self) -> List[Ponto3D]:
        """
        Retorna uma lista de todos os Ponto3D únicos que compõem o objeto.

        Returns:
            List[Ponto3D]: Lista de pontos únicos.
        """
        unique_points_map = {id(p): p for seg in self.segments for p in seg}
        return list(unique_points_map.values())

    def get_coords(self) -> List[Tuple[float, float, float]]:
        """
        Retorna as coordenadas de todos os pontos únicos do objeto.
        Usado pela TransformationController.

        Returns:
            List[Tuple[float, float, float]]: Lista de coordenadas (x, y, z).
        """
        return [p.get_coords() for p in self.get_all_points()]

    def get_center(self) -> Tuple[float, float, float]:
        """
        Calcula o centro geométrico do objeto (média das coordenadas dos pontos únicos).

        Returns:
            Tuple[float, float, float]: Coordenadas (x, y, z) do centro.
        """
        points = self.get_all_points()
        if not points:
            return (0.0, 0.0, 0.0)

        sum_x = sum(p.x for p in points)
        sum_y = sum(p.y for p in points)
        sum_z = sum(p.z for p in points)
        count = len(points)

        return (
            (sum_x / count, sum_y / count, sum_z / count)
            if count > 0
            else (0.0, 0.0, 0.0)
        )

    def apply_transformation_matrix(self, matrix: np.ndarray) -> None:
        """
        Aplica uma matriz de transformação 4x4 a todos os pontos do objeto.

        Args:
            matrix: Matriz de transformação NumPy 4x4.
        """
        for point in self.get_all_points():  # Transforma os Ponto3D únicos
            hom_coords = point.get_homogeneous_coords()
            transformed_hom_coords = matrix @ hom_coords
            point.set_from_homogeneous_coords(transformed_hom_coords)

    def translate(self, dx: float, dy: float, dz: float) -> None:
        """Translação do objeto 3D."""
        from ..utils import (
            transformations_3d as tf3d,
        )  # Importação local para evitar ciclos

        matrix = tf3d.create_translation_matrix_3d(dx, dy, dz)
        self.apply_transformation_matrix(matrix)

    def scale(
        self,
        sx: float,
        sy: float,
        sz: float,
        center: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        """Escalonamento 3D em relação a um ponto central (ou ao centro do objeto se None)."""
        from ..utils import transformations_3d as tf3d  # Importação local

        if center is None:
            center_x, center_y, center_z = self.get_center()
        else:
            center_x, center_y, center_z = center

        t_to_origin = tf3d.create_translation_matrix_3d(-center_x, -center_y, -center_z)
        s_matrix = tf3d.create_scaling_matrix_3d(sx, sy, sz)
        t_back = tf3d.create_translation_matrix_3d(center_x, center_y, center_z)
        # Ordem: Transladar para origem, Escalonar, Transladar de volta
        matrix = t_back @ s_matrix @ t_to_origin
        self.apply_transformation_matrix(matrix)

    def rotate_around_axis_angle(
        self,
        axis_vector: np.ndarray,
        angle_degrees: float,
        rotation_point: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        """
        Rotação 3D em torno de um eixo arbitrário que passa por rotation_point
        (ou origem se None).
        """
        from ..utils import transformations_3d as tf3d  # Importação local

        if rotation_point is None:
            px, py, pz = (
                self.get_center()
            )  # Rotaciona em torno do centro do objeto por padrão
        else:
            px, py, pz = rotation_point

        t_to_origin = tf3d.create_translation_matrix_3d(-px, -py, -pz)
        r_matrix = tf3d.create_rotation_matrix_3d_arbitrary_axis(
            axis_vector, angle_degrees
        )
        t_back = tf3d.create_translation_matrix_3d(px, py, pz)

        # Ordem: Transladar ponto de rotação para origem, Rotacionar, Transladar de volta
        final_matrix = t_back @ r_matrix @ t_to_origin
        self.apply_transformation_matrix(final_matrix)

    def create_graphics_item(self, projected_lines: List[QLineF]) -> QGraphicsPathItem:
        """
        Cria um item gráfico 2D (QGraphicsPathItem) a partir de uma lista de linhas 2D projetadas.
        Este método é chamado pelo SceneController após a projeção 3D->2D.

        Args:
            projected_lines: Lista de QLineF representando os segmentos do objeto projetados na cena 2D.

        Returns:
            QGraphicsPathItem: Item gráfico para exibição na QGraphicsScene.
        """
        path = QPainterPath()
        if (
            not projected_lines
        ):  # Se não há linhas projetadas (e.g. objeto totalmente fora da vista)
            return QGraphicsPathItem(path)  # Retorna item com caminho vazio

        for line in projected_lines:
            path.moveTo(
                line.p1()
            )  # Inicia um sub-caminho ou move para o início da linha
            path.lineTo(line.p2())  # Desenha a linha

        item = QGraphicsPathItem(path)
        pen = QPen(self.color, self.GRAPHICS_LINE_WIDTH)
        pen.setJoinStyle(
            Qt.RoundJoin
        )  # Para junções mais suaves entre segmentos de linha
        pen.setCapStyle(Qt.RoundCap)  # Para pontas de linha mais suaves
        item.setPen(pen)
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        # A movimentação direta de objetos 3D projetados na cena 2D é complexa
        # e geralmente requer interações 3D (manipuladores, etc.) ou transformações via diálogo.
        # item.setFlag(QGraphicsItem.ItemIsMovable)
        return item

    def __repr__(self) -> str:
        return f"Objeto3D(name='{self.name}', segments={len(self.segments)}, color={self.color.name()})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Objeto3D):
            return NotImplemented
        # Uma comparação mais robusta poderia verificar a igualdade de cada segmento e ponto.
        # Por simplicidade, comparamos nome, número de segmentos e cor.
        return (
            self.name == other.name
            and len(self.segments) == len(other.segments)
            and self.color == other.color
            and self.segments == other.segments
        )  # Compara se os segmentos são os mesmos (Ponto3D tem __eq__)
