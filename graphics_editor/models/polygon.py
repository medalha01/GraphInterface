"""
Módulo que define a classe Polygon para representação de polígonos e polilinhas 2D.
Este módulo contém a implementação de polígonos com vértices, preenchimento e cor.
"""

# graphics_editor/models/polygon.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QBrush, QPolygonF, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPolygonItem, QGraphicsPathItem
from typing import List, Tuple, Optional, Union

from .point import Point


class Polygon:
    """
    Representa um polígono 2D (fechado) ou polilinha (aberto).
    
    Esta classe é responsável por:
    - Gerenciar vértices do polígono/polilinha
    - Controlar o estado de preenchimento
    - Criar a representação gráfica do polígono
    - Fornecer métodos para manipulação de coordenadas
    """

    GRAPHICS_BORDER_WIDTH = 2  # Espessura da borda
    GRAPHICS_FILL_ALPHA = 0.35  # Transparência do preenchimento

    def __init__(
        self,
        points: List[Point],
        is_open: bool = False,
        color: Optional[QColor] = None,
        is_filled: bool = False,
    ):
        """
        Inicializa um polígono ou polilinha.
        
        Args:
            points: Lista de pontos que formam o polígono
            is_open: Se True, cria uma polilinha aberta; se False, cria um polígono fechado
            color: Cor do polígono (opcional, padrão é preto)
            is_filled: Se True, o polígono será preenchido (ignorado se is_open=True)
            
        Raises:
            TypeError: Se os pontos não forem instâncias de Point
            ValueError: Se houver menos de 2 pontos
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
        self.is_filled: bool = is_filled if not is_open else False
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def create_graphics_item(self) -> Union[QGraphicsPolygonItem, QGraphicsPathItem]:
        """
        Cria a representação gráfica do polígono como um item da cena.
        
        Returns:
            Union[QGraphicsPolygonItem, QGraphicsPathItem]: Item gráfico representando o polígono
            - QGraphicsPolygonItem para polígonos fechados
            - QGraphicsPathItem para polilinhas abertas
        """
        pen = QPen(self.color, self.GRAPHICS_BORDER_WIDTH)
        brush = QBrush(Qt.NoBrush)
        item: Union[QGraphicsPolygonItem, QGraphicsPathItem]

        if self.is_open:
            path = QPainterPath()
            if self.points:
                path.moveTo(self.points[0].to_qpointf())
                for point_model in self.points[1:]:
                    path.lineTo(point_model.to_qpointf())
            item = QGraphicsPathItem(path)
            pen.setStyle(Qt.SolidLine)
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

        return item

    def get_coords(self) -> List[Tuple[float, float]]:
        """
        Retorna as coordenadas de todos os vértices do polígono.
        
        Returns:
            List[Tuple[float, float]]: Lista contendo as coordenadas dos vértices
        """
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """
        Retorna o centro geométrico do polígono.
        
        Returns:
            Tuple[float, float]: Tupla contendo as coordenadas do centro
        """
        if not self.points:
            return (0.0, 0.0)
        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)
        if count == 0:
            return (0.0, 0.0)
        return (sum_x / count, sum_y / count)

    def __repr__(self) -> str:
        """
        Retorna uma representação textual do polígono.
        
        Returns:
            str: String representando o polígono com seus vértices, estado e cor
        """
        tipo = (
            "Polygon(open)"
            if self.is_open
            else f"Polygon(closed, filled={self.is_filled})"
        )
        points_str = ", ".join(repr(p) for p in self.points)
        return (
            f"Polygon(points=[{points_str}], is_open={self.is_open}, "
            f"is_filled={self.is_filled}, color={self.color.name()})"
        )
