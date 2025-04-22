# graphics_editor/utils/clipping.py
import math
from typing import List, Tuple, Optional, Union

from PyQt5.QtCore import QRectF

Point2D = Tuple[float, float]
# Define ClipRect relative to this module for clarity
ClipRect = Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)

# Epsilon for floating point comparisons
EPSILON = 1e-9


def clip_point(point: Point2D, clip_rect: ClipRect) -> Optional[Point2D]:
    """Clips a single point against the clipping rectangle."""
    x, y = point
    xmin, ymin, xmax, ymax = clip_rect
    # Ensure correct comparison order if rect dimensions are negative
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    if actual_xmin <= x <= actual_xmax and actual_ymin <= y <= actual_ymax:
        return point
    return None


# --- Cohen-Sutherland Line Clipping ---

INSIDE = 0b0000
LEFT = 0b0001
RIGHT = 0b0010
BOTTOM = 0b0100
TOP = 0b1000


def _compute_cohen_sutherland_code(x: float, y: float, clip_rect: ClipRect) -> int:
    """Computes the Cohen-Sutherland outcode for a point."""
    xmin, ymin, xmax, ymax = clip_rect
    # Ensure correct comparison order
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
    """Clips a line segment using the Cohen-Sutherland algorithm."""
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect
    # Ensure correct boundary order
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)
    ordered_clip_rect = (actual_xmin, actual_ymin, actual_xmax, actual_ymax)

    code1 = _compute_cohen_sutherland_code(x1, y1, ordered_clip_rect)
    code2 = _compute_cohen_sutherland_code(x2, y2, ordered_clip_rect)
    accept = False

    while True:
        # Case 1: Both points inside
        if code1 == INSIDE and code2 == INSIDE:
            accept = True
            break
        # Case 2: Both points share an outside region (trivial rejection)
        elif (code1 & code2) != 0:
            break
        # Case 3: Need to clip
        else:
            x, y = 0.0, 0.0
            # Choose the point that is outside
            code_out = code1 if code1 != INSIDE else code2

            # Calculate intersection point using parametric form
            # Avoid division by zero for horizontal/vertical lines
            if code_out & TOP:
                y = actual_ymax
                if abs(y2 - y1) > EPSILON:
                    x = x1 + (x2 - x1) * (actual_ymax - y1) / (y2 - y1)
                else:
                    x = x1  # Should not happen if code_out has TOP but line is horizontal unless point is exactly on edge
            elif code_out & BOTTOM:
                y = actual_ymin
                if abs(y2 - y1) > EPSILON:
                    x = x1 + (x2 - x1) * (actual_ymin - y1) / (y2 - y1)
                else:
                    x = x1
            elif code_out & RIGHT:
                x = actual_xmax
                if abs(x2 - x1) > EPSILON:
                    y = y1 + (y2 - y1) * (actual_xmax - x1) / (x2 - x1)
                else:
                    y = y1
            elif code_out & LEFT:
                x = actual_xmin
                if abs(x2 - x1) > EPSILON:
                    y = y1 + (y2 - y1) * (actual_xmin - x1) / (x2 - x1)
                else:
                    y = y1

            # Update the outside point to the intersection point
            if code_out == code1:
                x1, y1 = x, y
                code1 = _compute_cohen_sutherland_code(x1, y1, ordered_clip_rect)
            else:
                x2, y2 = x, y
                code2 = _compute_cohen_sutherland_code(x2, y2, ordered_clip_rect)

    if accept:
        return ((x1, y1), (x2, y2))
    else:
        return None


# --- Liang-Barsky Line Clipping ---


def liang_barsky(
    p1: Point2D, p2: Point2D, clip_rect: ClipRect
) -> Optional[Tuple[Point2D, Point2D]]:
    """Clips a line segment using the Liang-Barsky algorithm."""
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = clip_rect
    # Ensure correct boundary order
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    dx = x2 - x1
    dy = y2 - y1
    # p = parameters corresponding to left, right, bottom, top boundaries
    # q = parameters corresponding to the point distances from boundaries
    p = [-dx, dx, -dy, dy]
    q = [x1 - actual_xmin, actual_xmax - x1, y1 - actual_ymin, actual_ymax - y1]
    u1, u2 = 0.0, 1.0  # Parameter range for the visible segment

    for k in range(4):
        # Parallel case
        if abs(p[k]) < EPSILON:
            # If parallel and outside, reject
            if q[k] < 0:
                return None
        # Non-parallel case
        else:
            r = q[k] / p[k]
            # Line enters the clip region
            if p[k] < 0:
                u1 = max(u1, r)
            # Line exits the clip region
            else:  # p[k] > 0
                u2 = min(u2, r)

        # Check if line is entirely outside or parameter order is wrong
        if u1 > u2:
            return None

    # Calculate clipped endpoints using the parameters u1 and u2
    clipped_x1 = x1 + u1 * dx
    clipped_y1 = y1 + u1 * dy
    clipped_x2 = x1 + u2 * dx
    clipped_y2 = y1 + u2 * dy

    return ((clipped_x1, clipped_y1), (clipped_x2, clipped_y2))


