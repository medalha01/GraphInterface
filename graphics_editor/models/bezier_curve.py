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
        # (n_points - 4) must be a multiple of 3. So (n_points - 1) must be a multiple of 3.
        if (n_points - 1) % 3 != 0:  # Simplified check from (n_points - 4) % 3 != 0
            raise ValueError(
                f"Número inválido de pontos ({n_points}) para curva de Bézier composta. "
                "Deve ser 4, 7, 10,... (i.e., 3*N + 1, onde N é o nº de segmentos)."
            )

        self.points: List[Point] = points
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )
        self._num_segments = (n_points - 1) // 3

    def create_graphics_item(self) -> QGraphicsPathItem:
        """Cria a representação gráfica QGraphicsPathItem."""
        path = QPainterPath()
        if not self.points or self._num_segments == 0:  # Check segments too
            return QGraphicsPathItem(path)  # Retorna item vazio

        path.moveTo(self.points[0].to_qpointf())

        for i in range(self._num_segments):
            p0_idx = (
                3 * i
            )  # Start of current segment is end of previous, or first point
            p1_idx = 3 * i + 1
            p2_idx = 3 * i + 2
            p3_idx = 3 * i + 3

            # p0 is implicitly self.points[p0_idx] for the path segment
            # QPainterPath.cubicTo uses the current position as p0.
            if p3_idx < len(self.points):  # Ensure all points for this segment exist
                ctrl_pt1 = self.points[p1_idx].to_qpointf()
                ctrl_pt2 = self.points[p2_idx].to_qpointf()
                end_pt = self.points[p3_idx].to_qpointf()
                path.cubicTo(ctrl_pt1, ctrl_pt2, end_pt)

        curve_item = QGraphicsPathItem(path)

        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        curve_item.setPen(pen)

        curve_item.setFlag(QGraphicsItem.ItemIsSelectable)
        # curve_item.setFlag(QGraphicsItem.ItemIsMovable) #

        # SceneController will handle setting SC_ORIGINAL_OBJECT_KEY and SC_CURRENT_REPRESENTATION_KEY
        # curve_item.setData(0, self) # Removed as per issue #6
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
        if count == 0:
            return (0.0, 0.0)  # Avoid division by zero
        return (sum_x / count, sum_y / count)

    def get_num_segments(self) -> int:
        """Retorna o número de segmentos cúbicos na curva composta."""
        return self._num_segments

    @staticmethod
    def _cubic_bezier_point(
        t: float,
        p0_coords: Tuple[float, float],
        p1_coords: Tuple[float, float],
        p2_coords: Tuple[float, float],
        p3_coords: Tuple[float, float],
    ) -> QPointF:
        """Calcula um ponto na curva de Bézier cúbica para um dado t (0 a 1). Takes coordinate tuples."""
        t = max(0.0, min(1.0, t))

        one_minus_t = 1.0 - t
        one_minus_t_sq = one_minus_t * one_minus_t
        one_minus_t_cub = one_minus_t_sq * one_minus_t

        t_sq = t * t
        t_cub = t_sq * t

        x = (
            one_minus_t_cub * p0_coords[0]
            + 3.0 * one_minus_t_sq * t * p1_coords[0]
            + 3.0 * one_minus_t * t_sq * p2_coords[0]
            + t_cub * p3_coords[0]
        )
        y = (
            one_minus_t_cub * p0_coords[1]
            + 3.0 * one_minus_t_sq * t * p1_coords[1]
            + 3.0 * one_minus_t * t_sq * p2_coords[1]
            + t_cub * p3_coords[1]
        )

        return QPointF(x, y)

    def sample_curve(self, num_points_per_segment: int = 20) -> List[QPointF]:
        """Amostra a curva completa, retornando uma lista de QPointF."""
        sampled_points = []
        if num_points_per_segment < 2:
            num_points_per_segment = 2  # Minimum to define a line segment

        if not self.points or self._num_segments == 0:
            return []

        # Start with the first control point of the curve
        sampled_points.append(self.points[0].to_qpointf())

        for i in range(self._num_segments):
            p0_model = self.points[3 * i]
            p1_model = self.points[3 * i + 1]
            p2_model = self.points[3 * i + 2]
            p3_model = self.points[3 * i + 3]

            p0c, p1c, p2c, p3c = (
                p0_model.get_coords(),
                p1_model.get_coords(),
                p2_model.get_coords(),
                p3_model.get_coords(),
            )

            # Sample from t > 0 up to t = 1 for this segment
            for j in range(1, num_points_per_segment + 1):
                t = float(j) / float(num_points_per_segment)
                point_on_curve = self._cubic_bezier_point(t, p0c, p1c, p2c, p3c)

                # Add point if it's distinct from the last one (avoids duplicates at segment joins if t=0/1 included)
                if not math.isclose(
                    point_on_curve.x(), sampled_points[-1].x()
                ) or not math.isclose(point_on_curve.y(), sampled_points[-1].y()):
                    sampled_points.append(point_on_curve)
                elif (
                    j == num_points_per_segment
                    and (  # Ensure last point of segment is added if distinct
                        not math.isclose(point_on_curve.x(), sampled_points[-1].x())
                        or not math.isclose(point_on_curve.y(), sampled_points[-1].y())
                    )
                ):
                    sampled_points.append(point_on_curve)

        return sampled_points

    def __repr__(self) -> str:
        """Representação textual."""
        points_str = ", ".join(repr(p) for p in self.points)
        return f"BezierCurve(segments={self._num_segments}[{points_str}], color={self.color.name()})"
