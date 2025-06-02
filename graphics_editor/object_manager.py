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
from .models.bspline_curve import BSplineCurve

DataObject = Union[Point, Line, Polygon, BezierCurve, BSplineCurve]
# Este DATA_OBJECT_TYPES é especificamente para objetos 2D que podem ser salvos/carregados de OBJ/MTL.
# Objetos 3D não são tratados por este gerenciador para OBJ/MTL nesta versão.
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve, BSplineCurve)


class ObjectManager:
    """
    Gerencia a conversão entre dados de arquivo OBJ/MTL e os objetos de dados internos 2D.

    Esta classe é responsável por:
    - Converter dados OBJ/MTL em objetos internos 2D (Point, Line, Polygon, BezierCurve, BSplineCurve)
    - Gerar dados OBJ/MTL a partir de objetos internos 2D
    - Gerenciar a aproximação de curvas de Bézier e B-spline como polilinhas para salvamento
    - Tratar erros e gerar avisos durante a conversão

    Nota: Curvas de Bézier e B-spline são aproximadas como polilinhas ao salvar e não são
          reconstruídas como curvas ao carregar de OBJ. Objetos 3D não são tratados.
    """

    DEFAULT_BEZIER_SAVE_SAMPLES = 20
    DEFAULT_BSPLINE_SAVE_SAMPLES = 20  # Número de segmentos para aproximar B-Spline

    def __init__(
        self,
        bezier_samples: Optional[int] = None,
        bspline_samples: Optional[int] = None,
    ):
        """
        Inicializa o gerenciador de objetos.

        Args:
            bezier_samples: Número de amostras por segmento para aproximação de Bézier ao salvar.
            bspline_samples: Número total de pontos de amostragem para aproximação de B-spline ao salvar.
        """
        self.bezier_save_samples = (
            bezier_samples
            if bezier_samples is not None
            else self.DEFAULT_BEZIER_SAVE_SAMPLES
        )
        self.bspline_save_samples = (
            bspline_samples
            if bspline_samples is not None
            else self.DEFAULT_BSPLINE_SAVE_SAMPLES
        )

    def parse_obj_data(
        self,
        obj_lines: List[str],
        material_colors: Dict[str, QColor],
        default_color: QColor = QColor(Qt.black),
    ) -> Tuple[List[DataObject], List[str]]:
        """
        Analisa linhas de um arquivo OBJ e converte em objetos de dados 2D.

        Args:
            obj_lines: Linhas relevantes do OBJ (sem comentários/vazias).
            material_colors: Dicionário {nome_material: QColor} do MTL.
            default_color: Cor padrão se material não for encontrado.

        Returns:
            Tuple[List[DataObject], List[str]]: Tupla contendo:
                - Lista de objetos de dados 2D criados.
                - Lista de avisos gerados durante a análise.
        """
        parsed_objects: List[DataObject] = []
        warnings: List[str] = []
        obj_vertices: List[Tuple[float, float]] = []  # Armazena apenas (x,y) para 2D
        active_color: QColor = default_color
        local_warnings: List[str] = []

        for line_num, line in enumerate(obj_lines, 1):
            parts = line.split()
            if not parts:
                continue
            command = parts[0].lower()

            try:
                if command == "v":  # Vértice
                    if (
                        len(parts) >= 3
                    ):  # OBJ 'v x y z [w]'. Para 2D, usamos x, y. Ignoramos z.
                        x, y = float(parts[1]), float(parts[2])
                        obj_vertices.append((x, y))
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Vértice 'v' malformado (esperado 'v x y [z]'): {line}"
                        )
                elif command == "usemtl":  # Usar material
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
                elif command == "p":  # Ponto
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
                elif command == "l":  # Linha ou Polilinha
                    if len(parts) > 1:
                        indices = self._parse_vertex_indices(
                            parts[1:], len(obj_vertices), line_num, local_warnings
                        )
                        if len(indices) >= 2:
                            line_points_data = [
                                Point(*obj_vertices[idx], color=active_color)
                                for idx in indices
                            ]
                            if len(line_points_data) == 2:  # Linha simples
                                line_data = Line(
                                    line_points_data[0],
                                    line_points_data[1],
                                    color=active_color,
                                )
                                parsed_objects.append(line_data)
                            else:  # Polilinha (interpretada como Polygon aberto)
                                polyline_data = Polygon(
                                    line_points_data, is_open=True, color=active_color
                                )
                                parsed_objects.append(polyline_data)
                        elif indices:  # Apenas um índice válido para linha/polilinha
                            local_warnings.append(
                                f"Linha {line_num}: Linha/Polilinha 'l' requer >= 2 vértices válidos: {line}"
                            )
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Comando 'l' sem índices."
                        )
                elif command == "f":  # Face (Polígono fechado)
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
                                is_open=False,  # Faces são sempre fechadas
                                color=active_color,
                                is_filled=True,  # Assumimos que faces são preenchidas
                            )
                            parsed_objects.append(polygon_data)
                        elif indices:  # Menos de 3 índices válidos para face
                            local_warnings.append(
                                f"Linha {line_num}: Face 'f' requer >= 3 vértices válidos: {line}"
                            )
                    else:
                        local_warnings.append(
                            f"Linha {line_num}: Comando 'f' sem índices."
                        )
                # Ignorar comandos OBJ 3D não relevantes para carregamento 2D (vn, vt, s, g, o etc.)

            except (ValueError, IndexError) as e:
                local_warnings.append(
                    f"Linha {line_num}: Erro ao processar '{command}': {line} - Detalhe: {e}"
                )
            except Exception as e:  # Captura genérica para outros erros inesperados
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
        Formato de índice OBJ: v, v/vt, v/vt/vn, v//vn. Consideramos apenas 'v'.

        Args:
            index_parts: Lista de strings contendo os índices.
            num_vertices: Número total de vértices disponíveis.
            line_num: Número da linha sendo processada.
            warnings_list: Lista para acumular avisos.

        Returns:
            List[int]: Lista de índices convertidos para base 0.
        """
        indices: List[int] = []
        if (
            num_vertices == 0 and index_parts
        ):  # Tentativa de usar vértices antes de serem definidos
            warnings_list.append(
                f"Linha {line_num}: Referência a vértices antes de qualquer comando 'v' ser definido."
            )
            return []

        for part_str in index_parts:
            # Um índice OBJ pode ser 'v', 'v/vt', 'v/vt/vn', ou 'v//vn'.
            # Pegamos apenas a parte 'v' (antes do primeiro '/').
            vertex_index_str = part_str.split("/")[0]

            if not vertex_index_str:  # Parte vazia, e.g., de "l 1  2"
                warnings_list.append(
                    f"Linha {line_num}: Índice de vértice vazio encontrado ('{part_str}')."
                )
                continue

            try:
                idx = int(vertex_index_str)
            except ValueError:
                warnings_list.append(
                    f"Linha {line_num}: Índice de vértice não numérico '{vertex_index_str}' ('{part_str}')."
                )
                continue

            if idx == 0:
                warnings_list.append(
                    f"Linha {line_num}: Índice de vértice inválido (0). Índices OBJ são base 1."
                )
                continue
            elif idx > 0:  # Índice positivo (base 1)
                if idx <= num_vertices:
                    indices.append(idx - 1)  # Converter para base 0
                else:
                    warnings_list.append(
                        f"Linha {line_num}: Índice {idx} fora do intervalo [1..{num_vertices}]."
                    )
            else:  # Índice negativo (relativo ao final da lista de vértices atual)
                # Por exemplo, -1 é o último vértice definido
                relative_index_base0 = num_vertices + idx
                if 0 <= relative_index_base0 < num_vertices:
                    indices.append(relative_index_base0)
                else:
                    warnings_list.append(
                        f"Linha {line_num}: Índice negativo {idx} (resolvido para {relative_index_base0}) fora do intervalo [0..{num_vertices-1}]."
                    )
        return indices

    def generate_obj_data(
        self, data_objects: List[DataObject], mtl_filename: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]], List[str]]:
        """
        Gera conteúdo dos arquivos OBJ e MTL a partir dos objetos 2D internos.

        Args:
            data_objects: Lista de objetos da cena (Point, Line, Polygon, BezierCurve, BSplineCurve).
            mtl_filename: Nome do arquivo MTL a ser referenciado no OBJ.

        Returns:
            Tuple[Optional[List[str]], Optional[List[str]], List[str]]: Tupla contendo:
                - Linhas do arquivo OBJ (ou None se não houver o que salvar).
                - Linhas do arquivo MTL (ou None se não houver o que salvar).
                - Lista de avisos gerados durante a geração.
        """
        warnings: List[str] = []
        # Filtra apenas objetos 2D que este gerenciador sabe salvar
        savable_objects = [
            obj for obj in data_objects if isinstance(obj, DATA_OBJECT_TYPES)
        ]

        if not savable_objects:
            warnings.append(
                "Nenhum objeto 2D suportado (Ponto, Linha, Polígono, Bézier, B-spline) na cena para salvar."
            )
            return None, None, warnings

        vertex_map: Dict[Tuple[float, float], int] = (
            {}
        )  # Mapeia (x,y) para índice OBJ (1-based)
        output_vertices: List[Tuple[float, float]] = (
            []
        )  # Lista de vértices únicos (x,y) para OBJ
        materials: Dict[str, QColor] = {}  # nome_material -> QColor

        # Guarda definições processadas: (tipo_obj_string, nome_material, lista_coords_chave, ref_obj_original)
        object_definitions: List[
            Tuple[str, str, List[Tuple[float, float]], DataObject]
        ] = []
        vertex_counter = 1  # Índices OBJ são base 1

        for i, data_object in enumerate(savable_objects):
            obj_type_name_original = type(
                data_object
            ).__name__  # e.g. "Point", "BezierCurve"
            obj_type_name_for_obj = (
                obj_type_name_original  # Pode mudar para aproximações
            )

            obj_color = getattr(data_object, "color", QColor(Qt.black))
            if not isinstance(obj_color, QColor) or not obj_color.isValid():
                warnings.append(
                    f"Obj {i+1} ({obj_type_name_original}) sem cor válida. Usando preto."
                )
                obj_color = QColor(Qt.black)

            color_hex = obj_color.name(QColor.HexRgb).upper()[1:]  # e.g., "FF0000"
            material_name = f"mat_{color_hex}"
            if material_name not in materials:
                materials[material_name] = obj_color

            coords_list_for_obj: List[Tuple[float, float]] = []

            try:
                if isinstance(data_object, BezierCurve):
                    # Amostra curva de Bézier como polilinha
                    sampled_qpoints = data_object.sample_curve(self.bezier_save_samples)
                    coords_list_for_obj = [(qp.x(), qp.y()) for qp in sampled_qpoints]
                    if len(coords_list_for_obj) < 2:
                        warnings.append(
                            f"Bézier Obj {i+1} não pôde ser amostrado em pontos suficientes ({len(coords_list_for_obj)}). Ignorando."
                        )
                        continue
                    obj_type_name_for_obj = (
                        "BezierApproximation"  # Indica que é uma aproximação
                    )
                elif isinstance(data_object, BSplineCurve):
                    # Amostra curva B-spline como polilinha
                    # BSplineCurve.get_curve_points deve retornar List[Tuple[float,float]]
                    coords_list_for_obj = data_object.get_curve_points(
                        self.bspline_save_samples
                    )
                    if len(coords_list_for_obj) < 2:
                        warnings.append(
                            f"B-spline Obj {i+1} não pôde ser amostrado em pontos suficientes ({len(coords_list_for_obj)}). Ignorando."
                        )
                        continue
                    obj_type_name_for_obj = "BSplineApproximation"
                else:  # Point, Line, Polygon
                    raw_coords_from_model = data_object.get_coords()
                    if isinstance(
                        data_object, Point
                    ):  # Point.get_coords() -> Tuple[float,float]
                        coords_list_for_obj = [raw_coords_from_model]
                    elif isinstance(
                        raw_coords_from_model, list
                    ):  # Line/Polygon.get_coords() -> List[Tuple[float,float]]
                        coords_list_for_obj = raw_coords_from_model
                    else:
                        raise TypeError(
                            "get_coords() retornou tipo inesperado para objeto não-curva."
                        )

            except AttributeError as ae:  # Se método sample_curve ou get_coords faltar
                warnings.append(
                    f"Erro de atributo ao obter/processar coords do Obj {i+1} ({obj_type_name_original}): {ae}. Ignorando."
                )
                continue
            except Exception as e:
                warnings.append(
                    f"Erro ao obter/processar coords do Obj {i+1} ({obj_type_name_original}): {e}. Ignorando."
                )
                continue

            if not coords_list_for_obj:
                warnings.append(
                    f"Obj {i+1} ({obj_type_name_original}) sem coordenadas válidas após processamento. Ignorando."
                )
                continue

            current_object_vertex_key_coords = (
                []
            )  # Coordenadas chave (arredondadas) para este objeto
            for coords_tuple in coords_list_for_obj:
                if not isinstance(coords_tuple, tuple) or len(coords_tuple) != 2:
                    warnings.append(
                        f"Coordenada inesperada {coords_tuple} para Obj {i+1}. Ignorando vértice."
                    )
                    continue
                # Arredonda coordenadas para uma precisão razoável para a chave do vertex_map
                key_coords = (round(coords_tuple[0], 6), round(coords_tuple[1], 6))
                if key_coords not in vertex_map:
                    vertex_map[key_coords] = vertex_counter
                    output_vertices.append(
                        key_coords
                    )  # Armazena as coordenadas arredondadas para saída OBJ
                    vertex_counter += 1
                current_object_vertex_key_coords.append(key_coords)

            object_definitions.append(
                (
                    obj_type_name_for_obj,  # Pode ser "BezierApproximation", etc.
                    material_name,
                    current_object_vertex_key_coords,
                    data_object,  # Guarda referência ao objeto original
                )
            )

        if not output_vertices:  # Nenhum vértice válido para salvar
            warnings.append("Nenhum vértice válido encontrado nos objetos para salvar.")
            return None, None, warnings

        # --- Gerar conteúdo do arquivo MTL ---
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
                        f"Kd {color.redF():.6f} {color.greenF():.6f} {color.blueF():.6f}",  # Cor Difusa
                        "Ka 0.1 0.1 0.1",  # Cor Ambiente (opcional, pode ser igual a Kd ou fixa)
                        "Ks 0.0 0.0 0.0",  # Cor Especular (nenhuma para 2D)
                        "Ns 0.0",  # Expoente especular
                        "d 1.0",  # Dissolve (opacidade total)
                        "illum 1",  # Modelo de iluminação (1 = difuso + ambiente)
                        "",
                    ]
                )

        # --- Gerar conteúdo do arquivo OBJ ---
        obj_lines: List[str] = ["# Arquivo OBJ (Editor Gráfico 2D)"]
        if mtl_lines:  # Adiciona referência mtllib apenas se arquivo MTL for gerado
            obj_lines.append(f"mtllib {os.path.basename(mtl_filename)}")
        obj_lines.extend(
            [
                "",
                f"# Vértices: {len(output_vertices)}, Objetos: {len(object_definitions)}",
                "",
            ]
        )
        obj_lines.append("# Vértices Geométricos (z=0 para 2D)")
        for x, y in output_vertices:  # Estes são os vértices únicos e arredondados
            obj_lines.append(
                f"v {x:.6f} {y:.6f} 0.0"
            )  # Adiciona z=0 para compatibilidade
        obj_lines.append("")
        obj_lines.append("# Elementos Geométricos")

        last_material_name_used: Optional[str] = None

        for i, (
            obj_type,
            material,
            vertex_key_coords_list,
            original_obj_ref,
        ) in enumerate(object_definitions):
            obj_lines.append(f"o {obj_type}_{i+1}")  # Nome do objeto no OBJ

            # Uso de material
            if mtl_lines and material != last_material_name_used:
                if material in materials:  # Deve ser sempre verdade
                    obj_lines.append(f"usemtl {material}")
                    last_material_name_used = material
                else:  # Erro interno improvável
                    warnings.append(
                        f"Erro Interno: Material '{material}' para Obj {i+1} não encontrado."
                    )

            # Obtém índices dos vértices para este objeto
            indices_str_list_for_obj: List[str] = []
            lookup_failed_for_this_obj = False
            for (
                key_coords_for_lookup
            ) in vertex_key_coords_list:  # Coordenadas chave arredondadas
                if key_coords_for_lookup in vertex_map:
                    indices_str_list_for_obj.append(
                        str(vertex_map[key_coords_for_lookup])
                    )
                else:
                    warnings.append(
                        f"ERRO DE CONSULTA: Vértice {key_coords_for_lookup} (Obj {i+1}) não encontrado. OBJ estará incorreto."
                    )
                    lookup_failed_for_this_obj = True
                    break

            if lookup_failed_for_this_obj:
                obj_lines.append(
                    "# ERRO: Falha ao encontrar índices de vértices para este objeto."
                )
                obj_lines.append("")
                continue

            indices_str_output = " ".join(indices_str_list_for_obj)
            if not indices_str_output:  # Nenhum índice válido para este objeto
                warnings.append(
                    f"Obj {i+1} ({obj_type}) sem índices válidos. Ignorando."
                )
                continue

            # Tipo de elemento OBJ baseado no tipo do objeto original (ou sua aproximação)
            if obj_type == "Point":
                obj_lines.append(f"p {indices_str_output}")
            elif obj_type == "Line":  # Pode ser uma Line simples
                if len(indices_str_list_for_obj) >= 2:
                    obj_lines.append(f"l {indices_str_output}")
                else:
                    warnings.append(f"Linha {i+1} < 2 índices. Ignorando 'l'.")
            elif obj_type == "Polygon":  # Polígono fechado
                if isinstance(original_obj_ref, Polygon):
                    if original_obj_ref.is_open:  # Era uma Polilinha
                        if len(indices_str_list_for_obj) >= 2:
                            obj_lines.append(f"l {indices_str_output}")
                        else:
                            warnings.append(
                                f"Polilinha {i+1} < 2 índices. Ignorando 'l'."
                            )
                    else:  # Era um Polígono Fechado
                        if len(indices_str_list_for_obj) >= 3:
                            obj_lines.append(f"f {indices_str_output}")  # Faces são 'f'
                        else:
                            warnings.append(
                                f"Polígono {i+1} < 3 índices. Ignorando 'f'."
                            )
                else:  # Não deve acontecer
                    warnings.append(
                        f"Erro Interno: Esperado Polígono mas encontrado {type(original_obj_ref).__name__} para tipo 'Polygon'."
                    )
            elif (
                obj_type == "BezierApproximation" or obj_type == "BSplineApproximation"
            ):
                # Aproximações de curvas são salvas como polilinhas ('l')
                if len(indices_str_list_for_obj) >= 2:
                    obj_lines.append(f"l {indices_str_output}")
                else:
                    warnings.append(
                        f"Aproximação de Curva {i+1} < 2 índices. Ignorando 'l'."
                    )
            obj_lines.append(
                ""
            )  # Linha em branco após cada grupo de definição de objeto

        return obj_lines, mtl_lines, warnings
