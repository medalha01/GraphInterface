"""
Módulo que define a classe Point para representação de pontos 2D.
Este módulo contém a implementação de pontos geométricos com coordenadas e cor.
"""

# point.py
# graphics_editor/models/point.py
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsEllipseItem
from typing import Tuple, List, Optional  # Import Optional


class Point:
    """
    Representa um ponto geométrico 2D com coordenadas e cor.
    
    Esta classe é responsável por:
    - Armazenar coordenadas (x, y) de um ponto
    - Gerenciar a cor do ponto
    - Criar a representação gráfica do ponto
    - Fornecer métodos para manipulação de coordenadas
    """

    GRAPHICS_SIZE = 6.0  # Diâmetro visual do ponto na cena

    def __init__(self, x: float, y: float, color: Optional[QColor] = None):
        """
        Inicializa um ponto com coordenadas e cor.
        
        Args:
            x: Coordenada x do ponto
            y: Coordenada y do ponto
            color: Cor do ponto (opcional, padrão é preto)
        """
        self.x: float = float(x)
        self.y: float = float(y)
        # Cor padrão preta se não fornecida ou inválida
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def to_qpointf(self) -> QPointF:
        """
        Converte o ponto para o formato QPointF do Qt.
        
        Returns:
            QPointF: Ponto no formato Qt
        """
        return QPointF(self.x, self.y)

    def create_graphics_item(self) -> QGraphicsEllipseItem:
        """
        Cria a representação gráfica do ponto como um item da cena.
        
        Returns:
            QGraphicsEllipseItem: Item gráfico representando o ponto
        """
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
        """
        Retorna as coordenadas do ponto.
        
        Returns:
            Tuple[float, float]: Tupla contendo as coordenadas (x, y)
        """
        return (self.x, self.y)

    def get_center(self) -> Tuple[float, float]:
        """
        Retorna o centro geométrico do ponto.
        Para um ponto, o centro é o próprio ponto.
        
        Returns:
            Tuple[float, float]: Tupla contendo as coordenadas do centro
        """
        return self.get_coords()

    def __repr__(self) -> str:
        """
        Retorna uma representação textual do ponto.
        
        Returns:
            str: String representando o ponto com suas coordenadas e cor
        """
        return f"Point(x={self.x:.3f}, y={self.y:.3f}, color={self.color.name()})"
