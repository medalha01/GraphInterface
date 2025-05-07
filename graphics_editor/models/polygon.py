# graphics_editor/models/polygon.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QBrush, QPolygonF, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPolygonItem, QGraphicsPathItem
from typing import List, Tuple, Optional, Union

from .point import Point


class Polygon:
    """Representa um polígono 2D (fechado) ou polilinha (aberto)."""

    GRAPHICS_BORDER_WIDTH = 2
    GRAPHICS_FILL_ALPHA = 0.35

    def __init__(
        self,
        points: List[Point],
        is_open: bool = False,
        color: Optional[QColor] = None,
        is_filled: bool = False,
    ):
        if not isinstance(points, list) or not all(
            isinstance(p, Point) for p in points
        ):
            raise TypeError(
                "Argumento 'points' deve ser uma lista de instâncias de Point."
            )

        min_points = 2 if is_open else 3
        if len(points) < min_points:
            tipo = "Polilinha" if is_open else "Polígono"
            raise ValueError(
                f"{tipo} requer pelo menos {min_points} pontos (recebeu {len(points)})."
            )

        self.points: List[Point] = points
        self.is_open: bool = is_open
        self.is_filled: bool = is_filled if not is_open else False
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def create_graphics_item(self) -> Union[QGraphicsPolygonItem, QGraphicsPathItem]:
        """Cria a representação gráfica."""
        pen = QPen(self.color, self.GRAPHICS_BORDER_WIDTH)
        brush = QBrush(Qt.NoBrush)

        if self.is_open:
            path = QPainterPath()
            if self.points:
                path.moveTo(self.points[0].to_qpointf())
                for point_model in self.points[1:]:
                    path.lineTo(point_model.to_qpointf())

            item = QGraphicsPathItem(path)
            pen.setStyle(Qt.DashLine)
        else:
            polygon_qf = QPolygonF([p.to_qpointf() for p in self.points])
            item = QGraphicsPolygonItem(polygon_qf)

            pen.setStyle(Qt.SolidLine)
            if self.is_filled:
                brush.setStyle(Qt.SolidPattern)
                fill_color = QColor(self.color)
                fill_color.setAlphaF(self.GRAPHICS_FILL_ALPHA)
                brush.setColor(fill_color)

        item.setPen(pen)
        item.setBrush(brush)
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        item.setData(0, self)
        return item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna lista de coordenadas (x, y) dos vértices."""
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centroide (média aritmética dos vértices)."""
        if not self.points:
            return (0.0, 0.0)
        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)
        return (sum_x / count, sum_y / count)

    def __repr__(self) -> str:
        """Representação textual."""
        tipo = (
            "Polygon(open)"
            if self.is_open
            else f"Polygon(closed, filled={self.is_filled})"
        )
        points_str = ", ".join(repr(p) for p in self.points)
        return f"{tipo}[{points_str}], color={self.color.name()}"
