# graphics_editor/utils/transformations.py
import numpy as np
import math
from typing import List, Tuple

# Alias para clareza
VertexList2D = List[Tuple[float, float]]

# Constante pequena para comparações de ponto flutuante
EPSILON = 1e-9

# --- Funções para criar matrizes de transformação 2D 3x3 (homogêneas) ---


def create_translation_matrix(dx: float, dy: float) -> np.ndarray:
    """
    Cria matriz de translação 2D (homogênea 3x3).

    Args:
        dx: Deslocamento no eixo x.
        dy: Deslocamento no eixo y.

    Returns:
        np.ndarray: Matriz de translação 3x3.
    """
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]], dtype=float)


def create_scaling_matrix(sx: float, sy: float) -> np.ndarray:
    """
    Cria matriz de escala 2D (homogênea 3x3) relativa à origem.

    Args:
        sx: Fator de escala no eixo x.
        sy: Fator de escala no eixo y.

    Returns:
        np.ndarray: Matriz de escala 3x3.
        Retorna matriz identidade se sx ou sy forem muito próximos de zero.
    """
    if abs(sx) < EPSILON or abs(sy) < EPSILON:
        # print(f"Aviso: Fator de escala 2D próximo de zero ({sx=}, {sy=}). Usando identidade.")
        return np.identity(3, dtype=float)

    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=float)


def create_rotation_matrix(angle_degrees: float) -> np.ndarray:
    """
    Cria matriz de rotação 2D (homogênea 3x3) anti-horária em torno da origem.

    Args:
        angle_degrees: Ângulo de rotação em graus (positivo = anti-horário).

    Returns:
        np.ndarray: Matriz de rotação 3x3.
    """
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return np.array(
        [[cos_a, -sin_a, 0.0], [sin_a, cos_a, 0.0], [0.0, 0.0, 1.0]], dtype=float
    )


# --- Função para aplicar a transformação 2D ---


def apply_transformation(vertices: VertexList2D, matrix: np.ndarray) -> VertexList2D:
    """
    Aplica uma matriz de transformação 2D 3x3 a uma lista de vértices 2D.

    Args:
        vertices: Lista de tuplas (x, y) representando os vértices.
        matrix: Matriz NumPy 3x3 de transformação.

    Returns:
        VertexList2D: Nova lista de tuplas (x, y) transformadas.
        Retorna lista vazia se a entrada for vazia.
    """
    if not vertices:
        return []

    vertex_array = np.array(vertices, dtype=float)  # Formato (N, 2)
    # Adiciona coordenada homogênea w=1 para cada vértice -> (N, 3)
    homogeneous_coords = np.hstack(
        [vertex_array, np.ones((vertex_array.shape[0], 1), dtype=float)]
    )

    # Aplica a transformação: matrix (3x3) @ coords.T (3xN) -> resultado (3xN)
    # Garante que a matriz de transformação também seja float
    transformed_homogeneous = matrix.astype(float) @ homogeneous_coords.T

    # Transpõe de volta para (N, 3)
    transformed_homogeneous = transformed_homogeneous.T

    # Normaliza dividindo por w (terceira coordenada)
    # Pega a coluna w (índice 2)
    w_coords = transformed_homogeneous[:, 2]
    # Cria uma máscara para valores de w próximos de zero
    near_zero_mask = np.abs(w_coords) < EPSILON
    # Evita divisão por zero: substitui w próximo de zero por 1.0 para fins de divisão
    # Isso trata pontos no infinito como tendo w=1, prevenindo NaN/Inf.
    w_divisor = np.where(near_zero_mask, 1.0, w_coords)

    # Divide x e y (colunas 0 e 1) por w_divisor
    # np.newaxis transforma w_divisor (N,) em (N, 1) para broadcasting
    transformed_coords = transformed_homogeneous[:, :2] / w_divisor[:, np.newaxis]

    return [tuple(coord) for coord in transformed_coords]
