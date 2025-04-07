from PyQt5.QtCore import Qt, QLineF # Import QLineF
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from typing import TYPE_CHECKING, Tuple, List

# Importação condicional para type hinting, evita importação circular em runtime
if TYPE_CHECKING:
    from .point import Point

# Importa Point no final para evitar problemas de importação circular se Point importar Line
# (embora não seja o caso aqui, é uma boa prática em modelos inter-relacionados)
from .point import Point

class Line:
    """Representa um segmento de linha 2D definido por dois pontos (inicial e final)."""

    def __init__(self, start_point: Point, end_point: Point, color: QColor = QColor(Qt.black)):
        """
        Inicializa uma linha.
        Args:
            start_point: O objeto Point inicial da linha.
            end_point: O objeto Point final da linha.
            color: A cor da linha (padrão: preto).
        Raises:
            TypeError: Se start_point ou end_point não forem instâncias de Point.
        """
        if not isinstance(start_point, Point) or not isinstance(end_point, Point):
             raise TypeError("start_point e end_point devem ser instâncias da classe Point.")
        self.start: Point = start_point
        self.end: Point = end_point
        # Garante que a cor seja válida, senão usa preto
        self.color: QColor = color if color.isValid() else QColor(Qt.black)

    def create_graphics_item(self) -> QGraphicsLineItem:
        """
        Cria uma representação gráfica (QGraphicsLineItem) para esta linha.
        Retorna:
            Um QGraphicsLineItem configurado para representar a linha.
        """
        # Cria o item de linha usando as coordenadas dos pontos inicial e final
        line_item = QGraphicsLineItem(self.start.x, self.start.y, self.end.x, self.end.y)

        # Define a aparência da linha (caneta)
        pen = QPen(self.color, 2) # Caneta com a cor da linha e espessura 2
        line_item.setPen(pen)

        # Define flags para interação
        line_item.setFlag(QGraphicsItem.ItemIsMovable)
        line_item.setFlag(QGraphicsItem.ItemIsSelectable)

        # Associa este objeto de dados (self) ao item gráfico
        line_item.setData(0, self)

        return line_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """
        Retorna as coordenadas dos pontos inicial e final como uma lista de tuplas.
        Returns:
            Lista contendo duas tuplas: [(x_start, y_start), (x_end, y_end)].
        """
        return [self.start.get_coords(), self.end.get_coords()]

    def get_center(self) -> Tuple[float, float]:
        """
        Calcula e retorna as coordenadas do ponto médio do segmento de linha.
        Returns:
            Tupla (x_center, y_center).
        """
        center_x = (self.start.x + self.end.x) / 2.0
        center_y = (self.start.y + self.end.y) / 2.0
        return (center_x, center_y)

    def __repr__(self) -> str:
        """Representação textual do objeto Line."""
        return f"Line(start={self.start!r}, end={self.end!r}, color={self.color.name()})"
