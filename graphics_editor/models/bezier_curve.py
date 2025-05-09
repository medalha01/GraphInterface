# graphics_editor/models/bezier_curve.py
import math
import numpy as np
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem
from typing import List, Tuple, Optional, Union


from .point import Point

"""
Módulo que define a classe BezierCurve para representação de curvas de Bézier cúbicas compostas.
Este módulo contém a implementação de curvas de Bézier com múltiplos segmentos e pontos de controle.
"""


class BezierCurve:
    """
    Representa uma curva de Bézier cúbica composta (sequência de segmentos).
    
    Esta classe é responsável por:
    - Gerenciar múltiplos segmentos de curva de Bézier
    - Calcular pontos ao longo da curva
    - Subdividir segmentos da curva
    - Criar a representação gráfica da curva
    - Fornecer métodos para manipulação de coordenadas
    """

    GRAPHICS_WIDTH = 2  # Espessura visual da curva
    SUBDIVISION_THRESHOLD = 1.0  # Limiar para subdivisão da curva
    MAX_SUBDIVISION_DEPTH = 5  # Profundidade máxima de subdivisão

    def __init__(self, points: List[Point], color: Optional[QColor] = None):
        """
        Inicializa uma curva de Bézier com pontos de controle.
        
        Args:
            points: Lista de pontos de controle (deve ter 4, 7, 10, ... pontos)
            color: Cor da curva (opcional, padrão é preto)
            
        Raises:
            TypeError: Se os pontos não forem instâncias de Point
            ValueError: Se o número de pontos for inválido
        """
        if not isinstance(points, list) or not all(
            isinstance(p, Point) for p in points
        ):
            raise TypeError(
                "Argumento 'points' deve ser uma lista de instâncias de Point."
            )

        n_points = len(points)
        if n_points < 4:
            raise ValueError(
                f"Curva de Bézier requer pelo menos 4 pontos de controle (recebeu {n_points})."
            )
        if (n_points - 1) % 3 != 0:
            raise ValueError(
                f"Número inválido de pontos ({n_points}) para curva de Bézier composta. "
                "Deve ser 4, 7, 10,... (i.e., 3*N + 1, onde N é o nº de segmentos)."
            )

        self.points: List[Point] = points
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )
        self._num_segments = (n_points - 1) // 3

    def get_segment_control_points(self, segment_index: int) -> Optional[List[Point]]:
        """
        Retorna os 4 pontos de controle para um segmento específico.
        
        Args:
            segment_index: Índice do segmento desejado
            
        Returns:
            Optional[List[Point]]: Lista com 4 pontos de controle ou None se o índice for inválido
        """
        if not (0 <= segment_index < self._num_segments):
            return None
        start_idx = 3 * segment_index
        return self.points[start_idx : start_idx + 4]

    def create_graphics_item(self) -> QGraphicsPathItem:
        """
        Cria a representação gráfica da curva como um item da cena.
        
        Returns:
            QGraphicsPathItem: Item gráfico representando a curva
        """
        path = QPainterPath()
        if not self.points or self._num_segments == 0:
            return QGraphicsPathItem(path)

        path.moveTo(self.points[0].to_qpointf())
        for i in range(self._num_segments):
            segment_cps = self.get_segment_control_points(i)
            if segment_cps and len(segment_cps) == 4:

                ctrl_pt1 = segment_cps[1].to_qpointf()
                ctrl_pt2 = segment_cps[2].to_qpointf()
                end_pt = segment_cps[3].to_qpointf()
                path.cubicTo(ctrl_pt1, ctrl_pt2, end_pt)

        curve_item = QGraphicsPathItem(path)
        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        curve_item.setPen(pen)
        curve_item.setFlag(QGraphicsItem.ItemIsSelectable)
        return curve_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """
        Retorna as coordenadas de todos os pontos de controle.
        
        Returns:
            List[Tuple[float, float]]: Lista contendo as coordenadas dos pontos
        """
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """
        Retorna o centro da curva (média dos pontos de controle).
        
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

    def get_num_segments(self) -> int:
        """
        Retorna o número de segmentos na curva.
        
        Returns:
            int: Número de segmentos
        """
        return self._num_segments

    @staticmethod
    def _cubic_bezier_point(
        t: float,
        p0_coords: Tuple[float, float],
        p1_coords: Tuple[float, float],
        p2_coords: Tuple[float, float],
        p3_coords: Tuple[float, float],
    ) -> QPointF:
        """
        Calcula um ponto na curva de Bézier cúbica para um parâmetro t.
        
        Args:
            t: Parâmetro da curva (0 a 1)
            p0_coords: Coordenadas do primeiro ponto de controle
            p1_coords: Coordenadas do segundo ponto de controle
            p2_coords: Coordenadas do terceiro ponto de controle
            p3_coords: Coordenadas do quarto ponto de controle
            
        Returns:
            QPointF: Ponto calculado na curva
        """
        t = max(0.0, min(1.0, t))
        one_minus_t = 1.0 - t
        x = (
            one_minus_t**3 * p0_coords[0]
            + 3 * one_minus_t**2 * t * p1_coords[0]
            + 3 * one_minus_t * t**2 * p2_coords[0]
            + t**3 * p3_coords[0]
        )
        y = (
            one_minus_t**3 * p0_coords[1]
            + 3 * one_minus_t**2 * t * p1_coords[1]
            + 3 * one_minus_t * t**2 * p2_coords[1]
            + t**3 * p3_coords[1]
        )
        return QPointF(x, y)

    def sample_curve(self, num_points_per_segment: int = 20) -> List[QPointF]:
        """
        Amostra pontos ao longo da curva.
        
        Args:
            num_points_per_segment: Número de pontos a amostrar por segmento
            
        Returns:
            List[QPointF]: Lista de pontos amostrados ao longo da curva
        """
        sampled_points = []
        if num_points_per_segment < 2:
            num_points_per_segment = 2
        if not self.points or self._num_segments == 0:
            return []

        sampled_points.append(self.points[0].to_qpointf())
        for i in range(self._num_segments):
            segment_cps = self.get_segment_control_points(i)
            if not segment_cps or len(segment_cps) != 4:
                continue

            p0c, p1c, p2c, p3c = (pt.get_coords() for pt in segment_cps)

            for j in range(1, num_points_per_segment + 1):
                t = float(j) / float(num_points_per_segment)
                point_on_curve = self._cubic_bezier_point(t, p0c, p1c, p2c, p3c)
                if not sampled_points or (
                    not math.isclose(point_on_curve.x(), sampled_points[-1].x())
                    or not math.isclose(point_on_curve.y(), sampled_points[-1].y())
                ):
                    sampled_points.append(point_on_curve)
        return sampled_points

    @staticmethod
    def subdivide_segment(
        cps: List[Point], t: float = 0.5
    ) -> Tuple[List[Point], List[Point]]:
        """
        Subdivide um segmento de Bézier cúbico em dois sub-segmentos.
        
        Args:
            cps: Lista de 4 pontos de controle do segmento
            t: Parâmetro de subdivisão (0 a 1)
            
        Returns:
            Tuple[List[Point], List[Point]]: Dois conjuntos de pontos de controle para os sub-segmentos
            
        Raises:
            ValueError: Se não houver exatamente 4 pontos de controle
        """
        if len(cps) != 4:
            raise ValueError(
                "Subdivisão requer 4 pontos de controle para um segmento de Bézier cúbico."
            )

        p0, p1, p2, p3 = cps

        p01 = Point(p0.x + t * (p1.x - p0.x), p0.y + t * (p1.y - p0.y), p0.color)
        p12 = Point(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y), p0.color)
        p23 = Point(p2.x + t * (p3.x - p2.x), p2.y + t * (p3.y - p2.y), p0.color)

        p012 = Point(p01.x + t * (p12.x - p01.x), p01.y + t * (p12.y - p01.y), p0.color)
        p123 = Point(p12.x + t * (p23.x - p12.x), p12.y + t * (p23.y - p12.y), p0.color)

        p0123 = Point(
            p012.x + t * (p123.x - p012.x), p012.y + t * (p123.y - p012.y), p0.color
        )

        curve1_cps = [p0, p01, p012, p0123]

        curve2_cps = [p0123, p123, p23, p3]

        return curve1_cps, curve2_cps

    @staticmethod
    def segment_control_polygon_length(cps: List[Point]) -> float:
        """
        Calcula o comprimento do polígono de controle de um segmento.
        
        Args:
            cps: Lista de 4 pontos de controle
            
        Returns:
            float: Comprimento do polígono de controle
        """
        if len(cps) != 4:
            return float("inf")
        l = 0.0
        for i in range(3):
            dx = cps[i + 1].x - cps[i].x
            dy = cps[i + 1].y - cps[i].y
            l += math.sqrt(dx * dx + dy * dy)
        return l

    @staticmethod
    def segment_bounding_box(
        cps: List[Point],
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Calcula a caixa delimitadora de um segmento.
        
        Args:
            cps: Lista de 4 pontos de controle
            
        Returns:
            Optional[Tuple[float, float, float, float]]: Tupla (x_min, y_min, x_max, y_max) ou None se inválido
        """
        if not cps or len(cps) != 4:
            return None
        xs = [p.x for p in cps]
        ys = [p.y for p in cps]
        return min(xs), min(ys), max(xs), max(ys)

    def __repr__(self) -> str:
        """
        Retorna uma representação textual da curva.
        
        Returns:
            str: String representando a curva com seus segmentos e cor
        """
        points_str = ", ".join(repr(p) for p in self.points)
        return f"BezierCurve(segments={self._num_segments}[{points_str}], color={self.color.name()})"
