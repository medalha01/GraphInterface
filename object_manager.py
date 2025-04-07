# object_manager.py
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

from models.point import Point
from models.line import Line
from models.polygon import Polygon

DataObject = Union[Point, Line, Polygon]


class ObjectManager:
    """Manages parsing of OBJ data and generation of OBJ/MTL strings from scene objects."""

    def parse_obj_data(
        self,
        obj_lines: List[str],
        material_colors: Dict[str, QColor],
        default_color: QColor,
    ) -> Tuple[List[DataObject], List[str]]:
        """
        Parses lines from an OBJ file into application data objects, using provided materials.
        Args:
            obj_lines: A list of relevant lines from an OBJ file.
            material_colors: A dictionary mapping material names found in the MTL to QColors.
            default_color: The QColor to use if no material is active or found.
        Returns:
            A tuple containing:
                - A list of created DataObject instances (Point, Line, Polygon).
                - A list of warning messages generated during parsing.
        """
        parsed_objects: List[DataObject] = []
        warnings: List[str] = []
        obj_vertices: List[Tuple[float, float]] = []
        current_material_name: Optional[str] = None
        active_color = default_color

        for line_num, line in enumerate(obj_lines, 1):
            parts = line.split()
            if not parts:
                continue
            command = parts[0].lower()

            if command == "v":
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    obj_vertices.append((x, y))
                except (IndexError, ValueError):
                    warnings.append(
                        f"Linha {line_num}: Ignorando vértice malformado: {line}"
                    )
                    continue

            elif command == "usemtl":
                if len(parts) > 1:
                    current_material_name = parts[1]
                    active_color = material_colors.get(
                        current_material_name, default_color
                    )
                    if current_material_name not in material_colors:
                        warnings.append(
                            f"Linha {line_num}: Material '{current_material_name}' não encontrado no arquivo MTL, usando cor padrão."
                        )
                else:
                    warnings.append(f"Linha {line_num}: 'usemtl' sem nome de material.")
                    current_material_name = None
                    active_color = default_color

            elif command == "p":
                try:
                    indices = self._parse_face_or_line_indices(
                        parts[1:], len(obj_vertices), line_num
                    )
                    for idx in indices:
                        coords = obj_vertices[idx]
                        point_data = Point(coords[0], coords[1], color=active_color)
                        parsed_objects.append(point_data)
                except (IndexError, ValueError) as e:
                    warnings.append(
                        f"Linha {line_num}: Ignorando ponto 'p' malformado ou com índice inválido: {line} - Erro: {e}"
                    )
                    continue

            elif command == "l":
                try:
                    indices = self._parse_face_or_line_indices(
                        parts[1:], len(obj_vertices), line_num
                    )
                    if len(indices) >= 2:
                        if len(indices) == 2:
                            start_idx, end_idx = indices[0], indices[1]
                            start_coords = obj_vertices[start_idx]
                            end_coords = obj_vertices[end_idx]
                            start_point = Point(
                                start_coords[0], start_coords[1], color=active_color
                            )
                            end_point = Point(
                                end_coords[0], end_coords[1], color=active_color
                            )
                            line_data = Line(start_point, end_point, color=active_color)
                            parsed_objects.append(line_data)
                        else:
                            polygon_points_data = []
                            for idx in indices:
                                coords = obj_vertices[idx]
                                polygon_points_data.append(
                                    Point(coords[0], coords[1], color=active_color)
                                )
                            polygon_data = Polygon(
                                polygon_points_data, is_open=True, color=active_color
                            )
                            parsed_objects.append(polygon_data)

                    elif indices:
                        warnings.append(
                            f"Linha {line_num}: Linha/Polilinha 'l' requer pelo menos 2 vértices válidos: {line}"
                        )

                except (IndexError, ValueError) as e:
                    warnings.append(
                        f"Linha {line_num}: Ignorando linha/polilinha 'l' malformada ou com índice inválido: {line} - Erro: {e}"
                    )
                    continue

            elif command == "f":
                try:
                    indices = self._parse_face_or_line_indices(
                        parts[1:], len(obj_vertices), line_num
                    )
                    if len(indices) >= 3:
                        polygon_points_data = []
                        for idx in indices:
                            coords = obj_vertices[idx]
                            polygon_points_data.append(
                                Point(coords[0], coords[1], color=active_color)
                            )
                        polygon_data = Polygon(
                            polygon_points_data, is_open=False, color=active_color
                        )
                        parsed_objects.append(polygon_data)
                    elif indices:
                        warnings.append(
                            f"Linha {line_num}: Face 'f' requer pelo menos 3 vértices válidos: {line}"
                        )

                except (IndexError, ValueError) as e:
                    warnings.append(
                        f"Linha {line_num}: Ignorando face 'f' malformada ou com índice inválido: {line} - Erro: {e}"
                    )
                    continue

        return parsed_objects, warnings

    def _parse_face_or_line_indices(
        self, parts: List[str], num_vertices: int, line_num: int
    ) -> List[int]:
        """Helper to parse vertex indices from 'f', 'l', or 'p' lines."""
        indices = []
        for part in parts:
            index_str = part.split("/")[0]
            if not index_str:
                raise ValueError("Índice de vértice vazio encontrado.")
            idx = int(index_str)
            if 1 <= idx <= num_vertices:
                indices.append(idx - 1)
            elif idx < 0:
                rel_idx = num_vertices + idx
                if 0 <= rel_idx < num_vertices:
                    indices.append(rel_idx)
                else:
                    raise IndexError(
                        f"Índice relativo {idx} (resolvido para {rel_idx}) fora dos limites [0..{num_vertices-1}]"
                    )
            else:
                raise IndexError(f"Índice {idx} fora dos limites [1..{num_vertices}]")
        return indices

    def generate_obj_data(
        self, data_objects: List[DataObject], mtl_filename: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]], List[str]]:
        """
        Generates OBJ and MTL file content from scene data objects.
        Args:
            data_objects: A list of Point, Line, or Polygon instances to save.
            mtl_filename: The filename to use for the generated MTL file (e.g., "scene.mtl").
        Returns:
            A tuple containing:
                - List of strings for the OBJ file, or None if no savable objects.
                - List of strings for the MTL file, or None if no materials needed.
                - List of warning messages.
        """
        warnings: List[str] = []
        # Now include Points as savable objects
        savable_objects = [
            obj for obj in data_objects if isinstance(obj, (Point, Line, Polygon))
        ]

        if not savable_objects:
            warnings.append(
                "Nenhum objeto (Ponto, Linha, Polígono) encontrado para salvar."
            )
            return None, None, warnings

        vertex_map: Dict[Tuple[float, float], int] = {}
        output_vertices: List[Tuple[float, float]] = []
        vertex_counter = 1
        materials: Dict[str, QColor] = {}
        object_material_map: List[Tuple[DataObject, str]] = []

        for i, data_object in enumerate(savable_objects):
            coords_list: List[Tuple[float, float]] = []
            obj_color: QColor = QColor(Qt.black)

            if hasattr(data_object, "color") and isinstance(data_object.color, QColor):
                obj_color = data_object.color
            else:
                warnings.append(
                    f"Objeto {i+1} ({type(data_object).__name__}) não possui cor válida, usando preto."
                )

            color_hex = obj_color.name(QColor.HexRgb).upper()  # e.g., #RRGGBB
            material_name = f"mat_{color_hex[1:]}"  # e.g., mat_RRGGBB
            if material_name not in materials:
                materials[material_name] = obj_color
            object_material_map.append((data_object, material_name))

            if isinstance(data_object, Point):
                coords_list = [data_object.get_coords()]
            elif isinstance(data_object, Line):
                coords_list = data_object.get_coords()
            elif isinstance(data_object, Polygon):
                coords_list = data_object.get_coords()

            for coords in coords_list:
                coords_rounded = coords
                if coords_rounded not in vertex_map:
                    vertex_map[coords_rounded] = vertex_counter
                    output_vertices.append(coords_rounded)
                    vertex_counter += 1

        if not output_vertices:
            warnings.append("Falha ao extrair vértices dos objetos.")
            return None, None, warnings

        mtl_lines: List[str] = []
        if materials:
            mtl_lines.append(f"# Generated by Graphics Editor")
            mtl_lines.append(f"# Material Count: {len(materials)}")
            mtl_lines.append("")
            for name, color in materials.items():
                mtl_lines.append(f"newmtl {name}")
                r = color.redF()
                g = color.greenF()
                b = color.blueF()
                mtl_lines.append(f"Kd {r:.4f} {g:.4f} {b:.4f}")  # Diffuse color
                mtl_lines.append("Ka 0.0000 0.0000 0.0000")  # Ambient color (optional)
                mtl_lines.append("Ks 0.0000 0.0000 0.0000")  # Specular color (optional)
                mtl_lines.append("Ns 0.0")  # Specular exponent (optional)
                mtl_lines.append("d 1.0")  # Dissolve (alpha) (optional)
                mtl_lines.append("illum 1")  # Illumination model (optional)
                mtl_lines.append("")

        obj_lines: List[str] = []
        obj_lines.append(f"# Generated by Graphics Editor")
        if materials:
            obj_lines.append(f"mtllib {mtl_filename}")  # Reference the MTL file
        obj_lines.append(f"# Vertices: {len(output_vertices)}")
        obj_lines.append(f"# Objects: {len(savable_objects)}")
        obj_lines.append("")

        for x, y in output_vertices:
            obj_lines.append(f"v {x:.6f} {y:.6f} 0.0")
        obj_lines.append("")

        last_material_name = None
        for i, (data_object, material_name) in enumerate(object_material_map):
            obj_type_name = type(data_object).__name__
            obj_lines.append(f"# Object {i+1}")
            obj_lines.append(f"o {obj_type_name}_{i+1}")

            if material_name != last_material_name and material_name in materials:
                obj_lines.append(f"usemtl {material_name}")
                last_material_name = material_name
            elif material_name not in materials:
                warnings.append(
                    f"Material '{material_name}' não gerado para Objeto {i+1}, sem 'usemtl'."
                )
                last_material_name = None

            indices: List[int] = []
            missing_vertices_msg: Optional[str] = None
            try:
                if isinstance(data_object, Point):
                    coords_r = data_object.get_coords()
                    indices.append(vertex_map[coords_r])
                    obj_lines.append(f"p {indices[0]}")

                elif isinstance(data_object, Line):
                    start_coords_r = data_object.start.get_coords()
                    end_coords_r = data_object.end.get_coords()
                    idx1 = vertex_map[start_coords_r]
                    idx2 = vertex_map[end_coords_r]
                    obj_lines.append(f"l {idx1} {idx2}")

                elif isinstance(data_object, Polygon):
                    poly_indices = []
                    missing = []
                    for point in data_object.points:
                        coords_r = point.get_coords()
                        try:
                            poly_indices.append(vertex_map[coords_r])
                        except KeyError:
                            missing.append(coords_r)
                    if missing:
                        missing_vertices_msg = f"Vértices não encontrados no mapa para Polígono {i+1}: {missing}"
                        warnings.append(missing_vertices_msg)
                        obj_lines.append(f"# WARNING: {missing_vertices_msg}")

                    # Save as 'f' if closed and valid, 'l' if open and valid
                    if data_object.is_open:
                        if len(poly_indices) >= 2:
                            obj_lines.append(f"l {' '.join(map(str, poly_indices))}")
                        elif poly_indices:
                            warnings.append(
                                f"Polígono aberto {i+1} com apenas {len(poly_indices)} vértices válidos, ignorando (requer >= 2 para 'l')."
                            )
                    else:  # Closed polygon
                        if len(poly_indices) >= 3:
                            obj_lines.append(f"f {' '.join(map(str, poly_indices))}")
                        elif poly_indices:
                            warnings.append(
                                f"Polígono fechado {i+1} com apenas {len(poly_indices)} vértices válidos, ignorando (requer >= 3 para 'f')."
                            )

            except KeyError as e:
                # Catch cases where vertex lookup fails unexpectedly
                err_msg = f"Vértice {e} não encontrado no mapa para Objeto {i+1} ({obj_type_name})."
                warnings.append(err_msg)
                obj_lines.append(f"# WARNING: {err_msg}")
            except Exception as e:
                err_msg = (
                    f"Erro inesperado ao processar Objeto {i+1} ({obj_type_name}): {e}"
                )
                warnings.append(err_msg)
                obj_lines.append(f"# WARNING: {err_msg}")

            obj_lines.append("")

        final_mtl_lines = mtl_lines if mtl_lines else None
        return obj_lines, final_mtl_lines, warnings
