# models/point.py
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsEllipseItem
from typing import Tuple

class Point:
    """Representa um ponto geométrico com coordenadas e cor."""

    def __init__(self, x: float, y: float, color: QColor = QColor(Qt.black)):
        self.x: float = x
        self.y: float = y
        self.color: QColor = color

    def to_qpointf(self) -> QPointF:
        """Converte o Ponto para um QPointF."""
        return QPointF(self.x, self.y)

    def create_graphics_item(self) -> QGraphicsEllipseItem:
        """Cria uma representação QGraphicsEllipseItem do ponto."""
        size: float = 6.0
        offset: float = size / 2.0
        point_item = QGraphicsEllipseItem(self.x - offset, self.y - offset, size, size)
        point_item.setPen(QPen(self.color, 1))
        point_item.setBrush(QBrush(self.color))
        point_item.setFlag(QGraphicsItem.ItemIsMovable)
        point_item.setFlag(QGraphicsItem.ItemIsSelectable)
        point_item.setData(0, self)
        return point_item

    def get_coords(self) -> Tuple[float, float]:
         """Retorna as coordenadas como uma tupla."""
         return (self.x, self.y)

    def get_center(self) -> Tuple[float, float]:
        """Retorna as coordenadas do centro (que são as próprias coordenadas do ponto)."""
        return self.get_coords()