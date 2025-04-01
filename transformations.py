# transformations.py
import numpy as np
import math
from typing import List, Tuple

VertexList = List[Tuple[float, float]]

def create_translation_matrix(dx: float, dy: float) -> np.ndarray:
    """Cria uma matriz de translação 3x3."""
    return np.array([
        [1.0, 0.0, dx],
        [0.0, 1.0, dy],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def create_scaling_matrix(sx: float, sy: float) -> np.ndarray:
    """Cria uma matriz de escala 3x3 (escala relativa à origem)."""
    if abs(sx) < 1e-9 or abs(sy) < 1e-9:
        print("Aviso: Fator de escala é zero ou próximo de zero. Usando matriz identidade.")
        return np.identity(3, dtype=float)
    return np.array([
        [sx,  0.0, 0.0],
        [0.0, sy,  0.0],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def create_rotation_matrix(angle_degrees: float) -> np.ndarray:
    """
    Cria uma matriz de rotação 3x3 (rotaciona no sentido anti-horário em torno da origem).
    Ângulo é especificado em graus.
    """
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return np.array([
        [cos_a, -sin_a, 0.0],
        [sin_a,  cos_a, 0.0],
        [0.0,    0.0,   1.0]
    ], dtype=float)

def apply_transformation(vertices: VertexList, matrix: np.ndarray) -> VertexList:
    """
    Aplica uma matriz de transformação 3x3 a uma lista de vértices 2D.
    Vértices devem ser uma lista de tuplas (x, y).
    Retorna uma nova lista de tuplas (x, y) transformadas.
    """
    if not vertices:
        return []

    vertex_array = np.array(vertices, dtype=float)
    homogeneous_coords = np.hstack([vertex_array, np.ones((vertex_array.shape[0], 1))])
    transformed_homogeneous = matrix @ homogeneous_coords.T
    transformed_homogeneous = transformed_homogeneous.T
    w_coords = transformed_homogeneous[:, 2]
    w_coords[np.abs(w_coords) < 1e-9] = 1.0
    transformed_coords = transformed_homogeneous[:, :2] / w_coords[:, np.newaxis]

    return [tuple(coord) for coord in transformed_coords]