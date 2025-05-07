# point.py
# graphics_editor/models/point.py
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsEllipseItem
from typing import Tuple, List, Optional  # Import Optional


class Point:
    """Representa um ponto geométrico 2D com coordenadas e cor."""

    GRAPHICS_SIZE = 6.0  # Diâmetro visual do ponto na cena

    def __init__(self, x: float, y: float, color: Optional[QColor] = None):
        """Inicializa um ponto."""
        self.x: float = float(x)
        self.y: float = float(y)
        # Cor padrão preta se não fornecida ou inválida
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def to_qpointf(self) -> QPointF:
        """Converte para QPointF."""
        return QPointF(self.x, self.y)

    def create_graphics_item(self) -> QGraphicsEllipseItem:
        """Cria a representação gráfica QGraphicsEllipseItem."""
        offset = self.GRAPHICS_SIZE / 2.0
        # Cria elipse centrada em (x, y)
        point_item = QGraphicsEllipseItem(
            self.x - offset, self.y - offset, self.GRAPHICS_SIZE, self.GRAPHICS_SIZE
        )

        # Aparência
        pen = QPen(self.color, 1)  # Borda fina
        brush = QBrush(self.color)  # Preenchimento sólido
        point_item.setPen(pen)
        point_item.setBrush(brush)

        # Flags para interação
        point_item.setFlag(QGraphicsItem.ItemIsSelectable)
        # point_item.setFlag(QGraphicsItem.ItemIsMovable) # Allow move

        # SceneController will handle setting SC_ORIGINAL_OBJECT_KEY and SC_CURRENT_REPRESENTATION_KEY
        # point_item.setData(0, self) # Removed as per issue #6
        return point_item

    def get_coords(self) -> Tuple[float, float]:
        """Retorna as coordenadas (x, y) como tupla."""
        return (self.x, self.y)

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centro geométrico (é o próprio ponto)."""
        return self.get_coords()

    def __repr__(self) -> str:
        """Representação textual."""
        return f"Point(x={self.x:.3f}, y={self.y:.3f}, color={self.color.name()})"
