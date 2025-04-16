# graphics_editor/transformations.py
import numpy as np
import math
from typing import List, Tuple

# Alias para clareza
VertexList = List[Tuple[float, float]]

# Constante pequena para comparações de ponto flutuante
EPSILON = 1e-9

# --- Funções para criar matrizes de transformação 3x3 (homogêneas 2D) ---


def create_translation_matrix(dx: float, dy: float) -> np.ndarray:
    """Cria matriz de translação 3x3."""
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]], dtype=float)


def create_scaling_matrix(sx: float, sy: float) -> np.ndarray:
    """
    Cria matriz de escala 3x3 (relativa à origem).
    Retorna identidade se sx ou sy forem muito próximos de zero para evitar colapso.
    """
    # Valores pequenos (incluindo negativos para espelhamento) são permitidos
    if abs(sx) < EPSILON or abs(sy) < EPSILON:
        print(
            f"Aviso: Fator de escala próximo de zero ({sx=}, {sy=}). Usando identidade."
        )
        return np.identity(3, dtype=float)

    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=float)


def create_rotation_matrix(angle_degrees: float) -> np.ndarray:
    """Cria matriz de rotação 3x3 (anti-horário em torno da origem)."""
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return np.array(
        [[cos_a, -sin_a, 0.0], [sin_a, cos_a, 0.0], [0.0, 0.0, 1.0]], dtype=float
    )


# --- Função para aplicar a transformação ---


def apply_transformation(vertices: VertexList, matrix: np.ndarray) -> VertexList:
    """
    Aplica uma matriz de transformação 3x3 a uma lista de vértices 2D.

    Args:
        vertices: Lista de tuplas (x, y).
        matrix: Matriz NumPy 3x3 de transformação.

    Returns:
        Nova lista de tuplas (x, y) transformadas.
        Retorna lista vazia se a entrada for vazia.
    """
    if not vertices:
        return []

    # Converte para array NumPy (N, 2)
    vertex_array = np.array(vertices, dtype=float)

    # Adiciona coordenada homogênea 'w=1' (N, 3)
    homogeneous_coords = np.hstack(
        [vertex_array, np.ones((vertex_array.shape[0], 1), dtype=float)]
    )

    # Aplica a transformação: matrix (3x3) @ coords.T (3xN) -> resultado (3xN)
    # Garante que a matriz também seja float
    transformed_homogeneous = matrix.astype(float) @ homogeneous_coords.T

    # Transpõe de volta para (N, 3)
    transformed_homogeneous = transformed_homogeneous.T

    # Normaliza dividindo por w (terceira coordenada)
    # Pega a coluna w (índice 2) e evita divisão por zero
    w_coords = transformed_homogeneous[:, 2]
    w_coords[np.abs(w_coords) < EPSILON] = (
        1.0  # Se w for ~0, trata como 1 (evita NaN/Inf)
    )

    # Divide x e y (colunas 0 e 1) por w
    # np.newaxis transforma w_coords (N,) em (N, 1) para broadcasting
    transformed_coords = transformed_homogeneous[:, :2] / w_coords[:, np.newaxis]

    # Converte de volta para lista de tuplas
    return [tuple(coord) for coord in transformed_coords]
