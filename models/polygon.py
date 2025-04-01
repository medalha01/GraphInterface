# models/polygon.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QBrush, QPolygonF, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPolygonItem
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .point import Point

class Polygon:
    """Representa um polígono definido por uma lista de pontos."""

    def __init__(self, points: List['Point'], is_open: bool = False, color: QColor = QColor(Qt.black)):
        if points and not all(isinstance(p, Point) for p in points):
             raise TypeError("points deve ser uma lista de objetos Point")
        self.points: List['Point'] = points
        self.is_open: bool = is_open
        self.color: QColor = color

    def create_graphics_item(self) -> QGraphicsPolygonItem:
        """Cria uma representação QGraphicsPolygonItem do polígono."""
        polygon_qf = QPolygonF()
        for point in self.points:
            polygon_qf.append(point.to_qpointf())

        polygon_item = QGraphicsPolygonItem(polygon_qf)
        pen = QPen(self.color, 2)
        brush = QBrush()

        if self.is_open:
            pen.setStyle(Qt.DashLine)
            brush.setStyle(Qt.NoBrush)
        else:
            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.SolidPattern)
            fill_color = QColor(self.color)
            fill_color.setAlphaF(0.35)
            brush.setColor(fill_color)

        polygon_item.setPen(pen)
        polygon_item.setBrush(brush)

        polygon_item.setFlag(QGraphicsItem.ItemIsMovable)
        polygon_item.setFlag(QGraphicsItem.ItemIsSelectable)
        polygon_item.setData(0, self)
        return polygon_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna a lista de coordenadas para todos os pontos no polígono."""
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """Calcula o centro geométrico (centroide) do polígono."""
        if not self.points: return (0.0, 0.0)
        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)
        if count == 0: return (0.0, 0.0)
        return sum_x / count, sum_y / count

from .point import Point