"""
Módulo que define a classe Polygon para representação de polígonos e polilinhas 2D.
Este módulo contém a implementação de polígonos com vértices, preenchimento e cor.
"""

# graphics_editor/models/polygon.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QBrush, QPolygonF, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPolygonItem, QGraphicsPathItem
from typing import List, Tuple, Optional, Union

from .point import Point  # Importação explícita


class Polygon:
    """
    Representa um polígono 2D (fechado) ou uma polilinha (aberta).

    Responsável por:
    - Gerenciar uma lista de vértices (objetos Point).
    - Controlar se é aberto (polilinha) ou fechado (polígono).
    - Controlar o estado de preenchimento (para polígonos fechados).
    - Gerenciar a cor.
    - Criar a representação gráfica QGraphicsItem.
    """

    GRAPHICS_BORDER_WIDTH = 2  # Espessura da borda
    GRAPHICS_FILL_ALPHA = 0.35  # Transparência do preenchimento (0.0 a 1.0)

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
            points: Lista de objetos Point que formam os vértices.
            is_open: True para polilinha (aberta), False para polígono (fechado).
            color: Cor do polígono/polilinha (opcional, padrão é preto).
            is_filled: True para preencher o polígono (ignorado se is_open=True).

        Raises:
            TypeError: Se 'points' não for uma lista de instâncias de Point.
            ValueError: Se o número de pontos for insuficiente (mín. 2 para aberto, mín. 3 para fechado).
        """
        if not isinstance(points, list) or not all(
            isinstance(p, Point) for p in points
        ):
            raise TypeError(
                "Argumento 'points' deve ser uma lista de instâncias de Point."
            )

        min_points_required = 2 if is_open else 3
        if len(points) < min_points_required:
            obj_type_str = "Polilinha" if is_open else "Polígono"
            raise ValueError(
                f"{obj_type_str} requer pelo menos {min_points_required} pontos (recebeu {len(points)})."
            )

        self.points: List[Point] = points
        self.is_open: bool = is_open
        self.is_filled: bool = (
            is_filled if not is_open else False
        )  # Preenchimento só para fechados
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

    def create_graphics_item(self) -> Union[QGraphicsPolygonItem, QGraphicsPathItem]:
        """
        Cria a representação gráfica do polígono/polilinha.

        Returns:
            QGraphicsPathItem para polilinhas abertas.
            QGraphicsPolygonItem para polígonos fechados.
        """
        pen = QPen(self.color, self.GRAPHICS_BORDER_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)  # Melhora aparência das junções
        pen.setCapStyle(Qt.RoundCap)  # Melhora aparência das pontas (para abertos)

        brush = QBrush(Qt.NoBrush)  # Padrão sem preenchimento
        item: Union[QGraphicsPolygonItem, QGraphicsPathItem]

        if self.is_open:  # Polilinha aberta
            path = QPainterPath()
            if self.points:  # Garante que há pontos para desenhar
                path.moveTo(self.points[0].to_qpointf())
                for point_model in self.points[1:]:
                    path.lineTo(point_model.to_qpointf())
            item = QGraphicsPathItem(path)
            # Linhas abertas não são preenchidas
        else:  # Polígono fechado
            polygon_qf = QPolygonF([p.to_qpointf() for p in self.points])
            item = QGraphicsPolygonItem(polygon_qf)
            if self.is_filled:
                brush.setStyle(Qt.SolidPattern)
                fill_color = QColor(self.color)  # Usa a cor base
                fill_color.setAlphaF(self.GRAPHICS_FILL_ALPHA)  # Aplica transparência
                brush.setColor(fill_color)

        item.setPen(pen)
        item.setBrush(brush)
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        return item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna as coordenadas (x,y) de todos os vértices."""
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centro geométrico (média dos vértices)."""
        if not self.points:  # Defensivo, construtor deve garantir pontos
            return (0.0, 0.0)

        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)

        return (sum_x / count, sum_y / count) if count > 0 else (0.0, 0.0)

    def __repr__(self) -> str:
        """Retorna uma representação textual do polígono/polilinha."""
        type_str = (
            "Polilinha" if self.is_open else f"Polígono(preenchido={self.is_filled})"
        )
        points_str = ", ".join(repr(p) for p in self.points)
        return f"{type_str}(pontos=[{points_str}], cor={self.color.name()})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Polygon):
            return NotImplemented
        return (
            self.points == other.points
            and self.is_open == other.is_open
            and self.is_filled == other.is_filled
            and self.color == other.color
        )
