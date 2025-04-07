# graphics_editor/models/polygon.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QBrush, QPolygonF, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPolygonItem
from typing import List, Tuple, TYPE_CHECKING

# Importação condicional para type hinting
if TYPE_CHECKING:
    from .point import Point

# Importa Point no final
from .point import Point

class Polygon:
    """
    Representa um polígono 2D (fechado) ou uma polilinha (aberto)
    definido por uma lista ordenada de pontos.
    """

    def __init__(self, points: List[Point], is_open: bool = False, color: QColor = QColor(Qt.black)):
        """
        Inicializa um polígono ou polilinha.
        Args:
            points: Lista de objetos Point que definem os vértices em ordem.
            is_open: Se True, representa uma polilinha (aberta, geralmente tracejada).
                     Se False, representa um polígono fechado (com preenchimento).
            color: A cor da borda do polígono/polilinha (padrão: preto).
        Raises:
            TypeError: Se `points` não for uma lista ou contiver itens que não são Point.
            ValueError: Se `points` tiver menos de 2 pontos para polilinha ou 3 para polígono.
        """
        if not isinstance(points, list) or not all(isinstance(p, Point) for p in points):
             raise TypeError("O argumento 'points' deve ser uma lista de instâncias da classe Point.")

        # Validação básica do número de pontos
        min_points = 2 if is_open else 3
        if len(points) < min_points:
             type_str = "Polilinha (aberta)" if is_open else "Polígono (fechado)"
             raise ValueError(f"{type_str} requer pelo menos {min_points} pontos (recebeu {len(points)}).")

        self.points: List[Point] = points # Lista de vértices
        self.is_open: bool = is_open     # Define se é aberto (polilinha) ou fechado
        # Garante que a cor seja válida, senão usa preto
        self.color: QColor = color if color.isValid() else QColor(Qt.black)

    def create_graphics_item(self) -> QGraphicsPolygonItem:
        """
        Cria uma representação gráfica (QGraphicsPolygonItem) para este polígono/polilinha.
        Retorna:
            Um QGraphicsPolygonItem configurado.
        """
        # Cria um QPolygonF a partir dos QPointF dos nossos objetos Point
        polygon_qf = QPolygonF()
        for point in self.points:
            polygon_qf.append(point.to_qpointf())

        # Cria o item gráfico usando o QPolygonF
        polygon_item = QGraphicsPolygonItem(polygon_qf)

        # --- Configura a Aparência (Caneta e Pincel) ---
        pen = QPen(self.color, 2) # Caneta para a borda, espessura 2
        brush = QBrush()          # Pincel para o preenchimento

        if self.is_open:
            # Polilinha: linha tracejada, sem preenchimento
            pen.setStyle(Qt.DashLine)
            brush.setStyle(Qt.NoBrush) # Sem preenchimento
        else:
            # Polígono Fechado: linha sólida, preenchimento semi-transparente
            pen.setStyle(Qt.SolidLine)
            brush.setStyle(Qt.SolidPattern) # Preenchimento sólido
            # Cria uma cor de preenchimento baseada na cor da borda, mas com alfa
            fill_color = QColor(self.color)
            fill_color.setAlphaF(0.35) # 35% de opacidade
            brush.setColor(fill_color)

        polygon_item.setPen(pen)
        polygon_item.setBrush(brush)

        # --- Configura Flags de Interação ---
        polygon_item.setFlag(QGraphicsItem.ItemIsMovable)
        polygon_item.setFlag(QGraphicsItem.ItemIsSelectable)

        # Associa este objeto de dados (self) ao item gráfico
        polygon_item.setData(0, self)

        return polygon_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """
        Retorna a lista de coordenadas (x, y) para todos os pontos (vértices).
        Returns:
            Lista de tuplas: [(x1, y1), (x2, y2), ...].
        """
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """
        Calcula o centro geométrico (centroide) do polígono/polilinha.
        Retorna:
            Tupla (center_x, center_y). Retorna (0, 0) se não houver pontos.
        """
        if not self.points:
            return (0.0, 0.0)

        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)

        # Evita divisão por zero se a lista de pontos ficar vazia (não deveria acontecer com a validação no init)
        if count == 0:
             return (0.0, 0.0)

        return sum_x / count, sum_y / count

    def __repr__(self) -> str:
        """Representação textual do objeto Polygon."""
        type_str = "Polygon(open)" if self.is_open else "Polygon(closed)"
        points_str = ", ".join(repr(p) for p in self.points)
        return f"{type_str}[{points_str}], color={self.color.name()}"

