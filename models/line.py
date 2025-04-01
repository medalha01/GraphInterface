# models/line.py
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from typing import TYPE_CHECKING, Tuple, List

if TYPE_CHECKING:
    from .point import Point

class Line:
    """Representa um segmento de linha definido por dois pontos."""

    def __init__(self, start_point: 'Point', end_point: 'Point', color: QColor = QColor(Qt.black)):
        if not isinstance(start_point, Point) or not isinstance(end_point, Point):
             raise TypeError("start_point e end_point devem ser objetos Point")
        self.start: 'Point' = start_point
        self.end: 'Point' = end_point
        self.color: QColor = color

    def create_graphics_item(self) -> QGraphicsLineItem:
        """Cria uma representação QGraphicsLineItem da linha."""
        line_item = QGraphicsLineItem(self.start.x, self.start.y,
                                      self.end.x, self.end.y)
        pen = QPen(self.color, 2)
        line_item.setPen(pen)
        line_item.setFlag(QGraphicsItem.ItemIsMovable)
        line_item.setFlag(QGraphicsItem.ItemIsSelectable)
        line_item.setData(0, self)
        return line_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna as coordenadas dos pontos inicial e final como uma lista de tuplas."""
        return [self.start.get_coords(), self.end.get_coords()]

    def get_center(self) -> Tuple[float, float]:
        """Calcula o ponto médio do segmento de linha."""
        return ((self.start.x + self.end.x) / 2.0, (self.start.y + self.end.y) / 2.0)

from .point import Point