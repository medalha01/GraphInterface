# graphics_editor/models/bezier_curve.py
import math
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem
from typing import List, Tuple, Optional

from .point import Point


class BezierCurve:
    """Representa uma curva de Bézier cúbica composta (sequência de segmentos)."""

    GRAPHICS_WIDTH = 2  # Espessura visual da curva

    def __init__(self, points: List[Point], color: Optional[QColor] = None):
        """
        Inicializa uma curva de Bézier cúbica composta.

        Args:
            points: Lista ordenada de pontos de controle. O número de pontos
                    deve ser 4 para uma única curva, ou 3*N + 1 para N
                    segmentos conectados (P0, P1, P2, P3, P4, P5, P6...).
            color: Cor da curva.
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
        # Para curvas compostas, após os 4 primeiros, adiciona-se 3 para cada novo segmento
        if n_points > 4 and (n_points - 4) % 3 != 0:
            raise ValueError(
                f"Número inválido de pontos ({n_points}) para curva de Bézier composta. "
                "Deve ser 4 ou 3*N + 1 (onde N é o nº de segmentos)."
            )

        self.points: List[Point] = points
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )
        self._num_segments = (n_points - 1) // 3

    def create_graphics_item(self) -> QGraphicsPathItem:
        """Cria a representação gráfica QGraphicsPathItem."""
        path = QPainterPath()
        if not self.points:
            return QGraphicsPathItem(path)  # Retorna item vazio

        path.moveTo(self.points[0].to_qpointf())

        for i in range(self._num_segments):
            p1_idx = 3 * i + 1
            p2_idx = 3 * i + 2
            p3_idx = 3 * i + 3
            # Verifica se os índices são válidos (redundante se __init__ validou)
            if p3_idx < len(self.points):
                ctrl_pt1 = self.points[p1_idx].to_qpointf()
                ctrl_pt2 = self.points[p2_idx].to_qpointf()
                end_pt = self.points[p3_idx].to_qpointf()
                path.cubicTo(ctrl_pt1, ctrl_pt2, end_pt)

        curve_item = QGraphicsPathItem(path)

        # Aparência
        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        curve_item.setPen(pen)
        # Curvas de Bézier geralmente não são preenchidas
        curve_item.setBrush(Qt.NoBrush)

        # Flags
        curve_item.setFlag(QGraphicsItem.ItemIsSelectable)
        # curve_item.setFlag(QGraphicsItem.ItemIsMovable)

        # Associa dados
        curve_item.setData(0, self)
        return curve_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna lista de coordenadas (x, y) dos pontos de CONTROLE."""
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centroide (média aritmética dos pontos de CONTROLE)."""
        if not self.points:
            return (0.0, 0.0)
        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)
        return (sum_x / count, sum_y / count)

    def get_num_segments(self) -> int:
        """Retorna o número de segmentos cúbicos na curva composta."""
        return self._num_segments

    # --- Métodos para cálculo/amostragem da curva ---
    # Baseado na fórmula P(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3

    @staticmethod
    def _cubic_bezier_point(
        t: float, p0: Point, p1: Point, p2: Point, p3: Point
    ) -> QPointF:
        """Calcula um ponto na curva de Bézier cúbica para um dado t (0 a 1)."""
        # Clamp t to the valid range [0, 1]
        t = max(0.0, min(1.0, t))

        one_minus_t = 1.0 - t
        one_minus_t_sq = one_minus_t * one_minus_t
        one_minus_t_cub = one_minus_t_sq * one_minus_t

        t_sq = t * t
        t_cub = t_sq * t

        x = (
            one_minus_t_cub * p0.x
            + 3.0 * one_minus_t_sq * t * p1.x
            + 3.0 * one_minus_t * t_sq * p2.x
            + t_cub * p3.x
        )
        y = (
            one_minus_t_cub * p0.y
            + 3.0 * one_minus_t_sq * t * p1.y
            + 3.0 * one_minus_t * t_sq * p2.y
            + t_cub * p3.y
        )

        return QPointF(x, y)

    def sample_curve(self, num_points_per_segment: int = 20) -> List[QPointF]:
        """Amostra a curva completa, retornando uma lista de QPointF."""
        sampled_points = []
        if num_points_per_segment < 2:
            num_points_per_segment = 2  # Minimum for a line segment

        if not self.points:
            return []

        sampled_points.append(self.points[0].to_qpointf())  # Start point

        for i in range(self._num_segments):
            p0_idx = 3 * i
            p1_idx = 3 * i + 1
            p2_idx = 3 * i + 2
            p3_idx = 3 * i + 3

            if p3_idx < len(self.points):
                p0 = self.points[p0_idx]
                p1 = self.points[p1_idx]
                p2 = self.points[p2_idx]
                p3 = self.points[p3_idx]

                # Sample segment from t > 0 up to t = 1
                for j in range(1, num_points_per_segment + 1):
                    t = float(j) / float(num_points_per_segment)
                    point_on_curve = self._cubic_bezier_point(t, p0, p1, p2, p3)
                    # Avoid duplicate if it's the start of the next segment and identical
                    if (
                        not sampled_points
                        or not math.isclose(point_on_curve.x(), sampled_points[-1].x())
                        or not math.isclose(point_on_curve.y(), sampled_points[-1].y())
                    ):
                        sampled_points.append(point_on_curve)

        return sampled_points

    def __repr__(self) -> str:
        """Representação textual."""
        points_str = ", ".join(repr(p) for p in self.points)
        return f"BezierCurve(segments={self._num_segments}[{points_str}], color={self.color.name()})"
