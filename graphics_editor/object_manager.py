"""
Módulo que gerencia a conversão entre dados de arquivo e objetos internos.
Este módulo contém a classe ObjectManager que gerencia a conversão entre formatos OBJ/MTL e objetos internos.
"""

# graphics_editor/object_manager.py
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtGui import QColor, QPolygonF
from PyQt5.QtCore import Qt, QPointF, QLineF
import numpy as np
import os
import math

from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon
from .models.bezier_curve import BezierCurve

DataObject = Union[Point, Line, Polygon, BezierCurve]
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve)


class ObjectManager:
    """
    Gerencia a conversão entre dados de arquivo OBJ/MTL e os objetos de dados internos.
    
    Esta classe é responsável por:
    - Converter dados OBJ/MTL em objetos internos (Point, Line, Polygon, BezierCurve)
    - Gerar dados OBJ/MTL a partir de objetos internos
    - Gerenciar a aproximação de curvas de Bézier como polilinhas
    - Tratar erros e gerar avisos durante a conversão
    
    Nota: Curvas de Bézier são aproximadas como polilinhas ao salvar e não são
          reconstruídas ao carregar.
    """

    DEFAULT_BEZIER_SAVE_SAMPLES = 20

    def __init__(self, bezier_samples: Optional[int] = None):
        """
        Inicializa o gerenciador de objetos.
        
        Args:
            bezier_samples: Número de amostras por segmento para aproximação de Bézier ao salvar
        """
        self.bezier_save_samples = (
            bezier_samples
            if bezier_samples is not None
            else self.DEFAULT_BEZIER_SAVE_SAMPLES
        )

    def parse_obj_data(
        self,
        obj_lines: List[str],
        material_colors: Dict[str, QColor],
        default_color: QColor = QColor(Qt.black),
    ) -> Tuple[List[DataObject], List[str]]:
        """
        Analisa linhas de um arquivo OBJ e converte em objetos de dados.
        
        Args:
            obj_lines: Linhas relevantes do OBJ (sem comentários/vazias)
            material_colors: Dicionário {nome_material: QColor} do MTL
            default_color: Cor padrão se material não for encontrado
            
        Returns:
            Tuple[List[DataObject], List[str]]: Tupla contendo:
                - Lista de objetos de dados criados
                - Lista de avisos gerados durante a análise
        """
        parsed_objects: List[DataObject] = []
        warnings: List[str] = []
        obj_vertices: List[Tuple[float, float]] = []
        active_color: QColor = default_color
        # Use a local variable for warnings within this method
        local_warnings: List[str] = []

        for line_num, line in enumerate(obj_lines, 1):
            parts = line.split()
            if not parts:
                continue
            command = parts[0].lower()

            try:
                if command == "v":
                    if len(parts) >= 3:
                        x, y = float(parts[1]), float(parts[2])
                        obj_vertices.append((x, y))
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Vértice 'v' malformado: {line}"
                        )
                elif command == "usemtl":
                    if len(parts) > 1:
                        material_name = " ".join(parts[1:])
                        if material_name in material_colors:
                            active_color = material_colors[material_name]
                        else:
                            local_warnings.append(
                                f"Linha {line_num}: Material '{material_name}' não encontrado. Usando cor padrão."
                            )
                            active_color = default_color
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: 'usemtl' sem nome. Usando cor padrão."
                        )
                        active_color = default_color
                elif command == "p":
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num, local_warnings
                        )
                        for idx in indices:
                            point_data = Point(*obj_vertices[idx], color=active_color)
                            parsed_objects.append(point_data)
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Comando 'p' sem índices."
                        )
                elif command == "l":
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num, local_warnings
                        )
                        if len(indices) >= 2:
                            line_points_data = [
                                Point(*obj_vertices[idx], color=active_color)
                                for idx in indices
                            ]
                            if len(line_points_data) == 2:
                                line_data = Line(
                                    line_points_data[0],
                                    line_points_data[1],
                                    color=active_color,
                                )
                                parsed_objects.append(line_data)
                            else:
                                polyline_data = Polygon(
                                    line_points_data, is_open=True, color=active_color
                                )
                                parsed_objects.append(polyline_data)
                        elif indices:
                            local_warnings.append(
                                f"Linha {line_num}: Linha/Polilinha 'l' requer >= 2 vértices válidos: {line}"
                            )
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Comando 'l' sem índices."
                        )
                elif command == "f":
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num, local_warnings
                        )
                        if len(indices) >= 3:
                            face_points_data = [
                                Point(*obj_vertices[idx], color=active_color)
                                for idx in indices
                            ]
                            polygon_data = Polygon(
                                face_points_data,
                                is_open=False,
                                color=active_color,
                                is_filled=True,
                            )
                            parsed_objects.append(polygon_data)
                        elif indices:
                            local_warnings.append(
                                f"Linha {line_num}: Face 'f' requer >= 3 vértices válidos: {line}"
                            )
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Comando 'f' sem índices."
                        )

            except (ValueError, IndexError) as e:
                local_warnings.append(
                    f"Linha {line_num}: Erro ao processar '{command}': {line} - Detalhe: {e}"
                )
            except Exception as e:
                local_warnings.append(
                    f"Linha {line_num}: Erro inesperado processando '{command}': {line} - Detalhe: {e}"
                )

        warnings.extend(local_warnings)
        return parsed_objects, warnings

    def _parse_vertex_indices(
        self,
        index_parts: List[str],
        num_vertices: int,
        line_num: int,
        warnings_list: List[str],
    ) -> List[int]:
        """
        Analisa índices de vértices de comandos OBJ (p, l, f).
        
        Args:
            index_parts: Lista de strings contendo os índices
            num_vertices: Número total de vértices disponíveis
            line_num: Número da linha sendo processada
            warnings_list: Lista para acumular avisos
            
        Returns:
            List[int]: Lista de índices convertidos para base 0
        """
        indices: List[int] = []
        if num_vertices == 0 and index_parts:
            warnings_list.append(
                f"Linha {line_num}: Referência a vértices antes de 'v' ser definido."
            )
            return []

        for part in index_parts:
            index_str = part.split("/")[0]
            if not index_str:
                warnings_list.append(
                    f"Linha {line_num}: Índice de vértice vazio encontrado ('{part}')."
                )
                continue

            try:
                idx = int(index_str)
            except ValueError:
                warnings_list.append(
                    f"Linha {line_num}: Índice de vértice não numérico '{index_str}' ('{part}')."
                )
                continue

            if idx == 0:
                warnings_list.append(
                    f"Linha {line_num}: Índice de vértice inválido (0). Índices OBJ são base 1."
                )
                continue
            elif idx > 0:
                if idx <= num_vertices:
                    indices.append(idx - 1)
                else:
                    warnings_list.append(
                        f"Linha {line_num}: Índice {idx} fora do intervalo [1..{num_vertices}]."
                    )
            else:
                rel_idx_base0 = num_vertices + idx
                if 0 <= rel_idx_base0 < num_vertices:
                    indices.append(rel_idx_base0)
                else:
                    warnings_list.append(
                        f"Linha {line_num}: Índice negativo {idx} (resolvido para {rel_idx_base0}) fora do intervalo [0..{num_vertices-1}]."
                    )
        return indices

    def generate_obj_data(
        self, data_objects: List[DataObject], mtl_filename: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]], List[str]]:
        """
        Gera conteúdo dos arquivos OBJ e MTL a partir dos objetos internos.
        
        Args:
            data_objects: Lista de objetos da cena (Point, Line, Polygon, BezierCurve)
            mtl_filename: Nome do arquivo MTL a ser referenciado no OBJ
            
        Returns:
            Tuple[Optional[List[str]], Optional[List[str]], List[str]]: Tupla contendo:
                - Linhas do arquivo OBJ (ou None se não houver o que salvar)
                - Linhas do arquivo MTL (ou None se não houver o que salvar)
                - Lista de avisos gerados durante a geração
        """
        warnings: List[str] = []
        savable_objects = [
            obj for obj in data_objects if isinstance(obj, DATA_OBJECT_TYPES)
        ]

        if not savable_objects:
            warnings.append(
                "Nenhum objeto suportado (Ponto, Linha, Polígono, Bézier) na cena para salvar."
            )
            return None, None, warnings

        vertex_map: Dict[Tuple[float, float], int] = {}
        output_vertices: List[Tuple[float, float]] = []
        materials: Dict[str, QColor] = {}
        object_definitions: List[
            Tuple[str, str, List[Tuple[float, float]], DataObject]
        ] = []  # Added original object
        vertex_counter = 1

        for i, data_object in enumerate(savable_objects):
            obj_type_name = type(data_object).__name__

            obj_color = getattr(data_object, "color", QColor(Qt.black))
            if not isinstance(obj_color, QColor) or not obj_color.isValid():
                warnings.append(
                    f"Obj {i+1} ({obj_type_name}) sem cor válida. Usando preto."
                )
                obj_color = QColor(Qt.black)
            color_hex = obj_color.name(QColor.HexRgb).upper()[1:]
            material_name = f"mat_{color_hex}"
            if material_name not in materials:
                materials[material_name] = obj_color

            coords_list: List[Tuple[float, float]] = []
            is_bezier = isinstance(data_object, BezierCurve)

            try:
                if is_bezier:
                    sampled_qpoints = data_object.sample_curve(self.bezier_save_samples)
                    coords_list = [(qp.x(), qp.y()) for qp in sampled_qpoints]
                    if len(coords_list) < 2:
                        warnings.append(
                            f"Bézier Obj {i+1} não pôde ser amostrado em pontos suficientes ({len(coords_list)}). Ignorando."
                        )
                        continue
                    obj_type_name = "BezierApproximation"
                else:
                    raw_coords = data_object.get_coords()
                    if isinstance(data_object, Point):
                        coords_list = [raw_coords]
                    elif isinstance(raw_coords, list):
                        coords_list = raw_coords
                    else:
                        raise TypeError("get_coords() retornou tipo inesperado.")

            except Exception as e:
                warnings.append(
                    f"Erro ao obter/processar coords do Obj {i+1} ({obj_type_name}): {e}. Ignorando."
                )
                continue

            if not coords_list:
                warnings.append(
                    f"Obj {i+1} ({obj_type_name}) sem coordenadas válidas após processamento. Ignorando."
                )
                continue

            current_object_vertex_coords = []
            for coords_tuple in coords_list:
                if not isinstance(coords_tuple, tuple) or len(coords_tuple) != 2:
                    warnings.append(
                        f"Coord inesperada {coords_tuple} para Obj {i+1}. Ignorando vértice."
                    )
                    continue
                key_coords = (round(coords_tuple[0], 6), round(coords_tuple[1], 6))
                if key_coords not in vertex_map:
                    vertex_map[key_coords] = vertex_counter
                    output_vertices.append(key_coords)
                    vertex_counter += 1
                current_object_vertex_coords.append(key_coords)

            object_definitions.append(
                (
                    obj_type_name,
                    material_name,
                    current_object_vertex_coords,
                    data_object,
                )  # Store original object
            )

        if not output_vertices:
            warnings.append("Nenhum vértice válido encontrado nos objetos para salvar.")
            return None, None, warnings

        mtl_lines: Optional[List[str]] = None
        if materials:
            mtl_lines = [
                "# Arquivo de Materiais (Editor Gráfico 2D)",
                f"# Materiais: {len(materials)}",
                "",
            ]
            for name, color in materials.items():
                mtl_lines.extend(
                    [
                        f"newmtl {name}",
                        f"Kd {color.redF():.6f} {color.greenF():.6f} {color.blueF():.6f}",
                        "Ka 0.1 0.1 0.1",
                        "Ks 0.0 0.0 0.0",
                        "Ns 0.0",
                        "d 1.0",
                        "illum 1",
                        "",
                    ]
                )

        obj_lines: List[str] = ["# Arquivo OBJ (Editor Gráfico 2D)"]
        if mtl_lines:
            obj_lines.append(f"mtllib {os.path.basename(mtl_filename)}")
        obj_lines.extend(
            [
                "",
                f"# Vértices: {len(output_vertices)}, Objetos: {len(object_definitions)}",
                "",
            ]
        )
        obj_lines.append("# Vértices Geométricos (z=0)")
        for x, y in output_vertices:
            obj_lines.append(f"v {x:.6f} {y:.6f} 0.0")
        obj_lines.append("")
        obj_lines.append("# Elementos Geométricos")
        last_material_name: Optional[str] = None

        for i, (obj_type, material, vertex_coords, original_obj_ref) in enumerate(
            object_definitions
        ):
            obj_lines.append(f"o {obj_type}_{i+1}")

            if mtl_lines and material != last_material_name:
                if material in materials:
                    obj_lines.append(f"usemtl {material}")
                    last_material_name = material
                else:
                    warnings.append(
                        f"Erro Interno: Material '{material}' para Obj {i+1} não encontrado."
                    )

            indices_str_list: List[str] = []
            lookup_failed = False
            for key_coords in vertex_coords:
                if key_coords in vertex_map:
                    indices_str_list.append(str(vertex_map[key_coords]))
                else:
                    warnings.append(
                        f"ERRO LOOKUP: Vértice {key_coords} (Obj {i+1}) não encontrado. OBJ estará incorreto."
                    )
                    lookup_failed = True
                    break
            if lookup_failed:
                obj_lines.append("# ERRO: Falha ao encontrar índices de vértices.")
                obj_lines.append("")
                continue

            indices_str = " ".join(indices_str_list)
            if not indices_str:
                warnings.append(
                    f"Obj {i+1} ({obj_type}) sem índices válidos. Ignorando."
                )
                continue

            if obj_type == "Point":
                obj_lines.append(f"p {indices_str}")
            elif obj_type == "Line":
                if len(indices_str_list) >= 2:
                    obj_lines.append(f"l {indices_str}")
                else:
                    warnings.append(f"Linha {i+1} < 2 índices. Ignorando 'l'.")
            elif obj_type == "Polygon":
                # original_obj = savable_objects[i] # This was error prone if savable_objects filtered differently. Use original_obj_ref
                if isinstance(original_obj_ref, Polygon):
                    if original_obj_ref.is_open:
                        if len(indices_str_list) >= 2:
                            obj_lines.append(f"l {indices_str}")
                        else:
                            warnings.append(
                                f"Polilinha {i+1} < 2 índices. Ignorando 'l'."
                            )
                    else:
                        if len(indices_str_list) >= 3:
                            obj_lines.append(f"f {indices_str}")
                        else:
                            warnings.append(
                                f"Polígono {i+1} < 3 índices. Ignorando 'f'."
                            )
                else:
                    warnings.append(
                        f"Erro Interno: Esperado Polígono mas encontrado {type(original_obj_ref).__name__}."
                    )
            elif obj_type == "BezierApproximation":
                if len(indices_str_list) >= 2:
                    obj_lines.append(f"l {indices_str}")
                else:
                    warnings.append(
                        f"Aproximação Bézier {i+1} < 2 índices. Ignorando 'l'."
                    )
            obj_lines.append("")

        return obj_lines, mtl_lines, warnings
