# graphics_editor/models/polygon.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QBrush, QPolygonF, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPolygonItem
from typing import List, Tuple, Optional

# Importa Point explicitamente
from .point import Point


class Polygon:
    """Representa um polígono 2D (fechado) ou polilinha (aberto)."""

    GRAPHICS_BORDER_WIDTH = 2  # Espessura da borda
    GRAPHICS_FILL_ALPHA = 0.35  # Opacidade do preenchimento (0.0 a 1.0)

    def __init__(
        self, points: List[Point], is_open: bool = False, color: Optional[QColor] = None
    ):
        """
        Inicializa um polígono ou polilinha.
        Args:
            points: Lista ordenada de vértices (objetos Point).
            is_open: True para polilinha, False para polígono fechado.
            color: Cor da borda/linha.
        """
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
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def create_graphics_item(self) -> QGraphicsPolygonItem:
        """Cria a representação gráfica QGraphicsPolygonItem."""
        # Cria QPolygonF a partir dos pontos
        polygon_qf = QPolygonF([p.to_qpointf() for p in self.points])
        polygon_item = QGraphicsPolygonItem(polygon_qf)

        # Aparência (Caneta e Pincel)
        pen = QPen(self.color, self.GRAPHICS_BORDER_WIDTH)
        brush = QBrush()  # Padrão é NoBrush

        if self.is_open:  # Polilinha
            pen.setStyle(Qt.DashLine)
            brush.setStyle(Qt.NoBrush)
        else:  # Polígono Fechado
            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.SolidPattern)
            fill_color = QColor(self.color)
            fill_color.setAlphaF(self.GRAPHICS_FILL_ALPHA)  # Aplica transparência
            brush.setColor(fill_color)

        polygon_item.setPen(pen)
        polygon_item.setBrush(brush)

        # Flags
        polygon_item.setFlag(QGraphicsItem.ItemIsSelectable)
        polygon_item.setFlag(QGraphicsItem.ItemIsMovable)

        # Associa dados
        polygon_item.setData(0, self)
        return polygon_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna lista de coordenadas (x, y) dos vértices."""
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centroide (média aritmética dos vértices)."""
        if not self.points:
            return (0.0, 0.0)  # Caso impossível devido ao __init__
        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)
        return (sum_x / count, sum_y / count)

    def __repr__(self) -> str:
        """Representação textual."""
        tipo = "Polygon(open)" if self.is_open else "Polygon(closed)"
        points_str = ", ".join(repr(p) for p in self.points)
        return f"{tipo}[{points_str}], color={self.color.name()}"
