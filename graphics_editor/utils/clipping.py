"""
Módulo que implementa algoritmos de recorte (clipping) para gráficos 2D.

Este módulo contém implementações de algoritmos clássicos de recorte:
- Cohen-Sutherland: Para recorte de segmentos de linha
- Liang-Barsky: Para recorte de segmentos de linha (alternativa)
- Sutherland-Hodgman: Para recorte de polígonos

Os algoritmos suportam recorte contra um retângulo arbitrário.
"""

# graphics_editor/utils/clipping.py
import math
from typing import List, Tuple, Optional, Union
from enum import Enum

from PyQt5.QtCore import QRectF

Point2D = Tuple[float, float]

# (xmin, ymin, xmax, ymax) - QRectF usa (left, top, width, height)
# Este ClipRect assume xmin < xmax e ymin < ymax após normalização.
ClipRect = Tuple[float, float, float, float]

EPSILON = 1e-9  # Pequena tolerância para comparações de ponto flutuante


def qrectf_to_cliprect(qrect: QRectF) -> ClipRect:
    """Converte um QRectF para o formato de tupla (xmin, ymin, xmax, ymax), garantindo normalização."""
    norm_qrect = qrect.normalized()  # Garante que largura e altura sejam positivas
    return (
        norm_qrect.left(),
        norm_qrect.top(),
        norm_qrect.right(),
        norm_qrect.bottom(),
    )


def clip_point(point: Point2D, clip_rect_tuple: ClipRect) -> Optional[Point2D]:
    """
    Recorta um único ponto contra o retângulo de recorte.

    Args:
        point: Ponto (x, y) a ser recortado.
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        Optional[Point2D]: O ponto se estiver dentro do retângulo, None caso contrário.
    """
    x, y = point
    xmin, ymin, xmax, ymax = clip_rect_tuple  # Assume xmin <= xmax, ymin <= ymax

    if xmin <= x <= xmax and ymin <= y <= ymax:
        return point
    return None


# Códigos de região para Cohen-Sutherland
INSIDE = 0b0000  # 0
LEFT = 0b0001  # 1
RIGHT = 0b0010  # 2
BOTTOM = 0b0100  # 4 (y < ymin, considerando y aumentando para baixo como no Qt)
TOP = 0b1000  # 8 (y > ymax)


def _compute_cohen_sutherland_code(
    x: float, y: float, clip_rect_tuple: ClipRect
) -> int:
    """
    Computa o "outcode" de Cohen-Sutherland para um ponto em relação a um retângulo de recorte.

    Args:
        x: Coordenada x do ponto.
        y: Coordenada y do ponto.
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        int: Código de região do ponto.
    """
    xmin, ymin, xmax, ymax = clip_rect_tuple  # Assume xmin <= xmax, ymin <= ymax

    code = INSIDE
    if x < xmin:
        code |= LEFT
    elif x > xmax:
        code |= RIGHT
    if y < ymin:
        code |= BOTTOM  # y < ymin (acima de ymin, pois y cresce para baixo)
    elif y > ymax:
        code |= TOP  # y > ymax (abaixo de ymax)
    return code


