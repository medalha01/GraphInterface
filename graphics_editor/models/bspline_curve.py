# graphics_editor/models/bspline_curve.py
from typing import List, Tuple, Optional
import numpy as np
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPen, QPainterPath
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsItem
import math  # Adicionado para math.isclose

from .point import Point  # Importação explícita


class BSplineCurve:
    """
    Representa uma curva B-spline, definida por pontos de controle, grau e vetor de nós.
    Utiliza a fórmula de Cox-de Boor para avaliação.
    """

    GRAPHICS_WIDTH = 2  # Espessura visual da curva
    DEFAULT_DEGREE = 3  # Grau padrão da curva B-spline
    # Número de amostras para desenhar/exportar cada trecho da curva entre dois nós distintos.
    DEFAULT_SAMPLES_PER_KNOT_SPAN = 20
    EPSILON = 1e-9  # Para comparações de ponto flutuante

    def __init__(
        self,
        control_points: List[Point],
        degree: Optional[int] = None,
        color: Optional[QColor] = None,
        knots: Optional[np.ndarray] = None,
    ):
        """
        Inicializa a curva B-spline.

        Args:
            control_points: Lista de objetos Point.
            degree: Grau da curva B-spline (padrão é DEFAULT_DEGREE).
            color: Cor da curva (opcional, padrão é preto).
            knots: Vetor de nós (opcional). Se None, um vetor de nós aberto e uniforme é gerado.

        Raises:
            TypeError: Se control_points não for uma lista de Point.
            ValueError: Se o número de pontos de controle for insuficiente para o grau,
                        ou se o vetor de nós fornecido for inválido.
        """
        if not isinstance(control_points, list) or not all(
            isinstance(p, Point) for p in control_points
        ):
            raise TypeError("control_points deve ser uma lista de instâncias de Point.")

        n_plus_1 = len(
            control_points
        )  # n+1 é o número de pontos de controle P0, ..., Pn
        if n_plus_1 < 2:
            raise ValueError("B-spline requer pelo menos 2 pontos de controle.")

        self.control_points: List[Point] = control_points

        # Define o grau 'p'
        _degree = degree if degree is not None else self.DEFAULT_DEGREE
        # O grau 'p' deve ser p <= n (onde n = n_plus_1 - 1).
        # Portanto, p <= len(control_points) - 1.
        self.degree: int = min(_degree, n_plus_1 - 1)
        if self.degree < 1:  # Grau mínimo para uma curva é 1 (polilinha)
            # Ajusta para grau 1 se o grau fornecido for muito baixo para os pontos
            self.degree = 1
            # Ou poderia levantar um erro:
            # raise ValueError(f"Grau da B-spline ({_degree}) inválido para {n_plus_1} pontos. Deve ser >= 1 e <= {n_plus_1 - 1}.")

        self.color: QColor = (
            color if isinstance(color, QColor) and color.isValid() else QColor(Qt.black)
        )

        if knots is not None:
            # Validação básica do vetor de nós fornecido
            # m + 1 nós, onde m = n + p + 1 (n = num_pts-1, p = grau)
            # Número de nós = (num_pts - 1) + grau + 1 + 1 = num_pts + grau + 1
            expected_knot_count = n_plus_1 + self.degree + 1
            if len(knots) != expected_knot_count:
                raise ValueError(
                    f"Vetor de nós com tamanho incorreto. Esperado {expected_knot_count}, recebido {len(knots)}."
                )
            # Verifica se os nós são não-decrescentes
            if not np.all(
                np.diff(knots) >= -self.EPSILON
            ):  # Permite pequena tolerância para igualdade
                raise ValueError("Vetor de nós deve ser não-decrescente.")
            self.knots: np.ndarray = np.array(knots, dtype=float)  # Garante que é float
        else:
            self._generate_clamped_uniform_knot_vector()

    def _generate_clamped_uniform_knot_vector(self) -> None:
        """
        Gera um vetor de nós uniforme e "clamped" (aberto com multiplicidade p+1 nas extremidades).
        Isso faz a curva interpolar os pontos de controle inicial e final.
        O vetor de nós U = {u_0, ..., u_m} tem m+1 nós.
        m = n_idx + p + 1, onde 'n_idx' é o índice do último ponto de controle (P_{n_idx}),
        então n_idx = len(control_points) - 1. 'p' é o grau.
        Total de nós = (len(control_points) - 1) + degree + 1 + 1 = len(control_points) + degree + 1.
        """
        n_plus_1 = len(self.control_points)  # Número de pontos de controle
        p = self.degree  # Grau da curva

        num_knots = n_plus_1 + p + 1
        self.knots = np.zeros(num_knots, dtype=float)

        # Primeiros p+1 nós são 0 (clamped no início)
        for i in range(p + 1):
            self.knots[i] = 0.0

        # Últimos p+1 nós são 1 (clamped no final)
        # Índices de num_knots - (p+1) até num_knots - 1
        for i in range(num_knots - p - 1, num_knots):
            self.knots[i] = 1.0

        # Nós internos são uniformemente espaçados entre 0 e 1.
        # Número de segmentos internos do vetor de nós: (n_plus_1 - 1) - p + 1 = n_plus_1 - p
        # Número de valores de nós internos a serem definidos: n_plus_1 - p - 1
        num_internal_knots_to_generate = n_plus_1 - p - 1
        if num_internal_knots_to_generate > 0:
            # Estes são os nós u_{p+1}, ..., u_{n_idx}
            # (onde n_idx = n_plus_1 - 1)
            # Então, u_{p+1}, ..., u_{n_plus_1 - 1}
            # Ex: n_plus_1=4 (P0,P1,P2,P3), p=2. Nós = 7 (u0..u6).
            #   Clamped: {0,0,0, u3, 1,1,1}. num_internal_knots_to_generate = 4-2-1 = 1. u3 a ser definido.
            #   Intervalo [0,1] dividido em (n_plus_1 - p) partes. (4-2 = 2 partes). u3 = 0.5.
            step = 1.0 / (n_plus_1 - p)
            for i in range(num_internal_knots_to_generate):
                self.knots[p + 1 + i] = (i + 1) * step

    def _cox_de_boor(self, u: float, i: int, p: int) -> float:
        """
        Calcula o valor da i-ésima função base B-spline N_{i,p}(u) de grau p no parâmetro u.
        Implementação recursiva da fórmula de Cox-de Boor.

        Args:
            u: Parâmetro (valor do nó) onde a função base é avaliada.
            i: Índice do ponto de controle associado (0 <= i <= n_idx).
            p: Grau da função base (p >= 0).

        Returns:
            float: Valor da função base N_{i,p}(u).
        """
        # Caso base da recursão
        if p == 0:
            # N_{i,0}(u) é 1 se u_i <= u < u_{i+1}, e 0 caso contrário.
            # Tratamento especial para o último nó u_m=1.0 quando u = u_m
            # Se u_i <= u < u_{i+1}, ou se u == u_{i+1} == u_m (último nó)
            # e u_i <= u. Isso garante que N_{n,0}(1.0) = 1 para nós clampados.
            if (self.knots[i] <= u < self.knots[i + 1]) or (
                math.isclose(u, self.knots[i + 1])
                and math.isclose(self.knots[i + 1], self.knots[-1])
                and self.knots[i] <= u
            ):
                return 1.0
            return 0.0

        # Termos da recursão
        term1, term2 = 0.0, 0.0

        denominator1 = self.knots[i + p] - self.knots[i]
        if abs(denominator1) > self.EPSILON:  # Evita divisão por zero
            term1 = ((u - self.knots[i]) / denominator1) * self._cox_de_boor(
                u, i, p - 1
            )

        denominator2 = self.knots[i + p + 1] - self.knots[i + 1]
        if abs(denominator2) > self.EPSILON:  # Evita divisão por zero
            term2 = ((self.knots[i + p + 1] - u) / denominator2) * self._cox_de_boor(
                u, i + 1, p - 1
            )

        return term1 + term2

    def _evaluate(self, u: float) -> Tuple[float, float]:
        """
        Avalia um ponto na curva B-spline para um dado parâmetro u.
        C(u) = sum_{i=0 to n_idx} N_{i,p}(u) * P_i, onde n_idx = len(control_points)-1.

        Args:
            u: Parâmetro da curva. Para nós "clamped", o intervalo efetivo é [0, 1].
               Será clipado para o domínio válido [knots[degree], knots[len(control_points)]].

        Returns:
            Tuple[float, float]: Coordenadas (x, y) do ponto na curva.
        """
        # O domínio da curva é [u_p, u_{n+1}] ou [u_p, u_{m-p-1}] onde m+1 é o num_knots
        # m = n_idx + p + 1.  Então u_{n_idx+1} = u_{m-p}
        # Para nós clampados, este intervalo é [0, 1].
        u_clamped = np.clip(
            u, self.knots[self.degree], self.knots[len(self.control_points)]
        )
        if math.isclose(u_clamped, 1.0):
            u_clamped = 1.0  # Garante que 1.0 é tratado corretamente

        x, y = 0.0, 0.0
        for i in range(len(self.control_points)):  # Soma de P0 a Pn_idx
            N_ip = self._cox_de_boor(u_clamped, i, self.degree)
            x += N_ip * self.control_points[i].x
            y += N_ip * self.control_points[i].y
        return x, y

    def get_curve_points(
        self, num_samples_per_span: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """
        Gera uma lista de pontos amostrados ao longo da curva B-spline.
        Amostra 'num_samples_per_span' pontos em cada intervalo de nó não-nulo.

        Args:
            num_samples_per_span: Número de pontos para amostrar em cada intervalo de nó.
                                  Se None, usa DEFAULT_SAMPLES_PER_KNOT_SPAN.

        Returns:
            List[Tuple[float, float]]: Lista de coordenadas (x,y) dos pontos da curva.
        """
        if num_samples_per_span is None:
            num_samples_per_span = self.DEFAULT_SAMPLES_PER_KNOT_SPAN
        if num_samples_per_span < 2:
            num_samples_per_span = 2  # Mínimo para desenhar um segmento

        curve_pts: List[Tuple[float, float]] = []

        # Domínio útil da curva para nós clampados: [0, 1]
        # Corresponde a knots[degree] até knots[len(control_points)]
        u_min_domain = self.knots[self.degree]
        u_max_domain = self.knots[len(self.control_points)]

        # Obtém os valores únicos dos nós dentro do domínio da curva para definir os "spans"
        # Ex: Nós {0,0,0, 0.5, 1,1,1}, grau 2. Domínio [0,1]. Nós únicos relevantes: {0, 0.5, 1}.
        # Spans: [0, 0.5], [0.5, 1].
        unique_relevant_knots = sorted(
            list(set(self.knots[self.degree : len(self.control_points) + 1]))
        )

        if not unique_relevant_knots or len(unique_relevant_knots) < 2:
            # Se não há spans (e.g., todos os nós relevantes são iguais, como para grau 0 com 1 ponto)
            # ou apenas um valor de nó único, retorna o ponto avaliado em u_min_domain.
            return [self._evaluate(u_min_domain)]

        # Adiciona o ponto inicial da curva
        curve_pts.append(self._evaluate(u_min_domain))

        for k_idx in range(len(unique_relevant_knots) - 1):
            u_start_span = unique_relevant_knots[k_idx]
            u_end_span = unique_relevant_knots[k_idx + 1]

            # Amostra apenas se o intervalo do nó tiver comprimento > 0
            if abs(u_end_span - u_start_span) > self.EPSILON:
                for i in range(
                    1, num_samples_per_span + 1
                ):  # Amostra de >0 a 1 dentro do span
                    t_in_span = float(i) / num_samples_per_span
                    u_eval = u_start_span + t_in_span * (u_end_span - u_start_span)

                    pt = self._evaluate(u_eval)
                    # Evita pontos duplicados se o último ponto do span anterior for o mesmo
                    if not curve_pts or (
                        not math.isclose(pt[0], curve_pts[-1][0], abs_tol=self.EPSILON)
                        or not math.isclose(
                            pt[1], curve_pts[-1][1], abs_tol=self.EPSILON
                        )
                    ):
                        curve_pts.append(pt)

        # Garante que o último ponto (em u_max_domain) seja adicionado se não foi
        # devido a problemas de amostragem/arredondamento.
        last_pt_eval = self._evaluate(u_max_domain)
        if not curve_pts or (
            not math.isclose(last_pt_eval[0], curve_pts[-1][0], abs_tol=self.EPSILON)
            or not math.isclose(last_pt_eval[1], curve_pts[-1][1], abs_tol=self.EPSILON)
        ):
            curve_pts.append(last_pt_eval)

        return curve_pts

    def create_graphics_item(self) -> QGraphicsPathItem:
        """
        Cria um item gráfico QGraphicsPathItem para a curva B-spline.

        Returns:
            QGraphicsPathItem: Item gráfico da curva.
        """
        path = QPainterPath()
        if (
            len(self.control_points) < self.degree + 1
        ):  # Precisa de pelo menos grau+1 pontos
            # Se não há pontos suficientes para o grau, pode desenhar o polígono de controle
            # ou retornar um caminho vazio. Por simplicidade, caminho vazio.
            if (
                self.control_points
            ):  # Se houver algum ponto, desenha o polígono de controle
                path.moveTo(self.control_points[0].to_qpointf())
                for pt_model in self.control_points[1:]:
                    path.lineTo(pt_model.to_qpointf())
            return QGraphicsPathItem(path)

        curve_display_points = self.get_curve_points()

        if not curve_display_points:
            return QGraphicsPathItem(path)

        path.moveTo(QPointF(curve_display_points[0][0], curve_display_points[0][1]))
        for x, y in curve_display_points[1:]:
            path.lineTo(QPointF(x, y))

        item = QGraphicsPathItem(path)
        pen = QPen(self.color, self.GRAPHICS_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        item.setPen(pen)
        item.setFlag(QGraphicsItem.ItemIsSelectable)
        return item

    def get_coords(self) -> List[Tuple[float, float]]:
        """Retorna as coordenadas (x,y) de todos os pontos de controle."""
        return [p.get_coords() for p in self.control_points]

    def get_center(self) -> Tuple[float, float]:
        """Retorna o centro geométrico da curva (média dos pontos de controle)."""
        if not self.control_points:
            return (0.0, 0.0)

        sum_x = sum(p.x for p in self.control_points)
        sum_y = sum(p.y for p in self.control_points)
        count = len(self.control_points)
        return (sum_x / count, sum_y / count) if count > 0 else (0.0, 0.0)

    def __repr__(self) -> str:
        """Retorna uma representação textual da curva B-spline."""
        cp_repr = ", ".join(repr(p) for p in self.control_points)
        knots_repr = ", ".join(f"{k:.2f}" for k in self.knots)
        return (
            f"BSplineCurve(pontos=[{cp_repr}], grau={self.degree}, "
            f"nós=[{knots_repr}], cor={self.color.name()})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BSplineCurve):
            return NotImplemented
        # Compara com tolerância para o array de nós
        knots_equal = np.allclose(self.knots, other.knots, atol=self.EPSILON)
        return (
            self.control_points == other.control_points
            and self.degree == other.degree
            and knots_equal
            and self.color == other.color
        )
