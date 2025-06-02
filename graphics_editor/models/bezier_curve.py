# graphics_editor/models/bezier_curve.py
import math
import numpy as np
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem
from typing import List, Tuple, Optional, Union

from .point import Point  # Importação explícita


class BezierCurve:
    """
    Representa uma curva de Bézier cúbica composta (sequência de segmentos C0).
    Cada segmento cúbico é definido por 4 pontos de controle.
    Uma curva composta com N segmentos terá 3*N + 1 pontos de controle.

    Responsável por:
    - Gerenciar múltiplos segmentos de curva de Bézier.
    - Calcular pontos ao longo da curva (amostragem).
    - Subdividir segmentos da curva (para algoritmos de recorte).
    - Criar a representação gráfica QGraphicsItem da curva.
    """

    GRAPHICS_WIDTH = 2  # Espessura visual da curva
    # Limiar para subdivisão adaptativa da curva (usado em algoritmos de recorte)
    SUBDIVISION_THRESHOLD = 1.0
    MAX_SUBDIVISION_DEPTH = 5  # Profundidade máxima de subdivisão (para recorte)

    def __init__(self, points: List[Point], color: Optional[QColor] = None):
        """
        Inicializa uma curva de Bézier com pontos de controle.

        Args:
            points: Lista de objetos Point. Deve ter 4, 7, 10, ... pontos
                    (3*N_segmentos + 1).
            color: Cor da curva (opcional, padrão é preto).

        Raises:
            TypeError: Se 'points' não for uma lista de instâncias de Point.
            ValueError: Se o número de pontos for inválido para uma curva composta.
        """
        if not isinstance(points, list) or not all(
            isinstance(p, Point) for p in points
        ):
            raise TypeError(
                "Argumento 'points' deve ser uma lista de instâncias de Point."
            )

        n_points = len(points)
        if n_points < 4:  # Mínimo para um segmento cúbico
            raise ValueError(
                f"Curva de Bézier requer pelo menos 4 pontos de controle (recebeu {n_points})."
            )
        # Para uma curva composta C0, o número de pontos é 3*N_segmentos + 1.
        # (n_points - 1) deve ser um múltiplo de 3.
        if (n_points - 1) % 3 != 0:
            raise ValueError(
                f"Número inválido de pontos ({n_points}) para curva de Bézier composta. "
                "Deve ser 4, 7, 10,... (i.e., 3*N + 1, onde N é o nº de segmentos)."
            )

        self.points: List[Point] = points
        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )
        self._num_segments: int = (n_points - 1) // 3

    def get_segment_control_points(self, segment_index: int) -> Optional[List[Point]]:
        """
        Retorna os 4 pontos de controle (objetos Point) para um segmento específico.

        Args:
            segment_index: Índice do segmento desejado (0-based).

        Returns:
            Optional[List[Point]]: Lista com 4 objetos Point ou None se o índice for inválido.
        """
        if not (0 <= segment_index < self._num_segments):
            return None
        # O primeiro ponto de controle do segmento 'i' é o ponto de índice 3*i na lista geral.
        # O segmento 'i' usa os pontos self.points[3*i] até self.points[3*i + 3].
        start_idx = 3 * segment_index
        return self.points[start_idx : start_idx + 4]

    def create_graphics_item(self) -> QGraphicsPathItem:
        """
        Cria a representação gráfica da curva de Bézier como um QGraphicsPathItem.

        Returns:
            QGraphicsPathItem: Item gráfico representando a curva.
        """
        path = QPainterPath()
        if not self.points or self._num_segments == 0:  # Defensivo
            return QGraphicsPathItem(path)  # Retorna item com caminho vazio

        path.moveTo(self.points[0].to_qpointf())  # Começa no primeiro ponto da curva

        for i in range(self._num_segments):
            segment_cps = self.get_segment_control_points(i)
            if segment_cps and len(segment_cps) == 4:
                # Os pontos de controle para path.cubicTo são P1, P2, P3 do segmento.
                # P0 do segmento é o ponto final do segmento anterior (ou o moveTo inicial).
                ctrl_pt1_q = segment_cps[1].to_qpointf()  # P(3i+1)
                ctrl_pt2_q = segment_cps[2].to_qpointf()  # P(3i+2)
                end_pt_q = segment_cps[3].to_qpointf()  # P(3i+3)
                path.cubicTo(ctrl_pt1_q, ctrl_pt2_q, end_pt_q)

        curve_item = QGraphicsPathItem(path)
        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        pen.setJoinStyle(
            Qt.RoundJoin
        )  # Aparência das junções (embora Bézier C0 sejam suaves)
        pen.setCapStyle(Qt.RoundCap)  # Aparência das pontas da curva
        curve_item.setPen(pen)
        curve_item.setFlag(QGraphicsItem.ItemIsSelectable)
        return curve_item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna as coordenadas (x,y) de todos os pontos de controle."""
        return [p.get_coords() for p in self.points]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centro geométrico da curva (média dos pontos de controle)."""
        if not self.points:
            return (0.0, 0.0)  # Defensivo

        sum_x = sum(p.x for p in self.points)
        sum_y = sum(p.y for p in self.points)
        count = len(self.points)

        return (sum_x / count, sum_y / count) if count > 0 else (0.0, 0.0)

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
        """
        Calcula um ponto em um único segmento de Bézier cúbico para um parâmetro t.
        Usa a fórmula de Bernstein.

        Args:
            t: Parâmetro da curva (0.0 a 1.0).
            p0_coords, p1_coords, p2_coords, p3_coords: Coordenadas dos 4 pontos de controle do segmento.

        Returns:
            QPointF: Ponto calculado na curva.
        """
        t = max(0.0, min(1.0, t))  # Garante que t está em [0, 1]
        one_minus_t = 1.0 - t

        # Polinômios de Bernstein para Bézier cúbica
        b0 = one_minus_t**3
        b1 = 3 * one_minus_t**2 * t
        b2 = 3 * one_minus_t * t**2
        b3 = t**3

        x = (
            b0 * p0_coords[0]
            + b1 * p1_coords[0]
            + b2 * p2_coords[0]
            + b3 * p3_coords[0]
        )
        y = (
            b0 * p0_coords[1]
            + b1 * p1_coords[1]
            + b2 * p2_coords[1]
            + b3 * p3_coords[1]
        )

        return QPointF(x, y)

    def sample_curve(self, num_points_per_segment: int = 20) -> List[QPointF]:
        """
        Amostra pontos ao longo de toda a curva de Bézier composta.

        Args:
            num_points_per_segment: Número de pontos a amostrar por segmento cúbico.
                                    O total de pontos será aproximadamente num_segments * num_points_per_segment + 1.

        Returns:
            List[QPointF]: Lista de QPointF amostrados ao longo da curva.
        """
        sampled_points: List[QPointF] = []
        if num_points_per_segment < 1:
            num_points_per_segment = 1  # Mínimo 1 amostra além do início
        if not self.points or self._num_segments == 0:
            return []

        sampled_points.append(
            self.points[0].to_qpointf()
        )  # Adiciona o primeiro ponto da curva

        for i in range(self._num_segments):
            segment_cps_models = self.get_segment_control_points(i)
            if not segment_cps_models:
                continue  # Segurança

            # Extrai coordenadas dos modelos Point
            p0c, p1c, p2c, p3c = (pt.get_coords() for pt in segment_cps_models)

            # Amostra de t > 0 até t = 1 para cada segmento
            # O ponto t=0 do segmento já foi adicionado (seja como ponto inicial ou final do segmento anterior)
            for j in range(1, num_points_per_segment + 1):
                t = float(j) / float(num_points_per_segment)
                point_on_curve = self._cubic_bezier_point(t, p0c, p1c, p2c, p3c)

                # Evita duplicatas se segmentos se conectam perfeitamente
                # e num_points_per_segment é baixo.
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
        Subdivide um segmento de Bézier cúbico em dois sub-segmentos no parâmetro 't'
        usando o algoritmo de De Casteljau.

        Args:
            cps: Lista de 4 objetos Point (pontos de controle do segmento).
            t: Parâmetro de subdivisão (entre 0 e 1).

        Returns:
            Tuple[List[Point], List[Point]]: Dois conjuntos de 4 objetos Point,
                                             representando os pontos de controle dos dois novos sub-segmentos.
        Raises:
            ValueError: Se 'cps' não contiver exatamente 4 pontos.
        """
        if len(cps) != 4:
            raise ValueError(
                "Subdivisão requer 4 pontos de controle para um segmento Bézier cúbico."
            )

        p0, p1, p2, p3 = cps
        color = p0.color  # Preserva a cor original nos novos pontos

        # Algoritmo de De Casteljau para subdivisão
        # Camada 1 de interpolação linear
        p01 = Point(p0.x + t * (p1.x - p0.x), p0.y + t * (p1.y - p0.y), color)
        p12 = Point(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y), color)
        p23 = Point(p2.x + t * (p3.x - p2.x), p2.y + t * (p3.y - p2.y), color)

        # Camada 2 de interpolação linear
        p012 = Point(p01.x + t * (p12.x - p01.x), p01.y + t * (p12.y - p01.y), color)
        p123 = Point(p12.x + t * (p23.x - p12.x), p12.y + t * (p23.y - p12.y), color)

        # Camada 3 - Ponto na curva em 't', que é o ponto de junção dos dois sub-segmentos
        p0123 = Point(
            p012.x + t * (p123.x - p012.x), p012.y + t * (p123.y - p012.y), color
        )

        # Pontos de controle para a primeira sub-curva
        curve1_cps = [p0, p01, p012, p0123]
        # Pontos de controle para a segunda sub-curva
        curve2_cps = [p0123, p123, p23, p3]

        return curve1_cps, curve2_cps

    @staticmethod
    def segment_control_polygon_length(cps: List[Point]) -> float:
        """
        Calcula o comprimento do polígono de controle de um segmento de Bézier cúbico.

        Args:
            cps: Lista de 4 objetos Point (pontos de controle do segmento).

        Returns:
            float: Comprimento do polígono de controle. Retorna float('inf') se 'cps' for inválido.
        """
        if len(cps) != 4:
            return float("inf")

        length = 0.0
        for i in range(
            3
        ):  # São 3 segmentos no polígono de controle (P0-P1, P1-P2, P2-P3)
            dx = cps[i + 1].x - cps[i].x
            dy = cps[i + 1].y - cps[i].y
            length += math.sqrt(dx * dx + dy * dy)
        return length

    @staticmethod
    def segment_bounding_box(
        cps: List[Point],
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Calcula a caixa delimitadora (bounding box) dos pontos de controle de um segmento.
        Nota: A curva real pode se estender ligeiramente para fora desta caixa. Para uma
        caixa exata, os extremos da curva precisariam ser calculados analiticamente (envolvendo derivadas).

        Args:
            cps: Lista de 4 objetos Point (pontos de controle do segmento).

        Returns:
            Optional[Tuple[float, float, float, float]]: Tupla (x_min, y_min, x_max, y_max)
                                                         ou None se 'cps' for inválido.
        """
        if not cps or len(cps) != 4:
            return None

        xs = [p.x for p in cps]
        ys = [p.y for p in cps]

        return min(xs), min(ys), max(xs), max(ys)

    def __repr__(self) -> str:
        """Retorna uma representação textual da curva de Bézier."""
        points_str = ", ".join(repr(p) for p in self.points)
        return (
            f"BezierCurve(segmentos={self._num_segments}, pontos=[{points_str}], "
            f"cor={self.color.name()})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BezierCurve):
            return NotImplemented
        return (
            self.points == other.points
            and self.color == other.color
            and self._num_segments == other._num_segments
        )