def cohen_sutherland(
    p1: Point2D, p2: Point2D, clip_rect_tuple: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    """
    Recorta um segmento de linha [p1, p2] usando o algoritmo Cohen-Sutherland.

    Args:
        p1: Ponto inicial (x1, y1) do segmento.
        p2: Ponto final (x2, y2) do segmento.
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        Optional[Tuple[Point2D, Point2D]]: O segmento recortado (pode ser o original,
                                            um subsegmento, ou None se totalmente fora).
    """
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect_tuple  # Assumido normalizado

    code1 = _compute_cohen_sutherland_code(x1, y1, clip_rect_tuple)
    code2 = _compute_cohen_sutherland_code(x2, y2, clip_rect_tuple)

    while True:
        if not (code1 | code2):  # Aceitação trivial: ambos os pontos dentro
            return ((x1, y1), (x2, y2))
        elif code1 & code2:  # Rejeição trivial: ambos fora e na mesma região "externa"
            return None
        else:  # Segmento precisa ser recortado
            # Escolhe um ponto fora do retângulo
            code_out = (
                code1 if code1 else code2
            )  # Se code1 != INSIDE, usa code1, senão usa code2

            x, y = 0.0, 0.0  # Ponto de interseção a ser calculado

            # Encontra o ponto de interseção com uma das bordas do retângulo
            if code_out & TOP:  # Interseção com a borda superior (y = ymax)
                x = (
                    x1 + (x2 - x1) * (ymax - y1) / (y2 - y1)
                    if abs(y2 - y1) > EPSILON
                    else x1
                )
                y = ymax
            elif code_out & BOTTOM:  # Interseção com a borda inferior (y = ymin)
                x = (
                    x1 + (x2 - x1) * (ymin - y1) / (y2 - y1)
                    if abs(y2 - y1) > EPSILON
                    else x1
                )
                y = ymin
            elif code_out & RIGHT:  # Interseção com a borda direita (x = xmax)
                y = (
                    y1 + (y2 - y1) * (xmax - x1) / (x2 - x1)
                    if abs(x2 - x1) > EPSILON
                    else y1
                )
                x = xmax
            elif code_out & LEFT:  # Interseção com a borda esquerda (x = xmin)
                y = (
                    y1 + (y2 - y1) * (xmin - x1) / (x2 - x1)
                    if abs(x2 - x1) > EPSILON
                    else y1
                )
                x = xmin
            # else: break # Não deveria acontecer se a lógica acima estiver correta

            # Atualiza o ponto que estava fora com o ponto de interseção
            if code_out == code1:
                x1, y1 = x, y
                code1 = _compute_cohen_sutherland_code(x1, y1, clip_rect_tuple)
            else:
                x2, y2 = x, y
                code2 = _compute_cohen_sutherland_code(x2, y2, clip_rect_tuple)


def liang_barsky(
    p1: Point2D, p2: Point2D, clip_rect_tuple: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    """
    Recorta um segmento de linha [p1, p2] usando o algoritmo Liang-Barsky.

    Args:
        p1: Ponto inicial (x1, y1) do segmento.
        p2: Ponto final (x2, y2) do segmento.
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        Optional[Tuple[Point2D, Point2D]]: O segmento recortado ou None.
    """
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect_tuple  # Assumido normalizado

    dx = x2 - x1
    dy = y2 - y1

    # Parâmetros p e q para as 4 bordas (esquerda, direita, inferior, superior)
    p = [-dx, dx, -dy, dy]
    q = [x1 - xmin, xmax - x1, y1 - ymin, ymax - y1]
    # Nota: Para coordenadas de tela (y para baixo), ymin é a borda "de cima"
    # e ymax é a borda "de baixo". A formulação para 'p' e 'q' de y está correta para este caso.

    u1, u2 = 0.0, 1.0  # Parâmetros t para o segmento de linha

    for k in range(4):  # Para cada uma das 4 bordas
        if abs(p[k]) < EPSILON:  # Linha paralela à k-ésima borda
            if q[k] < 0:  # Linha fora e paralela -> rejeita
                return None
        else:
            r = q[k] / p[k]
            if p[k] < 0:  # Linha entra na região de recorte a partir desta borda
                u1 = max(u1, r)
            else:  # Linha sai da região de recorte a partir desta borda
                u2 = min(u2, r)

        if u1 > u2:  # Segmento totalmente fora
            return None

    # Se u1 <= u2, o segmento (ou parte dele) está dentro
    # Calcula os novos pontos do segmento recortado
    clipped_x1 = x1 + u1 * dx
    clipped_y1 = y1 + u1 * dy
    clipped_x2 = x1 + u2 * dx
    clipped_y2 = y1 + u2 * dy

    return ((clipped_x1, clipped_y1), (clipped_x2, clipped_y2))


def _intersect_polygon_edge(
    p1: Point2D, p2: Point2D, edge_index: int, clip_rect_tuple: ClipRect
) -> Point2D:
    """
    Calcula a interseção de um segmento de polígono [p1, p2] com uma das bordas do retângulo de recorte.
    Usado por Sutherland-Hodgman.

    Args:
        p1, p2: Pontos do segmento da aresta do polígono.
        edge_index: Índice da borda do retângulo (0=esquerda, 1=direita, 2=inferior(ymin), 3=superior(ymax)).
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        Point2D: Ponto de interseção.
    """
    xmin, ymin, xmax, ymax = clip_rect_tuple
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    intersect_x, intersect_y = 0.0, 0.0

    if edge_index == 0:  # Borda Esquerda (x = xmin)
        intersect_x = xmin
        intersect_y = y1 + dy * (xmin - x1) / dx if abs(dx) > EPSILON else y1
    elif edge_index == 1:  # Borda Direita (x = xmax)
        intersect_x = xmax
        intersect_y = y1 + dy * (xmax - x1) / dx if abs(dx) > EPSILON else y1
    elif edge_index == 2:  # Borda Inferior (y = ymin, "de cima" nas coords de tela)
        intersect_y = ymin
        intersect_x = x1 + dx * (ymin - y1) / dy if abs(dy) > EPSILON else x1
    elif edge_index == 3:  # Borda Superior (y = ymax, "de baixo" nas coords de tela)
        intersect_y = ymax
        intersect_x = x1 + dx * (ymax - y1) / dy if abs(dy) > EPSILON else x1

    return intersect_x, intersect_y


def _is_inside_edge(p: Point2D, edge_index: int, clip_rect_tuple: ClipRect) -> bool:
    """
    Verifica se um ponto 'p' está do lado "interno" de uma borda específica do retângulo de recorte.
    Usado por Sutherland-Hodgman.

    Args:
        p: Ponto (x,y) a ser verificado.
        edge_index: Índice da borda (0=esquerda, 1=direita, 2=inferior(ymin), 3=superior(ymax)).
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        bool: True se o ponto está do lado interno da borda, False caso contrário.
    """
    xmin, ymin, xmax, ymax = clip_rect_tuple
    x, y = p

    if edge_index == 0:
        return x >= xmin  # Para borda esquerda, "dentro" é x >= xmin
    if edge_index == 1:
        return x <= xmax  # Para borda direita, "dentro" é x <= xmax
    if edge_index == 2:
        return (
            y >= ymin
        )  # Para borda inferior (ymin), "dentro" é y >= ymin (lembre-se que y cresce para baixo)
    if edge_index == 3:
        return y <= ymax  # Para borda superior (ymax), "dentro" é y <= ymax
    return False  # Índice de borda inválido


def sutherland_hodgman(
    polygon_vertices: List[Point2D], clip_rect_tuple: ClipRect
) -> List[Point2D]:
    """
    Recorta um polígono (lista de vértices) contra um retângulo de recorte usando Sutherland-Hodgman.

    Args:
        polygon_vertices: Lista de vértices (x,y) do polígono. A ordem (horário/anti-horário) é preservada.
        clip_rect_tuple: Retângulo de recorte (xmin, ymin, xmax, ymax), já normalizado.

    Returns:
        List[Point2D]: Lista de vértices do polígono recortado (pode ser vazia).
    """
    if not polygon_vertices:
        return []

    clipped_polygon = list(polygon_vertices)

    # Itera sobre as 4 bordas do retângulo de recorte
    for edge_idx in range(
        4
    ):  # 0:Esquerda, 1:Direita, 2:Inferior(ymin), 3:Superior(ymax)
        input_vertices = list(clipped_polygon)  # Vértices da iteração anterior
        clipped_polygon.clear()  # Reinicia a lista de saída para esta borda

        if (
            not input_vertices
        ):  # Se o polígono foi completamente clipado por uma borda anterior
            break

        # 's' é o ponto inicial da aresta atual do polígono, 'e' é o ponto final
        s_point = input_vertices[
            -1
        ]  # Começa com a aresta do último para o primeiro vértice
        for e_point in input_vertices:
            s_is_inside = _is_inside_edge(s_point, edge_idx, clip_rect_tuple)
            e_is_inside = _is_inside_edge(e_point, edge_idx, clip_rect_tuple)

            if s_is_inside and e_is_inside:  # Caso 1: Ambos dentro -> Adiciona 'e'
                clipped_polygon.append(e_point)
            elif (
                s_is_inside and not e_is_inside
            ):  # Caso 2: 's' dentro, 'e' fora -> Adiciona interseção
                intersection = _intersect_polygon_edge(
                    s_point, e_point, edge_idx, clip_rect_tuple
                )
                clipped_polygon.append(intersection)
            elif (
                not s_is_inside and e_is_inside
            ):  # Caso 3: 's' fora, 'e' dentro -> Adiciona interseção e 'e'
                intersection = _intersect_polygon_edge(
                    s_point, e_point, edge_idx, clip_rect_tuple
                )
                clipped_polygon.append(intersection)
                clipped_polygon.append(e_point)
            # Caso 4: Ambos fora -> Não adiciona nada

            s_point = e_point  # Avança para a próxima aresta

    return clipped_polygon
