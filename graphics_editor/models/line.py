"""
Módulo que define a classe Line para representação de segmentos de linha 2D.
Este módulo contém a implementação de linhas com pontos inicial e final.
"""

# graphics_editor/models/line.py
from PyQt5.QtCore import Qt, QLineF
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from typing import List, Tuple, Optional

from .point import Point  # Importação explícita


class Line:
    """
    Representa um segmento de linha 2D definido por um ponto inicial e final.

    Responsável por:
    - Armazenar os objetos Point inicial e final.
    - Gerenciar a cor da linha.
    - Criar a representação gráfica QGraphicsItem da linha.
    - Fornecer métodos para manipulação de coordenadas.
    """

    GRAPHICS_WIDTH = 2  # Espessura visual da linha

    def __init__(
        self, start_point: Point, end_point: Point, color: Optional[QColor] = None
    ):
        """
        Inicializa uma linha com pontos inicial e final.

        Args:
            start_point: Objeto Point inicial.
            end_point: Objeto Point final.
            color: Cor da linha (opcional, padrão é preto).

        Raises:
            TypeError: Se start_point ou end_point não forem instâncias de Point.
        """
        if not isinstance(start_point, Point) or not isinstance(end_point, Point):
            raise TypeError("start_point e end_point devem ser instâncias de Point.")
        self.start: Point = start_point
        self.end: Point = end_point
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def create_graphics_item(self) -> QGraphicsLineItem:
        """
        Cria a representação gráfica da linha como um QGraphicsLineItem.

        Returns:
            QGraphicsLineItem: Item gráfico representando a linha.
        """
        # Cria QLineF a partir das coordenadas dos Point objects
        q_line_f = QLineF(self.start.to_qpointf(), self.end.to_qpointf())
        line_item = QGraphicsLineItem(q_line_f)

        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        line_item.setPen(pen)

        line_item.setFlag(QGraphicsItem.ItemIsSelectable)
        return line_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna as coordenadas dos pontos inicial e final como uma lista de tuplas."""
        return [self.start.get_coords(), self.end.get_coords()]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o ponto médio da linha."""
        center_x = (self.start.x + self.end.x) / 2.0
        center_y = (self.start.y + self.end.y) / 2.0
        return (center_x, center_y)

    def __repr__(self) -> str:
        """Retorna uma representação textual da linha."""
        return (
            f"Line(start={self.start!r}, end={self.end!r}, color={self.color.name()})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Line):
            return NotImplemented
        # Compara os pontos e a cor. A ordem dos pontos não importa para a igualdade geométrica da linha.
        # No entanto, para consistência com o construtor, comparamos start com start e end com end.
        return (
            self.start == other.start
            and self.end == other.end
            and self.color == other.color
        )
