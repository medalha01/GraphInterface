# graphics_editor/models/line.py
from PyQt5.QtCore import Qt, QLineF
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from typing import List, Tuple, Optional

# Importa Point explicitamente
from .point import Point


class Line:
    """Representa um segmento de linha 2D."""

    GRAPHICS_WIDTH = 2  # Espessura visual da linha

    def __init__(
        self, start_point: Point, end_point: Point, color: Optional[QColor] = None
    ):
        """Inicializa uma linha."""
        if not isinstance(start_point, Point) or not isinstance(end_point, Point):
            raise TypeError("start_point e end_point devem ser instâncias de Point.")
        self.start: Point = start_point
        self.end: Point = end_point
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def create_graphics_item(self) -> QGraphicsLineItem:
        """Cria a representação gráfica QGraphicsLineItem."""
        line_item = QGraphicsLineItem(
            self.start.x, self.start.y, self.end.x, self.end.y
        )

        # Aparência
        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        line_item.setPen(pen)

        # Flags
        line_item.setFlag(QGraphicsItem.ItemIsSelectable)
        # line_item.setFlag(QGraphicsItem.ItemIsMovable)

        # SceneController will handle setting SC_ORIGINAL_OBJECT_KEY and SC_CURRENT_REPRESENTATION_KEY
        # line_item.setData(0, self) # Removed as per issue #6
        return line_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna coordenadas inicial e final como lista de tuplas."""
        return [self.start.get_coords(), self.end.get_coords()]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o ponto médio da linha."""
        center_x = (self.start.x + self.end.x) / 2.0
        center_y = (self.start.y + self.end.y) / 2.0
        return (center_x, center_y)

    def __repr__(self) -> str:
        """Representação textual."""
        return (
            f"Line(start={self.start!r}, end={self.end!r}, color={self.color.name()})"
        )
