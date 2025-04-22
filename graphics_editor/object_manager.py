# graphics_editor/object_manager.py
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtGui import QColor, QPolygonF
from PyQt5.QtCore import Qt, QPointF, QLineF
import numpy as np
import os
import math

# Importações relativas de modelos
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon
from .models.bezier_curve import BezierCurve

# Alias para tipo de objeto de dados
DataObject = Union[Point, Line, Polygon, BezierCurve]
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve)


class ObjectManager:
    """
    Gerencia a conversão entre dados de arquivo OBJ/MTL e os objetos de dados
    internos (Point, Line, Polygon, BezierCurve), seguindo o padrão Wavefront OBJ.
    NOTA: Bézier curves são APROXIMADAS como polilinhas (sequência de 'l') ao salvar,
          e não são reconstruídas ao carregar.
    """

    # Moved sampling constant to editor.py for central configuration
    # BEZIER_SAMPLE_POINTS_PER_SEGMENT = 20 # Now defined in GraphicsEditor

    def __init__(self, bezier_samples: int = 20):
        """
        Initializes the ObjectManager.
        Args:
            bezier_samples: Number of samples per segment for Bezier approximation on save.
        """
        self.bezier_save_samples = bezier_samples

    def parse_obj_data(
        self,
        obj_lines: List[str],
        material_colors: Dict[str, QColor],
        default_color: QColor = QColor(Qt.black),
    ) -> Tuple[List[DataObject], List[str]]:
        """
        Analisa linhas de um arquivo OBJ e converte em objetos de dados.
        Bézier curves are not directly supported in standard OBJ format.
        This parser reads standard 'v', 'p', 'l', 'f' commands.
        Any curve information (e.g., 'curv', 'curv2') is ignored.

        Args:
            obj_lines: Linhas relevantes do OBJ (sem comentários/vazias).
            material_colors: Dicionário {nome_material: QColor} do MTL.
            default_color: Cor padrão se material não for encontrado.

        Returns:
            Tupla: (Lista de DataObject criados, Lista de avisos).
        """
        parsed_objects: List[DataObject] = []
        warnings: List[str] = []
        obj_vertices: List[Tuple[float, float]] = []
        active_color: QColor = default_color

        for line_num, line in enumerate(obj_lines, 1):
            parts = line.split()
            if not parts:
                continue
            command = parts[0].lower()

            try:
                if command == "v":  # Vertex
                    if len(parts) >= 3:
                        x, y = float(parts[1]), float(parts[2])
                        # Ignore Z (parts[3]) if present
                        obj_vertices.append((x, y))
                    else:
                        warnings.append(
                            f"Linha {line_num}: Vértice 'v' malformado: {line}"
                        )
                elif command == "usemtl":  # Use Material
                    if len(parts) > 1:
                        material_name = " ".join(parts[1:])  # Handle names with spaces
                        if material_name in material_colors:
                            active_color = material_colors[material_name]
                        else:
                            warnings.append(
                                f"Linha {line_num}: Material '{material_name}' não encontrado. Usando cor padrão."
                            )
                            active_color = default_color
                    else:
                        warnings.append(
                            f"Linha {line_num}: 'usemtl' sem nome. Usando cor padrão."
                        )
                        active_color = default_color
                elif command == "p":  # Point
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num
                        )
                        for idx in indices:
                            point_data = Point(*obj_vertices[idx], color=active_color)
                            parsed_objects.append(point_data)
                    else:
                        warnings.append(f"Linha {line_num}: Comando 'p' sem índices.")
                elif command == "l":  # Line or Polyline
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num
                        )
                        if len(indices) >= 2:
                            line_points_data = [
                                Point(*obj_vertices[idx], color=active_color)
                                for idx in indices
                            ]
                            # Create individual lines or an open Polygon (polyline)
                            if len(line_points_data) == 2:
                                # Create a Line object
                                line_data = Line(
                                    line_points_data[0],
                                    line_points_data[1],
                                    color=active_color,
                                )
                                parsed_objects.append(line_data)
                            else:
                                # Create an open Polygon object (polyline)
                                polyline_data = Polygon(
                                    line_points_data, is_open=True, color=active_color
                                )
                                parsed_objects.append(polyline_data)
                        elif indices:  # Only 1 valid index?
                            warnings.append(
                                f"Linha {line_num}: Linha/Polilinha 'l' requer >= 2 vértices válidos: {line}"
                            )
                    else:
                        warnings.append(f"Linha {line_num}: Comando 'l' sem índices.")
                elif command == "f":  # Face (Closed Polygon)
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num
                        )
                        if len(indices) >= 3:
                            face_points_data = [
                                Point(*obj_vertices[idx], color=active_color)
                                for idx in indices
                            ]
                            # Assume faces define filled polygons by default
                            polygon_data = Polygon(
                                face_points_data,
                                is_open=False,
                                color=active_color,
                                is_filled=True,
                            )
                            parsed_objects.append(polygon_data)
                        elif indices:  # 1 or 2 valid indices?
                            warnings.append(
                                f"Linha {line_num}: Face 'f' requer >= 3 vértices válidos: {line}"
                            )
                    else:
                        warnings.append(f"Linha {line_num}: Comando 'f' sem índices.")
                # Ignore other commands (vt, vn, g, s, curv, curv2, etc.)

            except (ValueError, IndexError) as e:
                warnings.append(
                    f"Linha {line_num}: Erro ao processar '{command}': {line} - Detalhe: {e}"
                )
            except Exception as e:  # Catch unexpected errors
                warnings.append(
                    f"Linha {line_num}: Erro inesperado processando '{command}': {line} - Detalhe: {e}"
                )

        return parsed_objects, warnings

    def _parse_vertex_indices(
        self, index_parts: List[str], num_vertices: int, line_num: int
    ) -> List[int]:
        """Helper para analisar índices de vértices (p, l, f). Retorna base 0."""
        indices: List[int] = []
        if num_vertices == 0 and index_parts:
            # Allow this case, might have only 'p' commands later? Usually vertices come first.
            warnings.append(
                f"Linha {line_num}: Referência a vértices antes de 'v' ser definido."
            )
            return []  # Return empty list, cannot parse indices

        for part in index_parts:
            # Take only the vertex index part (before the first '/')
            index_str = part.split("/")[0]
            if not index_str:
                warnings.append(
                    f"Linha {line_num}: Índice de vértice vazio encontrado ('{part}')."
                )
                continue  # Skip this part

            try:
                idx = int(index_str)
            except ValueError:
                warnings.append(
                    f"Linha {line_num}: Índice de vértice não numérico '{index_str}' ('{part}')."
                )
                continue  # Skip this part

            if idx == 0:
                warnings.append(
                    f"Linha {line_num}: Índice de vértice inválido (0). Índices OBJ são base 1."
                )
                continue
            elif idx > 0:  # Positive index (1-based)
                if idx <= num_vertices:
                    indices.append(idx - 1)  # Convert to 0-based
                else:
                    warnings.append(
                        f"Linha {line_num}: Índice {idx} fora do intervalo [1..{num_vertices}]."
                    )
                    # Continue parsing other indices if possible
            else:  # Negative index (relative to the end, -1 is last)
                rel_idx_base0 = num_vertices + idx
                if 0 <= rel_idx_base0 < num_vertices:
                    indices.append(rel_idx_base0)
                else:
                    warnings.append(
                        f"Linha {line_num}: Índice negativo {idx} (resolvido para {rel_idx_base0}) fora do intervalo [0..{num_vertices-1}]."
                    )
                    # Continue parsing other indices
        return indices

    def generate_obj_data(
        self, data_objects: List[DataObject], mtl_filename: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]], List[str]]:
        """
        Gera conteúdo dos arquivos OBJ e MTL. Bezier curves são aproximadas como polilinhas ('l').
        Original Bezier control point information is lost in the saved OBJ file.

        Args:
            data_objects: Lista de Point, Line, Polygon, BezierCurve da cena.
            mtl_filename: Nome do arquivo MTL a ser referenciado no OBJ.

        Returns:
            Tupla: (obj_lines, mtl_lines, warnings)
                   Retorna None para obj_lines/mtl_lines se não houver o que salvar.
        """
        warnings: List[str] = []
        # Filter for supported types
        savable_objects = [
            obj for obj in data_objects if isinstance(obj, DATA_OBJECT_TYPES)
        ]

        if not savable_objects:
            warnings.append(
                "Nenhum objeto suportado (Ponto, Linha, Polígono, Bézier) na cena para salvar."
            )
            return None, None, warnings

        # --- Data Collection Phase ---
        vertex_map: Dict[Tuple[float, float], int] = (
            {}
        )  # Maps (x,y) tuple -> 1-based index
        output_vertices: List[Tuple[float, float]] = []  # Unique vertices to be written
        materials: Dict[str, QColor] = {}  # Maps material_name -> QColor
        # Store data needed to write geometry definitions later
        # (original_object_type_name, material_name, list_of_vertex_coords_for_this_object)
        object_definitions: List[Tuple[str, str, List[Tuple[float, float]]]] = []
        vertex_counter = 1  # OBJ indices are 1-based

        for i, data_object in enumerate(savable_objects):
            obj_type_name = type(data_object).__name__

            # --- Get Color and Material ---
            obj_color = getattr(data_object, "color", QColor(Qt.black))
            if not isinstance(obj_color, QColor) or not obj_color.isValid():
                warnings.append(
                    f"Obj {i+1} ({obj_type_name}) sem cor válida. Usando preto."
                )
                obj_color = QColor(Qt.black)
            # Create material name from HEX color (e.g., mat_FF0000)
            color_hex = obj_color.name(QColor.HexRgb).upper()[1:]
            material_name = f"mat_{color_hex}"
            if material_name not in materials:
                materials[material_name] = obj_color

            # --- Get Coordinates (Vertices or Sampled Points) ---
            coords_list: List[Tuple[float, float]] = []
            is_bezier = isinstance(data_object, BezierCurve)

            try:
                if is_bezier:
                    # Sample Bezier into line segments for OBJ output
                    sampled_qpoints = data_object.sample_curve(self.bezier_save_samples)
                    coords_list = [(qp.x(), qp.y()) for qp in sampled_qpoints]
                    if len(coords_list) < 2:
                        warnings.append(
                            f"Bézier Obj {i+1} não pôde ser amostrado em pontos suficientes ({len(coords_list)}). Ignorando."
                        )
                        continue
                    # Mark this object to be saved as a line sequence ('l')
                    obj_type_name = (
                        "BezierApproximation"  # Internal marker for saving logic
                    )
                else:
                    # Get vertices for Point, Line, Polygon
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

            # --- Add Unique Vertices to Map and Collect Object Data ---
            current_object_vertex_coords = []
            for coords_tuple in coords_list:
                if not isinstance(coords_tuple, tuple) or len(coords_tuple) != 2:
                    warnings.append(
                        f"Coord inesperada {coords_tuple} para Obj {i+1}. Ignorando vértice."
                    )
                    continue
                # Round coordinates to handle potential floating point inaccuracies in mapping
                key_coords = (round(coords_tuple[0], 6), round(coords_tuple[1], 6))
                # Add to vertex map if new
                if key_coords not in vertex_map:
                    vertex_map[key_coords] = vertex_counter
                    output_vertices.append(key_coords)  # Add the rounded vertex
                    vertex_counter += 1
                # Store the rounded coordinate for lookup later when writing object definitions
                current_object_vertex_coords.append(key_coords)

            # Store definition data
            object_definitions.append(
                (obj_type_name, material_name, current_object_vertex_coords)
            )

        if not output_vertices:
            warnings.append("Nenhum vértice válido encontrado nos objetos para salvar.")
            return None, None, warnings

        # --- Generate MTL Content ---
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
                        f"Kd {color.redF():.6f} {color.greenF():.6f} {color.blueF():.6f}",  # Diffuse color
                        "Ka 0.1 0.1 0.1",  # Ambient color (low gray)
                        "Ks 0.0 0.0 0.0",  # Specular color (none)
                        "Ns 0.0",  # Specular exponent
                        "d 1.0",  # Dissolve (opacity, 1.0 = fully opaque)
                        "illum 1",  # Illumination model (1 = flat, Kd only)
                        "",  # Blank line between materials
                    ]
                )

        # --- Generate OBJ Content ---
        obj_lines: List[str] = ["# Arquivo OBJ (Editor Gráfico 2D)"]
        # Reference MTL file if it was generated
        if mtl_lines:
            obj_lines.append(f"mtllib {os.path.basename(mtl_filename)}")
        obj_lines.extend(
            [
                "",
                f"# Vértices: {len(output_vertices)}, Objetos: {len(object_definitions)}",
                "",
            ]
        )

        # Vertex definitions (v x y z) - Z is always 0.0
        obj_lines.append("# Vértices Geométricos (z=0)")
        for x, y in output_vertices:
            obj_lines.append(
                f"v {x:.6f} {y:.6f} 0.0"
            )  # Use 6 decimal places for precision
        obj_lines.append("")

        # Geometric Elements (p, l, f)
        obj_lines.append("# Elementos Geométricos")
        last_material_name: Optional[str] = None
        for i, (obj_type, material, vertex_coords) in enumerate(object_definitions):
            # Object Name (optional but good practice)
            obj_lines.append(f"o {obj_type}_{i+1}")  # e.g., o Point_1, o Polygon_2

            # Material ('usemtl')
            if mtl_lines and material != last_material_name:
                if material in materials:
                    obj_lines.append(f"usemtl {material}")
                    last_material_name = material
                else:  # Should not happen if logic is correct
                    warnings.append(
                        f"Erro Interno: Material '{material}' para Obj {i+1} não encontrado na lista de materiais."
                    )

            # --- Vertex Indices ---
            indices_str_list: List[str] = []
            lookup_failed = False
            for (
                key_coords
            ) in vertex_coords:  # Use the rounded coords that were used as keys
                if key_coords in vertex_map:
                    indices_str_list.append(
                        str(vertex_map[key_coords])
                    )  # Get 1-based index
                else:
                    # This indicates an internal error if coords were added correctly before
                    warnings.append(
                        f"ERRO LOOKUP: Vértice {key_coords} (Obj {i+1}) não encontrado no mapa de vértices! OBJ estará incorreto."
                    )
                    lookup_failed = True
                    break  # Stop processing indices for this object
            if lookup_failed:
                obj_lines.append(
                    "# ERRO: Falha ao encontrar índices de vértices para este objeto."
                )
                obj_lines.append("")
                continue  # Skip writing p/l/f for this broken object

            # --- Write Geometric Definition (p, l, f) ---
            indices_str = " ".join(indices_str_list)
            if not indices_str:  # Skip if no valid indices were found
                warnings.append(
                    f"Obj {i+1} ({obj_type}) não possui índices válidos. Ignorando linha p/l/f."
                )
                continue

            if obj_type == "Point":
                obj_lines.append(f"p {indices_str}")
            elif obj_type == "Line":
                if len(indices_str_list) >= 2:
                    obj_lines.append(f"l {indices_str}")
                else:
                    warnings.append(
                        f"Linha {i+1} tem < 2 índices. Ignorando linha 'l'."
                    )
            elif obj_type == "Polygon":
                # Need to access the original object to check is_open property
                # This assumes object_definitions maintains order relative to savable_objects
                original_obj = savable_objects[i]
                if isinstance(original_obj, Polygon):
                    if original_obj.is_open:  # Polyline -> 'l' command
                        if len(indices_str_list) >= 2:
                            obj_lines.append(f"l {indices_str}")
                        else:
                            warnings.append(
                                f"Polilinha {i+1} tem < 2 índices. Ignorando linha 'l'."
                            )
                    else:  # Closed Polygon -> 'f' command
                        if len(indices_str_list) >= 3:
                            obj_lines.append(f"f {indices_str}")
                        else:
                            warnings.append(
                                f"Polígono {i+1} tem < 3 índices. Ignorando linha 'f'."
                            )
                else:
                    warnings.append(
                        f"Erro Interno: Esperado Polígono mas encontrado {type(original_obj).__name__} em índice {i}."
                    )
            elif (
                obj_type == "BezierApproximation"
            ):  # Save sampled Bezier as lines ('l')
                if len(indices_str_list) >= 2:
                    obj_lines.append(f"l {indices_str}")
                else:
                    warnings.append(
                        f"Aproximação Bézier {i+1} tem < 2 índices. Ignorando linha 'l'."
                    )

            obj_lines.append("")  # Blank line between object definitions

        return obj_lines, mtl_lines, warnings
