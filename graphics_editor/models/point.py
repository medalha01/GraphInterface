# graphics_editor/models/point.py
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsEllipseItem
from typing import Tuple

class Point:
    """Representa um ponto geométrico 2D com coordenadas e cor."""

    def __init__(self, x: float, y: float, color: QColor = QColor(Qt.black)):
        """
        Inicializa um ponto.
        Args:
            x: Coordenada X.
            y: Coordenada Y.
            color: Cor do ponto (padrão: preto).
        """
        self.x: float = x
        self.y: float = y
        # Garante que a cor seja válida, senão usa preto
        self.color: QColor = color if color.isValid() else QColor(Qt.black)

    def to_qpointf(self) -> QPointF:
        """Converte as coordenadas do Ponto para um objeto QPointF."""
        return QPointF(self.x, self.y)

    def create_graphics_item(self) -> QGraphicsEllipseItem:
        """
        Cria uma representação gráfica (QGraphicsEllipseItem) para este ponto.
        Retorna:
            Um QGraphicsEllipseItem configurado para representar o ponto.
        """
        size: float = 6.0  # Diâmetro do círculo que representa o ponto
        offset: float = size / 2.0 # Metade do tamanho para centralizar a elipse

        # Cria a elipse centrada nas coordenadas (x, y)
        point_item = QGraphicsEllipseItem(self.x - offset, self.y - offset, size, size)

        # Define a aparência (caneta para borda, pincel para preenchimento)
        point_item.setPen(QPen(self.color, 1)) # Borda fina com a cor do ponto
        point_item.setBrush(QBrush(self.color)) # Preenchimento com a cor do ponto

        # Define flags para interação na QGraphicsScene
        point_item.setFlag(QGraphicsItem.ItemIsMovable)   # Permite mover o ponto
        point_item.setFlag(QGraphicsItem.ItemIsSelectable)# Permite selecionar o ponto

        # Associa este objeto de dados (self) ao item gráfico
        # O número 0 é uma chave de dados comum para o objeto principal associado
        point_item.setData(0, self)

        return point_item

    def get_coords(self) -> Tuple[float, float]:
         """Retorna as coordenadas (x, y) como uma tupla."""
         return (self.x, self.y)

    def get_center(self) -> Tuple[float, float]:
        """
        Retorna as coordenadas do centro geométrico do ponto.
        Para um ponto, o centro é sua própria coordenada.
        """
        return self.get_coords()

    def __repr__(self) -> str:
        """Representação textual do objeto Point."""
        return f"Point(x={self.x:.2f}, y={self.y:.2f}, color={self.color.name()})"
