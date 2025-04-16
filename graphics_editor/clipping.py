# graphics_editor/clipping.py
import math
from typing import List, Tuple, Optional, Union

from PyQt5.QtCore import QRectF, QPointF

Point2D = Tuple[float, float]
ClipRect = Tuple[float, float, float, float]


def clip_point(point: Point2D, clip_rect: ClipRect) -> Optional[Point2D]:
    x, y = point
    xmin, ymin, xmax, ymax = clip_rect
    if xmin <= x <= xmax and ymin <= y <= ymax:
        return point
    return None


INSIDE = 0b0000
LEFT = 0b0001
RIGHT = 0b0010
BOTTOM = 0b0100
TOP = 0b1000


def _compute_cohen_sutherland_code(x: float, y: float, clip_rect: ClipRect) -> int:
    xmin, ymin, xmax, ymax = clip_rect
    code = INSIDE
    if x < xmin:
        code |= LEFT
    elif x > xmax:
        code |= RIGHT
    if y < ymin:
        code |= BOTTOM
    elif y > ymax:
        code |= TOP
    return code


def cohen_sutherland(
    p1: Point2D, p2: Point2D, clip_rect: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect

    code1 = _compute_cohen_sutherland_code(x1, y1, clip_rect)
    code2 = _compute_cohen_sutherland_code(x2, y2, clip_rect)
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
                y = ymax
                if abs(y2 - y1) > 1e-9:
                    x = x1 + (x2 - x1) * (ymax - y1) / (y2 - y1)
                else:
                    x = x1
            elif code_out & BOTTOM:
                y = ymin
                if abs(y2 - y1) > 1e-9:
                    x = x1 + (x2 - x1) * (ymin - y1) / (y2 - y1)
                else:
                    x = x1
            elif code_out & RIGHT:
                x = xmax
                if abs(x2 - x1) > 1e-9:
                    y = y1 + (y2 - y1) * (xmax - x1) / (x2 - x1)
                else:
                    y = y1
            elif code_out & LEFT:
                x = xmin
                if abs(x2 - x1) > 1e-9:
                    y = y1 + (y2 - y1) * (xmin - x1) / (x2 - x1)
                else:
                    y = y1

            if code_out == code1:
                x1, y1 = x, y
                code1 = _compute_cohen_sutherland_code(x1, y1, clip_rect)
            else:
                x2, y2 = x, y
                code2 = _compute_cohen_sutherland_code(x2, y2, clip_rect)

    if accept:
        return ((x1, y1), (x2, y2))
    else:
        return None


# --- Recorte de Linha Liang-Barsky ---


def liang_barsky(
    p1: Point2D, p2: Point2D, clip_rect: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect

    dx = x2 - x1
    dy = y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - xmin, xmax - x1, y1 - ymin, ymax - y1]
    u1, u2 = 0.0, 1.0

    for k in range(4):
        if abs(p[k]) < 1e-9:
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

    clipped_x1 = x1 + u1 * dx
    clipped_y1 = y1 + u1 * dy
    clipped_x2 = x1 + u2 * dx
    clipped_y2 = y1 + u2 * dy

    return ((clipped_x1, clipped_y1), (clipped_x2, clipped_y2))


# --- Recorte de Polígono Sutherland-Hodgman ---


def _intersect_polygon_edge(
    p1: Point2D, p2: Point2D, edge_index: int, clip_rect: ClipRect
) -> Point2D:
    xmin, ymin, xmax, ymax = clip_rect
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    x, y = 0.0, 0.0

    if edge_index == 0:
        x = xmin
        y = y1 + dy * (xmin - x1) / dx if abs(dx) > 1e-9 else y1
    elif edge_index == 1:
        x = xmax
        y = y1 + dy * (xmax - x1) / dx if abs(dx) > 1e-9 else y1
    elif edge_index == 2:
        y = ymin
        x = x1 + dx * (ymin - y1) / dy if abs(dy) > 1e-9 else x1
    elif edge_index == 3:
        y = ymax
        x = x1 + dx * (ymax - y1) / dy if abs(dy) > 1e-9 else x1
    return x, y


def _is_inside_edge(p: Point2D, edge_index: int, clip_rect: ClipRect) -> bool:
    xmin, ymin, xmax, ymax = clip_rect
    x, y = p
    if edge_index == 0:
        return x >= xmin
    if edge_index == 1:
        return x <= xmax
    if edge_index == 2:
        return y >= ymin
    if edge_index == 3:
        return y <= ymax
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

            if e_inside:
                if not s_inside:
                    intersection = _intersect_polygon_edge(s, e, edge_index, clip_rect)
                    output_list.append(intersection)
                output_list.append(e)
            elif s_inside:
                intersection = _intersect_polygon_edge(s, e, edge_index, clip_rect)
                output_list.append(intersection)

            s = e

    return output_list
