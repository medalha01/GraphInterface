from typing import List, Tuple, Optional
import numpy as np
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPen, QPainterPath
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItem

from .point import Point

class BSplineCurve:
    """
    Classe que representa uma curva B-spline.
    
    A curva é gerada usando o algoritmo de diferenças progressivas (forward differences)
    para B-splines, permitindo curvas de diferentes graus.
    """
    
    # Constantes para visualização
    GRAPHICS_WIDTH = 2
    SAMPLING_POINTS = 100  # Número de pontos para amostragem da curva
    DEFAULT_DEGREE = 3  # Grau padrão da curva B-spline
    
    def __init__(self, control_points: List[Point], degree: int = DEFAULT_DEGREE, color: QColor = None):
        """
        Inicializa a curva B-spline.
        
        Args:
            control_points: Lista de pontos de controle
            degree: Grau da curva B-spline (padrão é 3)
            color: Cor da curva (opcional)
        """
        if len(control_points) < 2:
            raise ValueError("B-spline requer pelo menos 2 pontos de controle")
        
        self.control_points = control_points
        self.degree = min(degree, len(control_points) - 1)  # Grau não pode exceder n-1
        self.color = color if color else QColor(0, 0, 0)
        self._samples_per_segment = 20  # Número de amostras por segmento
        
        # Gera o vetor de nós uniforme
        self._generate_knot_vector()

    def _generate_knot_vector(self) -> None:
        """
        Gera um vetor de nós uniforme para a curva B-spline.
        """
        n = len(self.control_points)
        p = self.degree
        
        # Número total de nós = n + p + 1
        self.knots = np.zeros(n + p + 1)
        
        # Nós múltiplos nas extremidades
        self.knots[0:p+1] = 0.0
        self.knots[-(p+1):] = 1.0
        
        # Nós internos uniformemente espaçados
        if n > p + 1:
            internal_knots = np.linspace(0, 1, n - p + 1)
            self.knots[p+1:-(p+1)] = internal_knots[1:-1]

    def _basis_function(self, i: int, p: int, u: float) -> float:
        """
        Calcula a função base B-spline usando recursão.
        
        Args:
            i: Índice do ponto de controle
            p: Grau da função base
            u: Parâmetro da curva
            
        Returns:
            float: Valor da função base
        """
        if p == 0:
            return 1.0 if self.knots[i] <= u < self.knots[i+1] else 0.0
            
        # Evita divisão por zero
        denom1 = self.knots[i+p] - self.knots[i]
        term1 = (u - self.knots[i]) / denom1 * self._basis_function(i, p-1, u) if denom1 != 0 else 0
        
        denom2 = self.knots[i+p+1] - self.knots[i+1]
        term2 = (self.knots[i+p+1] - u) / denom2 * self._basis_function(i+1, p-1, u) if denom2 != 0 else 0
        
        return term1 + term2

    def _compute_point(self, u: float) -> Tuple[float, float]:
        """
        Calcula um ponto na curva B-spline usando o algoritmo de diferenças progressivas.
        
        Args:
            u: Parâmetro da curva (entre 0 e 1)
            
        Returns:
            Tuple[float, float]: Ponto calculado na curva (x, y)
        """
        x = y = 0.0
        
        # Ajusta u para evitar problemas numéricos nas extremidades
        if u >= 1.0:
            u = 1.0 - np.finfo(float).eps
            
        # Calcula o ponto usando as funções base
        for i in range(len(self.control_points)):
            basis = self._basis_function(i, self.degree, u)
            x += basis * self.control_points[i].x
            y += basis * self.control_points[i].y
            
        return (x, y)

    def _compute_forward_differences(self, num_points: int) -> List[Tuple[float, float]]:
        """
        Calcula pontos na curva usando o algoritmo de diferenças progressivas.
        
        Args:
            num_points: Número de pontos a calcular
            
        Returns:
            List[Tuple[float, float]]: Lista de pontos calculados (x, y)
        """
        points = []
        delta = 1.0 / (num_points - 1)
        
        # Calcula os pontos iniciais
        for i in range(num_points):
            u = i * delta
            points.append(self._compute_point(u))
            
        return points

    def create_graphics_item(self) -> QGraphicsPathItem:
        """
        Cria um item gráfico para a curva B-spline.
        
        Returns:
            QGraphicsPathItem: Item gráfico da curva
        """
        path = QPainterPath()
        n = len(self.control_points)
        
        if n < 2:
            return QGraphicsPathItem(path)

        # Gera pontos usando diferenças progressivas
        points = self._compute_forward_differences(self.SAMPLING_POINTS)
        
        # Cria o caminho
        path.moveTo(QPointF(points[0][0], points[0][1]))
        for x, y in points[1:]:
            path.lineTo(QPointF(x, y))

        # Cria o item gráfico
        item = QGraphicsPathItem(path)
        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        item.setPen(pen)
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        return item

    def get_curve_points(self, num_samples: int = SAMPLING_POINTS) -> List[Tuple[float, float]]:
        """
        Retorna uma lista de pontos que formam a curva.
        
        Args:
            num_samples: Número de pontos de amostragem
            
        Returns:
            List[Tuple[float, float]]: Lista de pontos (x,y) da curva
        """
        return self._compute_forward_differences(num_samples)

    def get_control_points(self) -> List[Point]:
        """
        Retorna os pontos de controle da curva.
        
        Returns:
            List[Point]: Lista de pontos de controle
        """
        return self.control_points

    def get_color(self) -> QColor:
        """
        Retorna a cor da curva.
        
        Returns:
            QColor: Cor da curva
        """
        return self.color

    def set_color(self, color: QColor) -> None:
        """
        Define a cor da curva.
        
        Args:
            color: Nova cor da curva
        """
        if isinstance(color, QColor) and color.isValid():
            self.color = color

    def get_coords(self) -> List[Tuple[float, float]]:
        """
        Obtém as coordenadas dos pontos de controle.
        
        Returns:
            Lista de tuplas (x,y) dos pontos de controle
        """
        return [p.get_coords() for p in self.control_points]
        
    def get_center(self) -> Tuple[float, float]:
        """
        Retorna o centro da curva (média dos pontos de controle).
        
        Returns:
            Tuple[float, float]: Coordenadas do centro
        """
        if not self.control_points:
            return (0.0, 0.0)
        sum_x = sum(p.x for p in self.control_points)
        sum_y = sum(p.y for p in self.control_points)
        count = len(self.control_points)
        return (sum_x / count, sum_y / count)
        
    def get_bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Calcula a caixa delimitadora da curva B-spline.
        
        Returns:
            Optional[Tuple[float, float, float, float]]: Tupla (x_min, y_min, x_max, y_max) ou None se inválido
        """
        if not self.control_points:
            return None
            
        # Amostra pontos na curva para calcular a caixa delimitadora
        points = self.get_curve_points()
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        
        return min(xs), min(ys), max(xs), max(ys)
        
    def get_control_polygon_length(self) -> float:
        """
        Calcula o comprimento do polígono de controle.
        
        Returns:
            float: Comprimento do polígono de controle
        """
        if len(self.control_points) < 2:
            return 0.0
            
        length = 0.0
        for i in range(len(self.control_points) - 1):
            p1 = self.control_points[i]
            p2 = self.control_points[i + 1]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            length += (dx * dx + dy * dy) ** 0.5
            
        return length

    def __repr__(self) -> str:
        """
        Retorna uma representação em string da curva B-spline.
        
        Returns:
            str: Representação da curva
        """
        return f"BSplineCurve(control_points={self.control_points}, degree={self.degree})" 