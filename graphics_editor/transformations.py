# graphics_editor/transformations.py
import numpy as np
import math
from typing import List, Tuple

# Define um alias para clareza
VertexList = List[Tuple[float, float]]

# --- Funções para criar matrizes de transformação 3x3 (homogêneas 2D) ---

def create_translation_matrix(dx: float, dy: float) -> np.ndarray:
    """
    Cria uma matriz de translação 3x3 para coordenadas homogêneas 2D.

    Args:
        dx: Deslocamento no eixo X.
        dy: Deslocamento no eixo Y.

    Returns:
        Matriz de translação NumPy 3x3.
    """
    return np.array([
        [1.0, 0.0, dx ],
        [0.0, 1.0, dy ],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def create_scaling_matrix(sx: float, sy: float) -> np.ndarray:
    """
    Cria uma matriz de escala 3x3 (relativa à origem) para coordenadas homogêneas 2D.

    Args:
        sx: Fator de escala no eixo X.
        sy: Fator de escala no eixo Y.

    Returns:
        Matriz de escala NumPy 3x3. Retorna identidade se sx ou sy forem próximos de zero.
    """
    # Evita divisão por zero ou escala zero que colapsaria o objeto
    if abs(sx) < 1e-9 or abs(sy) < 1e-9:
        print("Aviso: Fator de escala próximo de zero detectado. Usando matriz identidade para evitar colapso.")
        return np.identity(3, dtype=float)

    return np.array([
        [sx,  0.0, 0.0],
        [0.0, sy,  0.0],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def create_rotation_matrix(angle_degrees: float) -> np.ndarray:
    """
    Cria uma matriz de rotação 3x3 (sentido anti-horário em torno da origem)
    para coordenadas homogêneas 2D.

    Args:
        angle_degrees: Ângulo de rotação em graus.

    Returns:
        Matriz de rotação NumPy 3x3.
    """
    angle_rad = math.radians(angle_degrees) # Converte graus para radianos
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return np.array([
        [cos_a, -sin_a, 0.0],
        [sin_a,  cos_a, 0.0],
        [0.0,    0.0,   1.0]
    ], dtype=float)

# --- Função para aplicar a transformação ---

def apply_transformation(vertices: VertexList, matrix: np.ndarray) -> VertexList:
    """
    Aplica uma matriz de transformação 3x3 a uma lista de vértices 2D.

    Args:
        vertices: Uma lista de tuplas, onde cada tupla é (x, y).
        matrix: A matriz de transformação NumPy 3x3.

    Returns:
        Uma nova lista de tuplas (x, y) com os vértices transformados.
        Retorna lista vazia se a entrada for vazia.
    """
    if not vertices:
        return [] # Retorna lista vazia se não houver vértices

    # Converte a lista de tuplas para um array NumPy (N, 2)
    vertex_array = np.array(vertices, dtype=float)

    # Converte para coordenadas homogêneas adicionando uma coluna de 1s (N, 3)
    # np.ones precisa de uma tupla para a forma (shape)
    homogeneous_coords = np.hstack([vertex_array, np.ones((vertex_array.shape[0], 1))])

    # Aplica a transformação: matrix (3x3) @ coords.T (3xN) -> resultado (3xN)
    transformed_homogeneous = matrix @ homogeneous_coords.T

    # Transpõe o resultado de volta para (N, 3)
    transformed_homogeneous = transformed_homogeneous.T

    # Normaliza dividindo por w (a terceira coordenada) para obter coords cartesianas
    # Pega a coluna w (índice 2)
    w_coords = transformed_homogeneous[:, 2]

    # Evita divisão por zero se w for muito pequeno (pode acontecer em transformações de perspectiva, embora não usadas aqui)
    # Se w for próximo de zero, trata como 1 (não normaliza)
    w_coords[np.abs(w_coords) < 1e-9] = 1.0

    # Divide as coordenadas x e y (colunas 0 e 1) por w
    # Usa np.newaxis para tornar w_coords (N,) em (N, 1) para broadcasting
    transformed_coords = transformed_homogeneous[:, :2] / w_coords[:, np.newaxis]

    # Converte o array NumPy de volta para uma lista de tuplas
    return [tuple(coord) for coord in transformed_coords]

