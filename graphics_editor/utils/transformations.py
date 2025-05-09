"""
Módulo que implementa transformações geométricas 2D usando matrizes homogêneas.

Este módulo fornece funções para:
- Criar matrizes de transformação 3x3 (homogêneas 2D)
- Aplicar transformações a listas de vértices
- Suporta translação, escala e rotação

As transformações são implementadas usando coordenadas homogêneas para permitir
composição de transformações através de multiplicação de matrizes.
"""

# graphics_editor/utils/transformations.py
import numpy as np
import math
from typing import List, Tuple

# Alias para clareza
VertexList = List[Tuple[float, float]]

# Constante pequena para comparações de ponto flutuante
EPSILON = 1e-9

# --- Funções para criar matrizes de transformação 3x3 (homogêneas 2D) ---


def create_translation_matrix(dx: float, dy: float) -> np.ndarray:
    """
    Cria matriz de translação 3x3.
    
    Args:
        dx: Deslocamento no eixo x
        dy: Deslocamento no eixo y
        
    Returns:
        np.ndarray: Matriz de translação 3x3
    """
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]], dtype=float)


def create_scaling_matrix(sx: float, sy: float) -> np.ndarray:
    """
    Cria matriz de escala 3x3 (relativa à origem).
    
    Args:
        sx: Fator de escala no eixo x
        sy: Fator de escala no eixo y
        
    Returns:
        np.ndarray: Matriz de escala 3x3
        Retorna matriz identidade se sx ou sy forem muito próximos de zero
    """
    # Check if scale factors are practically zero
    if abs(sx) < EPSILON or abs(sy) < EPSILON:
        # Return identity matrix to avoid scaling issues
        print(
            f"Aviso: Fator de escala próximo de zero ({sx=}, {sy=}). Usando identidade."
        )
        return np.identity(3, dtype=float)

    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]], dtype=float)


def create_rotation_matrix(angle_degrees: float) -> np.ndarray:
    """
    Cria matriz de rotação 3x3 (anti-horário em torno da origem).
    
    Args:
        angle_degrees: Ângulo de rotação em graus (positivo = anti-horário)
        
    Returns:
        np.ndarray: Matriz de rotação 3x3
    """
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
        vertices: Lista de tuplas (x, y) representando os vértices
        matrix: Matriz NumPy 3x3 de transformação
        
    Returns:
        VertexList: Nova lista de tuplas (x, y) transformadas
        Retorna lista vazia se a entrada for vazia
        
    Note:
        - Usa coordenadas homogêneas para aplicar a transformação
        - Trata pontos no infinito (w ≈ 0) como tendo w = 1
        - Normaliza as coordenadas dividindo por w após a transformação
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
    # Ensure matrix is also float type
    transformed_homogeneous = matrix.astype(float) @ homogeneous_coords.T

    # Transpõe de volta para (N, 3)
    transformed_homogeneous = transformed_homogeneous.T

    # Normaliza dividindo por w (terceira coordenada)
    # Pega a coluna w (índice 2) e evita divisão por zero ou near-zero
    w_coords = transformed_homogeneous[:, 2]
    # Create a mask for near-zero values
    near_zero_mask = np.abs(w_coords) < EPSILON
    # Avoid division by zero: replace near-zero w with 1.0 for division purposes
    # This effectively treats points at infinity as having w=1, preventing NaN/Inf.
    w_divisor = np.where(near_zero_mask, 1.0, w_coords)

    # Divide x e y (colunas 0 e 1) por w_divisor
    # np.newaxis transforma w_divisor (N,) em (N, 1) para broadcasting
    transformed_coords = transformed_homogeneous[:, :2] / w_divisor[:, np.newaxis]

    # Handle original near-zero w values if needed (e.g., for perspective, though not used here)
    # Currently, points that would have w~0 are projected as if w=1.

    # Converte de volta para lista de tuplas
    return [tuple(coord) for coord in transformed_coords]