# --- Sutherland-Hodgman Polygon Clipping ---


def _intersect_polygon_edge(
    p1: Point2D, p2: Point2D, edge_index: int, clip_rect: ClipRect
) -> Point2D:
    """Calculates intersection of polygon edge (p1,p2) with a clip boundary edge."""
    xmin, ymin, xmax, ymax = clip_rect
    # Ensure correct boundary order (although SH usually assumes ordered vertices)
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    x, y = 0.0, 0.0

    # Calculate intersection based on which edge we are clipping against
    try:
        if edge_index == 0:  # Left edge (x = xmin)
            x = actual_xmin
            y = y1 + dy * (actual_xmin - x1) / dx if abs(dx) > EPSILON else y1
        elif edge_index == 1:  # Right edge (x = xmax)
            x = actual_xmax
            y = y1 + dy * (actual_xmax - x1) / dx if abs(dx) > EPSILON else y1
        elif edge_index == 2:  # Bottom edge (y = ymin)
            y = actual_ymin
            x = x1 + dx * (actual_ymin - y1) / dy if abs(dy) > EPSILON else x1
        elif edge_index == 3:  # Top edge (y = ymax)
            y = actual_ymax
            x = x1 + dx * (actual_ymax - y1) / dy if abs(dy) > EPSILON else x1
    except ZeroDivisionError:
        # This case should ideally be handled by the abs(dx/dy) > EPSILON checks
        # If it still occurs, return one of the original points as a fallback
        # print(f"Warning: ZeroDivisionError in _intersect_polygon_edge for edge {edge_index}")
        return p1  # Or p2, debatable which is better

    return x, y


def _is_inside_edge(p: Point2D, edge_index: int, clip_rect: ClipRect) -> bool:
    """Checks if point p is inside the half-plane defined by the clip edge."""
    xmin, ymin, xmax, ymax = clip_rect
    # Ensure correct boundary order
    actual_xmin, actual_xmax = min(xmin, xmax), max(xmin, xmax)
    actual_ymin, actual_ymax = min(ymin, ymax), max(ymin, ymax)

    x, y = p
    if edge_index == 0:
        return x >= actual_xmin  # Inside is to the right of left edge
    if edge_index == 1:
        return x <= actual_xmax  # Inside is to the left of right edge
    if edge_index == 2:
        return y >= actual_ymin  # Inside is above the bottom edge
    if edge_index == 3:
        return y <= actual_ymax  # Inside is below the top edge
    return False  # Should not happen


def sutherland_hodgman(
    polygon_vertices: List[Point2D], clip_rect: ClipRect
) -> List[Point2D]:
    """
    Clips a polygon using the Sutherland-Hodgman algorithm against a rectangle.
    Assumes polygon_vertices are ordered (clockwise or counter-clockwise).
    """
    if not polygon_vertices:
        return []

    output_list = list(polygon_vertices)
    # Clip edges: 0=Left, 1=Right, 2=Bottom, 3=Top
    for edge_index in range(4):
        input_list = list(
            output_list
        )  # Start with the result of the previous clip edge
        output_list.clear()
        if not input_list:
            break  # Polygon was completely clipped out

        # 's' is the start vertex of the current edge, 'e' is the end vertex
        s = input_list[-1]  # Start with the edge from the last to the first vertex
        for e in input_list:
            s_inside = _is_inside_edge(s, edge_index, clip_rect)
            e_inside = _is_inside_edge(e, edge_index, clip_rect)

            # Case 1: Both inside -> Output E
            if e_inside and s_inside:
                output_list.append(e)
            # Case 2: S outside, E inside -> Output Intersection, E
            elif e_inside and not s_inside:
                intersection = _intersect_polygon_edge(s, e, edge_index, clip_rect)
                output_list.append(intersection)
                output_list.append(e)
            # Case 3: S inside, E outside -> Output Intersection
            elif s_inside and not e_inside:
                intersection = _intersect_polygon_edge(s, e, edge_index, clip_rect)
                output_list.append(intersection)
            # Case 4: Both outside -> Output nothing

            s = e  # Move to the next edge

    return output_list
