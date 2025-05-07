# graphics_editor/utils/clipping.py
import math
from typing import List, Tuple, Optional, Union
from enum import Enum

from PyQt5.QtCore import QRectF

Point2D = Tuple[float, float]

ClipRect = Tuple[float, float, float, float]


EPSILON = 1e-9


def clip_point(point: Point2D, clip_rect: ClipRect) -> Optional[Point2D]:
    """Recorta um único ponto contra o retângulo de recorte."""
    x, y = point
    xmin, ymin, xmax, ymax = clip_rect

    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    if actual_xmin <= x <= actual_xmax and actual_ymin <= y <= actual_ymax:
        return point
    return None


INSIDE = 0b0000
LEFT = 0b0001
RIGHT = 0b0010
BOTTOM = 0b0100
TOP = 0b1000


def _compute_cohen_sutherland_code(x: float, y: float, clip_rect: ClipRect) -> int:
    """Computa o outcode Cohen-Sutherland para um ponto."""
    xmin, ymin, xmax, ymax = clip_rect

    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    code = INSIDE
    if x < actual_xmin:
        code |= LEFT
    elif x > actual_xmax:
        code |= RIGHT
    if y < actual_ymin:
        code |= BOTTOM
    elif y > actual_ymax:
        code |= TOP
    return code


def cohen_sutherland(
    p1: Point2D, p2: Point2D, clip_rect: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    """Recorta um segmento de linha usando o algoritmo Cohen-Sutherland."""
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect

    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)
    ordered_clip_rect = (actual_xmin, actual_ymin, actual_xmax, actual_ymax)

    code1 = _compute_cohen_sutherland_code(x1, y1, ordered_clip_rect)
    code2 = _compute_cohen_sutherland_code(x2, y2, ordered_clip_rect)
    accept = False

    while True:
        if code1 == INSIDE and code2 == INSIDE:
            accept = True
            break
        elif (code1 & code2) != 0:
            break
        else:
            x, y = 0.0, 0.0
            code_out = code1 if code1 != INSIDE else code2

            if code_out & TOP:
                y = actual_ymax
                x = (
                    x1 + (x2 - x1) * (actual_ymax - y1) / (y2 - y1)
                    if abs(y2 - y1) > EPSILON
                    else x1
                )
            elif code_out & BOTTOM:
                y = actual_ymin
                x = (
                    x1 + (x2 - x1) * (actual_ymin - y1) / (y2 - y1)
                    if abs(y2 - y1) > EPSILON
                    else x1
                )
            elif code_out & RIGHT:
                x = actual_xmax
                y = (
                    y1 + (y2 - y1) * (actual_xmax - x1) / (x2 - x1)
                    if abs(x2 - x1) > EPSILON
                    else y1
                )
            elif code_out & LEFT:
                x = actual_xmin
                y = (
                    y1 + (y2 - y1) * (actual_xmin - x1) / (x2 - x1)
                    if abs(x2 - x1) > EPSILON
                    else y1
                )
            else:
                break

            if code_out == code1:
                x1, y1 = x, y
                code1 = _compute_cohen_sutherland_code(x1, y1, ordered_clip_rect)
            else:
                x2, y2 = x, y
                code2 = _compute_cohen_sutherland_code(x2, y2, ordered_clip_rect)

    return ((x1, y1), (x2, y2)) if accept else None


def liang_barsky(
    p1: Point2D, p2: Point2D, clip_rect: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    """Recorta um segmento de linha usando o algoritmo Liang-Barsky."""
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    dx = x2 - x1
    dy = y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - actual_xmin, actual_xmax - x1, y1 - actual_ymin, actual_ymax - y1]
    u1, u2 = 0.0, 1.0

    for k in range(4):
        if abs(p[k]) < EPSILON:
            if q[k] < 0:
                return None
        else:
            r = q[k] / p[k]
            if p[k] < 0:
                u1 = max(u1, r)
            else:
                u2 = min(u2, r)
        if u1 > u2:
            return None

    return ((x1 + u1 * dx, y1 + u1 * dy), (x1 + u2 * dx, y1 + u2 * dy))


def _intersect_polygon_edge(
    p1: Point2D, p2: Point2D, edge_index: int, clip_rect: ClipRect
) -> Point2D:
    xmin, ymin, xmax, ymax = clip_rect
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    x, y = 0.0, 0.0

    try:
        if edge_index == 0:
            x = actual_xmin
            y = y1 + dy * (actual_xmin - x1) / dx if abs(dx) > EPSILON else y1
        elif edge_index == 1:
            x = actual_xmax
            y = y1 + dy * (actual_xmax - x1) / dx if abs(dx) > EPSILON else y1
        elif edge_index == 2:
            y = actual_ymin
            x = x1 + dx * (actual_ymin - y1) / dy if abs(dy) > EPSILON else x1
        elif edge_index == 3:
            y = actual_ymax
            x = x1 + dx * (actual_ymax - y1) / dy if abs(dy) > EPSILON else x1
    except ZeroDivisionError:
        return p1
    return x, y


def _is_inside_edge(p: Point2D, edge_index: int, clip_rect: ClipRect) -> bool:
    xmin, ymin, xmax, ymax = clip_rect
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)
    x, y = p

    if edge_index == 0:
        return x >= actual_xmin
    if edge_index == 1:
        return x <= actual_xmax
    if edge_index == 2:
        return y >= actual_ymin
    if edge_index == 3:
        return y <= actual_ymax
    return False


def sutherland_hodgman(
    polygon_vertices: List[Point2D], clip_rect: ClipRect
) -> List[Point2D]:
    if not polygon_vertices:
        return []
    output_list = list(polygon_vertices)

    for edge_index in range(4):
        input_list = list(output_list)
        output_list.clear()
        if not input_list:
            break

        s = input_list[-1]
        for e in input_list:
            s_inside = _is_inside_edge(s, edge_index, clip_rect)
            e_inside = _is_inside_edge(e, edge_index, clip_rect)

            if e_inside and s_inside:
                output_list.append(e)
            elif e_inside and not s_inside:
                output_list.append(_intersect_polygon_edge(s, e, edge_index, clip_rect))
                output_list.append(e)
            elif s_inside and not e_inside:
                output_list.append(_intersect_polygon_edge(s, e, edge_index, clip_rect))
            s = e
    return output_list
