# graphics_editor/object_manager.py
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

# Importa os modelos usando caminhos relativos
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon

# Define um tipo para os objetos de dados gerenciados
DataObject = Union[Point, Line, Polygon]


class ObjectManager:
    """
    Gerencia a conversão entre dados de arquivo OBJ/MTL e os objetos de
    dados internos da aplicação (Point, Line, Polygon).
    """

    def parse_obj_data(
        self,
        obj_lines: List[str],
        material_colors: Dict[str, QColor],
        default_color: QColor = QColor(Qt.black), # Cor padrão caso material falhe
    ) -> Tuple[List[DataObject], List[str]]:
        """
        Analisa linhas de um arquivo OBJ e as converte em objetos Point, Line, Polygon.
        Utiliza as cores de materiais fornecidas.

        Args:
            obj_lines: Lista de linhas relevantes de um arquivo OBJ (sem comentários/vazias).
            material_colors: Dicionário mapeando nomes de material (do MTL) para QColor.
            default_color: Cor a ser usada se um material não for encontrado ou definido.

        Returns:
            Uma tupla contendo:
                - Lista de instâncias DataObject criadas (Point, Line, Polygon).
                - Lista de mensagens de aviso geradas durante a análise.
        """
        parsed_objects: List[DataObject] = []
        warnings: List[str] = []
        # Armazena os vértices ('v' lines) definidos no OBJ (base 1 para índices OBJ)
        # Usamos uma lista de tuplas (float, float) para simplicidade 2D
        obj_vertices: List[Tuple[float, float]] = []
        current_material_name: Optional[str] = None
        active_color: QColor = default_color # Cor ativa no momento da análise

        for line_num, line in enumerate(obj_lines, 1): # Enumera a partir de 1 para msgs
            parts = line.split()
            if not parts: continue # Linha ficou vazia após split? (não deveria acontecer)
            command = parts[0].lower() # Comando OBJ (v, f, l, p, usemtl, etc.)

            # --- Processamento de Vértices ('v') ---
            if command == "v":
                if len(parts) >= 3: # Precisa de 'v', x, y (ignora z, w se houver)
                    try:
                        x = float(parts[1])
                        y = float(parts[2])
                        obj_vertices.append((x, y))
                    except (ValueError):
                        warnings.append(f"Linha {line_num}: Ignorando vértice 'v' com coordenadas não numéricas: {line}")
                else:
                    warnings.append(f"Linha {line_num}: Ignorando vértice 'v' malformado (coordenadas ausentes): {line}")

            # --- Processamento de Materiais ('usemtl') ---
            elif command == "usemtl":
                if len(parts) > 1:
                    material_name = " ".join(parts[1:]) # Permite nomes com espaços
                    current_material_name = material_name
                    # Tenta obter a cor do dicionário, senão usa a padrão
                    active_color = material_colors.get(current_material_name, default_color)
                    if current_material_name not in material_colors:
                        warnings.append(f"Linha {line_num}: Material '{current_material_name}' usado mas não definido no MTL. Usando cor padrão.")
                else:
                    warnings.append(f"Linha {line_num}: Comando 'usemtl' sem nome de material. Usando cor padrão.")
                    current_material_name = None
                    active_color = default_color # Volta para cor padrão

            # --- Processamento de Pontos ('p') ---
            elif command == "p":
                if len(parts) > 1:
                    try:
                        # Parseia os índices dos vértices para os pontos
                        indices = self._parse_vertex_indices(parts[1:], len(obj_vertices), line_num)
                        # Cria um objeto Point para cada índice válido
                        for idx in indices:
                            coords = obj_vertices[idx] # Obtém coords do vértice (base 0)
                            point_data = Point(coords[0], coords[1], color=active_color)
                            parsed_objects.append(point_data)
                    except (IndexError, ValueError) as e:
                        warnings.append(f"Linha {line_num}: Ignorando ponto(s) 'p' com índice(s) inválido(s) ou malformados: {line} - Erro: {e}")
                else:
                     warnings.append(f"Linha {line_num}: Ignorando comando 'p' sem índices de vértice.")

            # --- Processamento de Linhas/Polilinhas ('l') ---
            elif command == "l":
                if len(parts) > 1:
                    try:
                        indices = self._parse_vertex_indices(parts[1:], len(obj_vertices), line_num)
                        if len(indices) >= 2:
                            # Cria objetos Point para cada vértice da linha/polilinha
                            line_points_data = []
                            for idx in indices:
                                coords = obj_vertices[idx]
                                line_points_data.append(Point(coords[0], coords[1], color=active_color))

                            # Se forem exatamente 2 pontos, cria uma Line
                            if len(line_points_data) == 2:
                                line_data = Line(line_points_data[0], line_points_data[1], color=active_color)
                                parsed_objects.append(line_data)
                            # Se forem mais de 2 pontos, cria um Polygon aberto (polilinha)
                            else:
                                polyline_data = Polygon(line_points_data, is_open=True, color=active_color)
                                parsed_objects.append(polyline_data)
                        elif indices: # Tinha índices, mas não o suficiente (apenas 1)
                            warnings.append(f"Linha {line_num}: Linha/Polilinha 'l' requer pelo menos 2 vértices válidos. Ignorando: {line}")

                    except (IndexError, ValueError) as e:
                        warnings.append(f"Linha {line_num}: Ignorando linha/polilinha 'l' com índice(s) inválido(s) ou malformada: {line} - Erro: {e}")
                else:
                     warnings.append(f"Linha {line_num}: Ignorando comando 'l' sem índices de vértice.")


            # --- Processamento de Faces ('f') ---
            elif command == "f":
                if len(parts) > 1:
                    try:
                        indices = self._parse_vertex_indices(parts[1:], len(obj_vertices), line_num)
                        if len(indices) >= 3: # Face requer no mínimo 3 vértices
                            # Cria objetos Point para cada vértice da face
                            face_points_data = []
                            for idx in indices:
                                coords = obj_vertices[idx]
                                face_points_data.append(Point(coords[0], coords[1], color=active_color))
                            # Cria um Polygon fechado
                            polygon_data = Polygon(face_points_data, is_open=False, color=active_color)
                            parsed_objects.append(polygon_data)
                        elif indices: # Tinha índices, mas não o suficiente (1 ou 2)
                             warnings.append(f"Linha {line_num}: Face 'f' requer pelo menos 3 vértices válidos. Ignorando: {line}")

                    except (IndexError, ValueError) as e:
                        warnings.append(f"Linha {line_num}: Ignorando face 'f' com índice(s) inválido(s) ou malformada: {line} - Erro: {e}")
                else:
                     warnings.append(f"Linha {line_num}: Ignorando comando 'f' sem índices de vértice.")

            # Outros comandos OBJ (vt, vn, g, o, s, etc.) são ignorados nesta versão 2D simples

        return parsed_objects, warnings

    def _parse_vertex_indices(self, index_parts: List[str], num_vertices: int, line_num: int) -> List[int]:
        """
        Helper para analisar índices de vértices de strings como '1', '1/2', '1/2/3', '1//3'.
        Retorna apenas o índice do vértice (o primeiro número).
        Lida com índices positivos (base 1) e negativos (relativos ao fim).

        Args:
            index_parts: Lista de strings de índice (ex: ["1/1", "2/2", "3/3"]).
            num_vertices: O número total de vértices ('v') lidos até agora.
            line_num: Número da linha atual para mensagens de erro.

        Returns:
            Lista de índices de vértice base 0 válidos.

        Raises:
            ValueError: Se um índice não for numérico ou for zero.
            IndexError: Se um índice (positivo ou negativo) estiver fora dos limites válidos.
        """
        indices: List[int] = []
        if num_vertices == 0: # Não pode referenciar vértices se nenhum foi definido
             raise ValueError("Tentativa de referenciar vértices antes de qualquer linha 'v' ser definida.")

        for part in index_parts:
            # Pega apenas a parte antes da primeira '/' (índice do vértice)
            index_str = part.split('/')[0]
            if not index_str: # Verifica se a string do índice não está vazia
                raise ValueError(f"Índice de vértice vazio encontrado na linha {line_num}.")

            try:
                idx = int(index_str)
            except ValueError:
                raise ValueError(f"Índice de vértice não numérico '{index_str}' encontrado na linha {line_num}.")

            if idx == 0:
                 raise ValueError(f"Índice de vértice inválido (zero) encontrado na linha {line_num}. Índices OBJ são base 1.")
            elif idx > 0:
                # Índice positivo (base 1): converte para base 0
                if 1 <= idx <= num_vertices:
                    indices.append(idx - 1)
                else:
                    raise IndexError(f"Índice de vértice positivo {idx} fora dos limites [1..{num_vertices}] na linha {line_num}.")
            else: # idx < 0
                # Índice negativo (relativo ao fim): converte para base 0
                # Ex: -1 refere-se ao último vértice (índice num_vertices - 1)
                rel_idx = num_vertices + idx
                if 0 <= rel_idx < num_vertices:
                    indices.append(rel_idx)
                else:
                    raise IndexError(f"Índice de vértice negativo {idx} (resolvido para {rel_idx}) fora dos limites [0..{num_vertices-1}] na linha {line_num}.")
        return indices

    def generate_obj_data(
        self, data_objects: List[DataObject], mtl_filename: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]], List[str]]:
        """
        Gera o conteúdo dos arquivos OBJ e MTL a partir de uma lista de objetos de dados da cena.

        Args:
            data_objects: Lista de instâncias Point, Line ou Polygon a serem salvas.
            mtl_filename: Nome do arquivo MTL a ser referenciado no OBJ (ex: "cena.mtl").

        Returns:
            Uma tupla contendo:
                - Lista de strings para o arquivo OBJ, ou None se não houver objetos salváveis.
                - Lista de strings para o arquivo MTL, ou None se nenhum material for necessário/gerado.
                - Lista de mensagens de aviso geradas durante a geração.
        """
        warnings: List[str] = []
        # Filtra apenas os tipos de objetos que sabemos como salvar
        savable_objects = [
            obj for obj in data_objects if isinstance(obj, (Point, Line, Polygon))
        ]

        if not savable_objects:
            warnings.append("Nenhum objeto (Ponto, Linha, Polígono) encontrado na cena para salvar.")
            return None, None, warnings

        # --- Coleta de Vértices e Materiais Únicos ---
        vertex_map: Dict[Tuple[float, float], int] = {} # Mapeia coordenada (x,y) -> índice do vértice (base 1)
        output_vertices: List[Tuple[float, float]] = [] # Lista de vértices únicos a serem escritos
        vertex_counter = 1 # Contador de índice de vértice (base 1)
        materials: Dict[str, QColor] = {} # Mapeia nome do material -> QColor
        object_material_map: List[Tuple[DataObject, str]] = [] # Mapeia objeto -> nome do material

        for i, data_object in enumerate(savable_objects):
            # 1. Determina a cor e o nome do material do objeto
            obj_color: QColor = QColor(Qt.black) # Padrão
            if hasattr(data_object, "color") and isinstance(data_object.color, QColor) and data_object.color.isValid():
                obj_color = data_object.color
            else:
                warnings.append(f"Objeto {i+1} ({type(data_object).__name__}) sem cor válida. Usando preto.")

            # Cria um nome de material baseado na cor hexadecimal (ex: mat_FF0000 para vermelho)
            # Isso agrupa objetos da mesma cor sob o mesmo material
            color_hex = obj_color.name(QColor.HexRgb).upper()[1:] # Remove o '#' inicial
            material_name = f"mat_{color_hex}"
            if material_name not in materials:
                materials[material_name] = obj_color # Adiciona novo material único
            object_material_map.append((data_object, material_name)) # Associa objeto ao material

            # 2. Coleta as coordenadas do objeto
            coords_list: List[Tuple[float, float]] = []
            if isinstance(data_object, Point):
                coords_list = [data_object.get_coords()]
            elif isinstance(data_object, Line):
                coords_list = data_object.get_coords()
            elif isinstance(data_object, Polygon):
                coords_list = data_object.get_coords()

            # 3. Adiciona vértices únicos ao mapa e à lista de saída
            for coords in coords_list:
                # Chave do mapa é a tupla de coordenadas (float, float)
                # Não arredondamos aqui para manter precisão, mas pode causar vértices ligeiramente diferentes
                # TODO: Considerar arredondar para agrupar vértices muito próximos? (ex: round(c, 6))
                if coords not in vertex_map:
                    vertex_map[coords] = vertex_counter
                    output_vertices.append(coords)
                    vertex_counter += 1

        if not output_vertices:
            warnings.append("Nenhum vértice encontrado nos objetos para salvar.")
            return None, None, warnings

        # --- Geração do Conteúdo do Arquivo MTL (se houver materiais) ---
        mtl_lines: Optional[List[str]] = None
        if materials:
            mtl_lines = []
            mtl_lines.append("# Arquivo de Materiais gerado pelo Editor Gráfico 2D")
            mtl_lines.append(f"# Total de Materiais: {len(materials)}")
            mtl_lines.append("")
            for name, color in materials.items():
                mtl_lines.append(f"newmtl {name}")
                # Converte QColor para componentes R, G, B float [0.0, 1.0]
                r, g, b = color.redF(), color.greenF(), color.blueF()
                mtl_lines.append(f"Kd {r:.6f} {g:.6f} {b:.6f}") # Cor difusa (essencial)
                # Poderia adicionar outras propriedades padrão se necessário:
                mtl_lines.append("Ka 0.000000 0.000000 0.000000") # Ambiente
                mtl_lines.append("Ks 0.000000 0.000000 0.000000") # Especular
                mtl_lines.append("Ns 0.0")                      # Expoente especular
                mtl_lines.append("d 1.0")                       # Dissolve (opacidade)
                mtl_lines.append("illum 1")                     # Modelo de iluminação simples
                mtl_lines.append("")

        # --- Geração do Conteúdo do Arquivo OBJ ---
        obj_lines: List[str] = []
        obj_lines.append("# Arquivo OBJ gerado pelo Editor Gráfico 2D")
        if mtl_lines: # Adiciona referência ao MTL apenas se ele for gerado
            obj_lines.append(f"mtllib {mtl_filename}")
        obj_lines.append("")
        obj_lines.append(f"# Total de Vértices: {len(output_vertices)}")
        obj_lines.append(f"# Total de Objetos: {len(savable_objects)}")
        obj_lines.append("")

        # Escreve as definições de vértices ('v')
        obj_lines.append("# Definições de Vértices")
        for x, y in output_vertices:
            # Adiciona z=0.0 para compatibilidade 3D básica
            obj_lines.append(f"v {x:.6f} {y:.6f} 0.000000")
        obj_lines.append("")

        # Escreve as definições de elementos (pontos, linhas, faces) por objeto
        obj_lines.append("# Definições de Elementos Geométricos")
        last_material_name: Optional[str] = None # Rastreia o último material usado
        for i, (data_object, material_name) in enumerate(object_material_map):
            obj_type_name = type(data_object).__name__
            # Opcional: Adiciona nome do objeto ('o')
            obj_lines.append(f"o {obj_type_name}_{i+1}")

            # Adiciona 'usemtl' se o material mudou e existe
            if material_name != last_material_name:
                if material_name in materials:
                    obj_lines.append(f"usemtl {material_name}")
                    last_material_name = material_name
                else:
                    # Isso não deveria acontecer se a lógica acima estiver correta
                    warnings.append(f"Erro interno: Material '{material_name}' associado ao objeto {i+1} mas não encontrado no dicionário de materiais.")
                    last_material_name = None # Reseta para garantir 'usemtl' na próxima vez

            # Escreve a definição geométrica (p, l, f)
            indices_str_list: List[str] = []
            vertex_lookup_failed = False
            try:
                coords_to_lookup = []
                if isinstance(data_object, Point):
                    coords_to_lookup = [data_object.get_coords()]
                elif isinstance(data_object, Line):
                    coords_to_lookup = data_object.get_coords()
                elif isinstance(data_object, Polygon):
                    coords_to_lookup = data_object.get_coords()

                # Converte coordenadas para índices de vértice (base 1)
                for coords in coords_to_lookup:
                    if coords in vertex_map:
                        indices_str_list.append(str(vertex_map[coords]))
                    else:
                        warnings.append(f"Vértice {coords} do objeto {i+1} ({obj_type_name}) não encontrado no mapa de vértices. Objeto pode estar incompleto.")
                        vertex_lookup_failed = True
                        # Não adiciona índice inválido, a linha pode ficar incompleta

                # Escreve a linha p/l/f apropriada se a busca foi bem-sucedida
                if not vertex_lookup_failed:
                    indices_str = " ".join(indices_str_list)
                    if isinstance(data_object, Point):
                        if len(indices_str_list) == 1:
                            obj_lines.append(f"p {indices_str}")
                        else: warnings.append(f"Objeto Point {i+1} resultou em {len(indices_str_list)} índices. Esperado 1.")
                    elif isinstance(data_object, Line):
                         if len(indices_str_list) == 2:
                             obj_lines.append(f"l {indices_str}")
                         else: warnings.append(f"Objeto Line {i+1} resultou em {len(indices_str_list)} índices. Esperado 2.")
                    elif isinstance(data_object, Polygon):
                        if data_object.is_open: # Polilinha
                             min_pts = 2
                             if len(indices_str_list) >= min_pts:
                                 obj_lines.append(f"l {indices_str}")
                             else: warnings.append(f"Polígono aberto {i+1} tem {len(indices_str_list)} vértices válidos. Requer {min_pts}. Ignorando linha 'l'.")
                        else: # Polígono fechado (Face)
                             min_pts = 3
                             if len(indices_str_list) >= min_pts:
                                 obj_lines.append(f"f {indices_str}")
                             else: warnings.append(f"Polígono fechado {i+1} tem {len(indices_str_list)} vértices válidos. Requer {min_pts}. Ignorando linha 'f'.")

            except Exception as e:
                # Captura qualquer erro inesperado durante o processamento deste objeto
                err_msg = f"Erro inesperado ao processar objeto {i+1} ({obj_type_name}) para salvar: {e}"
                warnings.append(err_msg)
                obj_lines.append(f"# AVISO: {err_msg}")

            obj_lines.append("") # Linha em branco entre objetos

        return obj_lines, mtl_lines, warnings
