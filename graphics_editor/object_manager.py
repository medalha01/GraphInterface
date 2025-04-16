# graphics_editor/object_manager.py
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
import numpy as np  # Mantido para uso potencial futuro
import os

# Importações relativas de modelos
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon

# Alias para tipo de objeto de dados
DataObject = Union[Point, Line, Polygon]


class ObjectManager:
    """
    Gerencia a conversão entre dados de arquivo OBJ/MTL e os objetos de dados
    internos (Point, Line, Polygon), seguindo o padrão Wavefront OBJ.
    """

    def parse_obj_data(
        self,
        obj_lines: List[str],
        material_colors: Dict[str, QColor],
        default_color: QColor = QColor(Qt.black),
    ) -> Tuple[List[DataObject], List[str]]:
        """
        Analisa linhas de um arquivo OBJ e converte em objetos de dados.

        Args:
            obj_lines: Linhas relevantes do OBJ (sem comentários/vazias).
            material_colors: Dicionário {nome_material: QColor} do MTL.
            default_color: Cor padrão se material não for encontrado.

        Returns:
            Tupla: (Lista de DataObject criados, Lista de avisos).
        """
        parsed_objects: List[DataObject] = []
        warnings: List[str] = []
        obj_vertices: List[Tuple[float, float]] = (
            []
        )  # Vértices 'v' (base 1 para índices OBJ)
        active_color: QColor = default_color  # Cor ativa pelo último 'usemtl'

        for line_num, line in enumerate(obj_lines, 1):
            parts = line.split()
            if not parts:
                continue
            command = parts[0].lower()

            try:
                if command == "v":  # Vértice
                    if len(parts) >= 3:
                        x, y = float(parts[1]), float(parts[2])
                        # Ignora Z (parts[3]) se existir
                        obj_vertices.append((x, y))
                    else:
                        warnings.append(
                            f"Linha {line_num}: Vértice 'v' malformado: {line}"
                        )

                elif command == "usemtl":  # Usar material
                    if len(parts) > 1:
                        material_name = " ".join(parts[1:])
                        if material_name in material_colors:
                            active_color = material_colors[material_name]
                        else:
                            warnings.append(
                                f"Linha {line_num}: Material '{material_name}' não encontrado no MTL. Usando cor padrão."
                            )
                            active_color = default_color
                    else:
                        warnings.append(
                            f"Linha {line_num}: 'usemtl' sem nome de material. Usando cor padrão."
                        )
                        active_color = default_color

                elif command == "p":  # Pontos
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num
                        )
                        for idx in indices:
                            point_data = Point(*obj_vertices[idx], color=active_color)
                            parsed_objects.append(point_data)
                    else:
                        warnings.append(f"Linha {line_num}: Comando 'p' sem índices.")

                elif command == "l":  # Linha ou Polilinha
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num
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
                            else:  # Mais de 2 pontos -> Polilinha aberta
                                polyline_data = Polygon(
                                    line_points_data, is_open=True, color=active_color
                                )
                                parsed_objects.append(polyline_data)
                        elif indices:  # Apenas 1 índice válido?
                            warnings.append(
                                f"Linha {line_num}: Linha/Polilinha 'l' requer >= 2 vértices válidos: {line}"
                            )
                    else:
                        warnings.append(f"Linha {line_num}: Comando 'l' sem índices.")

                elif command == "f":  # Face (Polígono fechado)
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num
                        )
                        if len(indices) >= 3:
                            face_points_data = [
                                Point(*obj_vertices[idx], color=active_color)
                                for idx in indices
                            ]
                            polygon_data = Polygon(
                                face_points_data, is_open=False, color=active_color
                            )
                            parsed_objects.append(polygon_data)
                        elif indices:  # 1 ou 2 índices válidos?
                            warnings.append(
                                f"Linha {line_num}: Face 'f' requer >= 3 vértices válidos: {line}"
                            )
                    else:
                        warnings.append(f"Linha {line_num}: Comando 'f' sem índices.")

                # Ignora outros comandos OBJ (vt, vn, g, s, etc.)

            except (ValueError, IndexError) as e:
                warnings.append(
                    f"Linha {line_num}: Erro ao processar '{command}': {line} - Detalhe: {e}"
                )
            except Exception as e:  # Erro inesperado
                warnings.append(
                    f"Linha {line_num}: Erro inesperado processando '{command}': {line} - Detalhe: {e}"
                )

        return parsed_objects, warnings

    def _parse_vertex_indices(
        self, index_parts: List[str], num_vertices: int, line_num: int
    ) -> List[int]:
        """Helper para analisar índices de vértices (ex: '1', '1/2', '1//3', '-1'). Retorna base 0."""
        indices: List[int] = []
        if num_vertices == 0 and index_parts:
            raise ValueError(f"Referência a vértices antes de 'v' ser definido.")

        for part in index_parts:
            # Pega apenas a parte do índice do vértice (antes do primeiro '/')
            index_str = part.split("/")[0]
            if not index_str:
                raise ValueError(f"Índice de vértice vazio encontrado ('{part}').")

            try:
                idx = int(index_str)
            except ValueError:
                raise ValueError(
                    f"Índice de vértice não numérico '{index_str}' ('{part}')."
                )

            if idx == 0:
                raise ValueError(
                    "Índice de vértice inválido (0). Índices OBJ são base 1."
                )
            elif idx > 0:  # Índice positivo (base 1)
                if idx <= num_vertices:
                    indices.append(idx - 1)  # Converte para base 0
                else:
                    raise IndexError(
                        f"Índice {idx} fora do intervalo [1..{num_vertices}]."
                    )
            else:  # Índice negativo (relativo ao fim, base 1)
                # Ex: -1 é o último vértice (índice num_vertices - 1 em base 0)
                rel_idx_base0 = num_vertices + idx
                if 0 <= rel_idx_base0 < num_vertices:
                    indices.append(rel_idx_base0)
                else:
                    raise IndexError(
                        f"Índice negativo {idx} (resolvido para {rel_idx_base0}) fora do intervalo [0..{num_vertices-1}]."
                    )
        return indices

    def generate_obj_data(
        self, data_objects: List[DataObject], mtl_filename: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]], List[str]]:
        """
        Gera conteúdo dos arquivos OBJ e MTL a partir dos objetos de dados da cena.

        Args:
            data_objects: Lista de Point, Line, Polygon da cena.
            mtl_filename: Nome do arquivo MTL a ser referenciado no OBJ (ex: 'cena.mtl').

        Returns:
            Tupla: (obj_lines, mtl_lines, warnings)
                   Retorna None para obj_lines/mtl_lines se não houver o que salvar.
        """
        warnings: List[str] = []
        savable_objects = [
            obj for obj in data_objects if isinstance(obj, (Point, Line, Polygon))
        ]

        if not savable_objects:
            warnings.append(
                "Nenhum objeto (Ponto, Linha, Polígono) na cena para salvar."
            )
            return None, None, warnings

        # --- Coleta Vértices e Materiais Únicos ---
        vertex_map: Dict[Tuple[float, float], int] = {}  # Mapeia (x,y) -> índice base 1
        output_vertices: List[Tuple[float, float]] = (
            []
        )  # Lista de vértices únicos (x,y)
        materials: Dict[str, QColor] = {}  # Mapeia nome_material -> QColor
        object_material_map: List[Tuple[DataObject, str]] = (
            []
        )  # Mapeia objeto -> nome_material
        vertex_counter = 1  # Índice OBJ (base 1)

        for i, data_object in enumerate(savable_objects):
            # 1. Determina cor e nome do material
            obj_color = getattr(data_object, "color", QColor(Qt.black))
            if not isinstance(obj_color, QColor) or not obj_color.isValid():
                warnings.append(
                    f"Obj {i+1} ({type(data_object).__name__}) sem cor válida. Usando preto."
                )
                obj_color = QColor(Qt.black)

            # Cria nome do material baseado no HEX da cor (evita nomes inválidos)
            color_hex = obj_color.name(QColor.HexRgb).upper()[1:]  # Ex: "FF0000"
            material_name = f"mat_{color_hex}"
            if material_name not in materials:
                materials[material_name] = obj_color
            object_material_map.append((data_object, material_name))

            # 2. Coleta coordenadas dos vértices do objeto
            try:
                coords_list = (
                    data_object.get_coords()
                )  # Espera List[Tuple[float, float]]
                # Se for Ponto, get_coords retorna Tuple, então envolve em lista
                if isinstance(data_object, Point):
                    coords_list = [coords_list]

            except AttributeError:
                warnings.append(
                    f"Obj {i+1} ({type(data_object).__name__}) sem método 'get_coords'. Ignorando."
                )
                continue
            except Exception as e:
                warnings.append(
                    f"Erro inesperado ao obter coords do Obj {i+1}: {e}. Ignorando."
                )
                continue

            # 3. Adiciona vértices únicos ao mapa
            for coords_tuple in coords_list:
                if not isinstance(coords_tuple, tuple) or len(coords_tuple) != 2:
                    warnings.append(
                        f"Coord inesperada {coords_tuple} para Obj {i+1}. Ignorando vértice."
                    )
                    continue
                # Arredonda para evitar problemas de ponto flutuante no mapeamento
                # Ajuste o número de casas decimais conforme necessário
                key_coords = (round(coords_tuple[0], 6), round(coords_tuple[1], 6))

                if key_coords not in vertex_map:
                    vertex_map[key_coords] = vertex_counter
                    output_vertices.append(key_coords)  # Adiciona o vértice arredondado
                    vertex_counter += 1

        if not output_vertices:
            warnings.append("Nenhum vértice encontrado nos objetos para salvar.")
            return None, None, warnings

        # --- Geração do Conteúdo MTL ---
        mtl_lines: Optional[List[str]] = None
        if materials:
            mtl_lines = []
            mtl_lines.append("# Arquivo de Materiais gerado pelo Editor Gráfico 2D")
            mtl_lines.append(f"# Total de Materiais: {len(materials)}")
            mtl_lines.append("")
            for name, color in materials.items():
                mtl_lines.append(f"newmtl {name}")
                # Cores como float [0.0, 1.0]
                r, g, b = color.redF(), color.greenF(), color.blueF()
                mtl_lines.append(f"Kd {r:.6f} {g:.6f} {b:.6f}")  # Cor Difusa
                # Outras propriedades básicas (Ka, Ks, Ns, d, illum) - podem ser ajustadas
                mtl_lines.append("Ka 0.100000 0.100000 0.100000")  # Ambiente baixo
                mtl_lines.append("Ks 0.000000 0.000000 0.000000")  # Especular zero
                mtl_lines.append("Ns 0.0")  # Expoente especular
                mtl_lines.append("d 1.0")  # Opacidade total (não-transparente)
                mtl_lines.append("illum 1")  # Modelo de iluminação simples (cor*Kd)
                mtl_lines.append("")

        # --- Geração do Conteúdo OBJ ---
        obj_lines: List[str] = []
        obj_lines.append("# Arquivo OBJ gerado pelo Editor Gráfico 2D")
        if mtl_lines:
            mtl_filename_base = os.path.basename(mtl_filename)  # Apenas nome + extensão
            obj_lines.append(f"mtllib {mtl_filename_base}")
        obj_lines.append("")
        obj_lines.append(
            f"# Vértices: {len(output_vertices)}, Objetos: {len(savable_objects)}"
        )
        obj_lines.append("")

        # Definições de Vértices ('v x y z') - Z é sempre 0.0
        obj_lines.append("# Vértices Geométricos")
        for x, y in output_vertices:
            obj_lines.append(f"v {x:.6f} {y:.6f} 0.000000")
        obj_lines.append("")

        # Definições de Elementos (p, l, f) por objeto
        obj_lines.append("# Elementos Geométricos")
        last_material_name: Optional[str] = None

        for i, (data_object, material_name) in enumerate(object_material_map):
            obj_type_name = type(data_object).__name__
            obj_lines.append(f"o {obj_type_name}_{i+1}")  # Nome do objeto

            # Adiciona 'usemtl' se mudou e existe MTL
            if mtl_lines and material_name != last_material_name:
                if material_name in materials:
                    obj_lines.append(f"usemtl {material_name}")
                    last_material_name = material_name
                else:  # Erro interno, deveria estar em 'materials'
                    warnings.append(
                        f"Erro: Material '{material_name}' (Obj {i+1}) não encontrado no dict. 'usemtl' omitido."
                    )
                    last_material_name = (
                        None  # Força re-emissão se o próximo for válido
                    )

            # Escreve definição geométrica (p, l, f)
            indices_str_list: List[str] = []
            lookup_failed = False
            try:
                # Coleta coordenadas do objeto atual para buscar índices
                coords_for_indices = data_object.get_coords()
                if isinstance(data_object, Point):
                    coords_for_indices = [coords_for_indices]

                for coords_tuple in coords_for_indices:
                    if not isinstance(coords_tuple, tuple) or len(coords_tuple) != 2:
                        warnings.append(
                            f"Coord inesperada {coords_tuple} ao buscar índice para Obj {i+1}."
                        )
                        lookup_failed = True
                        break

                    # Usa coordenadas arredondadas para buscar no mapa
                    key_coords = (round(coords_tuple[0], 6), round(coords_tuple[1], 6))
                    if key_coords in vertex_map:
                        indices_str_list.append(str(vertex_map[key_coords]))  # Base 1
                    else:
                        warnings.append(
                            f"ERRO LOOKUP: Vértice {key_coords} (Obj {i+1}) não encontrado no mapa! OBJ pode ficar incorreto."
                        )
                        lookup_failed = True
                        break

                if lookup_failed:
                    continue  # Pula escrita de p/l/f para este objeto

                # Escreve linha p/l/f se índices foram encontrados
                if indices_str_list:
                    indices_str = " ".join(indices_str_list)
                    if isinstance(data_object, Point):
                        obj_lines.append(f"p {indices_str}")
                    elif isinstance(data_object, Line):
                        if len(indices_str_list) >= 2:
                            obj_lines.append(f"l {indices_str}")
                        else:
                            warnings.append(f"Linha {i+1} < 2 índices. 'l' ignorada.")
                    elif isinstance(data_object, Polygon):
                        if data_object.is_open:  # Polilinha
                            if len(indices_str_list) >= 2:
                                obj_lines.append(f"l {indices_str}")
                            else:
                                warnings.append(
                                    f"Polilinha {i+1} < 2 índices. 'l' ignorada."
                                )
                        else:  # Polígono fechado
                            if len(indices_str_list) >= 3:
                                obj_lines.append(f"f {indices_str}")
                            else:
                                warnings.append(
                                    f"Polígono {i+1} < 3 índices. 'f' ignorada."
                                )

            except Exception as e:
                err_msg = (
                    f"Erro inesperado ao gerar índices/linha OBJ para Obj {i+1}: {e}"
                )
                warnings.append(err_msg)
                obj_lines.append(f"# AVISO: {err_msg}")

            obj_lines.append("")  # Linha em branco entre elementos

        return obj_lines, mtl_lines, warnings
