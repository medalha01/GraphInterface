"""
Módulo que define a classe Point para representação de pontos 2D.
Este módulo contém a implementação de pontos geométricos com coordenadas e cor.
"""

# graphics_editor/models/point.py
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsEllipseItem
from typing import Tuple, List, Optional


class Point:
    """
    Representa um ponto geométrico 2D com coordenadas e cor.

    Responsável por:
    - Armazenar coordenadas (x, y) de um ponto.
    - Gerenciar a cor do ponto.
    - Criar a representação gráfica QGraphicsItem do ponto.
    - Fornecer métodos para manipulação de coordenadas.
    """

    GRAPHICS_SIZE = 6.0  # Diâmetro visual do ponto na cena

    def __init__(self, x: float, y: float, color: Optional[QColor] = None):
        """
        Inicializa um ponto com coordenadas e cor.

        Args:
            x: Coordenada x do ponto.
            y: Coordenada y do ponto.
            color: Cor do ponto (opcional, padrão é preto).
        """
        self.x: float = float(x)
        self.y: float = float(y)
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def to_qpointf(self) -> QPointF:
        """Converte o ponto para o formato QPointF do Qt."""
        return QPointF(self.x, self.y)

    def create_graphics_item(self) -> QGraphicsEllipseItem:
        """
        Cria a representação gráfica do ponto como um QGraphicsEllipseItem.

        Returns:
            QGraphicsEllipseItem: Item gráfico representando o ponto.
        """
        offset = self.GRAPHICS_SIZE / 2.0
        # Cria elipse centrada em (x, y)
        point_item = QGraphicsEllipseItem(
            self.x - offset, self.y - offset, self.GRAPHICS_SIZE, self.GRAPHICS_SIZE
        )

        pen = QPen(self.color, 1)  # Borda fina com a cor do ponto
        brush = QBrush(self.color)  # Preenchimento sólido com a cor do ponto
        point_item.setPen(pen)
        point_item.setBrush(brush)

        point_item.setFlag(QGraphicsItem.ItemIsSelectable)
        # A movimentação é geralmente tratada pelo SceneController ou View,
        # não habilitada diretamente no item por padrão.
        # point_item.setFlag(QGraphicsItem.ItemIsMovable)
        return point_item

    def get_coords(self) -> Tuple[float, float]:
        """Retorna as coordenadas (x, y) do ponto."""
        return (self.x, self.y)

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centro geométrico do ponto (que é o próprio ponto)."""
        return self.get_coords()

    def __repr__(self) -> str:
        """Retorna uma representação textual do ponto."""
        return f"Point(x={self.x:.3f}, y={self.y:.3f}, color={self.color.name()})"

    def __eq__(self, other: object) -> bool:
        """Verifica se dois Pontos são iguais (baseado nas coordenadas)."""
        if not isinstance(other, Point):
            return NotImplemented
        # Compara com uma pequena tolerância para pontos flutuantes
        epsilon = 1e-9
        return abs(self.x - other.x) < epsilon and abs(self.y - other.y) < epsilon
        # A cor não é considerada para igualdade geométrica aqui.
