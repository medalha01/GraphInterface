# graphics_editor/io_handler.py
import os
from typing import List, Optional, Dict, Tuple

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

class IOHandler:
    """
    Gerencia diálogos de arquivo e operações básicas de leitura/escrita
    para arquivos OBJ e MTL.
    """

    def __init__(self, parent_widget: QWidget):
        """
        Inicializa o IOHandler.
        Args:
            parent_widget: O widget pai (geralmente a janela principal) para os diálogos.
        """
        self._parent = parent_widget
        self._last_dir: Optional[str] = None # Armazena o último diretório acessado

    def prompt_load_obj(self) -> Optional[str]:
        """
        Abre um diálogo para selecionar um arquivo OBJ para carregar.
        Retorna:
            O caminho do arquivo selecionado, ou None se cancelado.
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Carregar Arquivo OBJ",
            self._last_dir or "", # Usa o último diretório ou o padrão
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath) # Atualiza o último diretório
            return filepath
        return None # Retorna None se o usuário cancelar

    def prompt_save_obj(self, default_filename: str = "untitled.obj") -> Optional[str]:
        """
        Abre um diálogo para selecionar um caminho base para salvar arquivos OBJ e MTL.
        Garante que a extensão .obj seja sugerida.
        Args:
            default_filename: O nome de arquivo sugerido no diálogo.
        Returns:
            O caminho base selecionado (sem garantia de extensão), ou None se cancelado.
            Ex: Se o usuário escolher 'meu/arquivo.obj', retorna 'meu/arquivo'.
        """
        # Garante que o nome padrão termine com .obj
        if not default_filename.lower().endswith(".obj"):
            default_filename += ".obj"

        filepath, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Salvar Como Arquivo OBJ",
            os.path.join(self._last_dir or "", default_filename), # Combina último dir e nome
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
            options=QFileDialog.Options() | QFileDialog.DontConfirmOverwrite # Deixa o sistema lidar com confirmação
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath) # Atualiza o último diretório
            # Remove a extensão .obj (ou qualquer outra) para obter o caminho base
            base_path, _ = os.path.splitext(filepath)
            return base_path
        return None # Retorna None se o usuário cancelar

    def read_obj_lines(self, filepath: str) -> Optional[Tuple[List[str], Optional[str]]]:
        """
        Lê as linhas relevantes de um arquivo OBJ e encontra a referência mtllib.
        Args:
            filepath: O caminho para o arquivo OBJ.
        Returns:
            Uma tupla contendo:
              - Lista de linhas OBJ relevantes (sem espaços extras, não vazias, não comentários).
              - O nome do arquivo especificado na linha mtllib (se encontrado), senão None.
            Retorna None se o arquivo não puder ser lido ou ocorrer um erro.
        """
        obj_lines: List[str] = []
        mtl_filename: Optional[str] = None
        try:
            with open(filepath, "r", encoding='utf-8') as f: # Especifica encoding
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    # Ignora linhas vazias ou comentários
                    if not stripped_line or stripped_line.startswith("#"):
                        continue

                    obj_lines.append(stripped_line)
                    parts = stripped_line.split()
                    # Procura pela diretiva 'mtllib' (case-insensitive)
                    if len(parts) > 1 and parts[0].lower() == "mtllib":
                        # Armazena apenas a primeira referência mtllib encontrada
                        if mtl_filename is None:
                            # Junta o resto da linha caso o nome tenha espaços (incomum mas possível)
                            mtl_filename = " ".join(parts[1:])
                        else:
                            QMessageBox.warning(self._parent, "Aviso de Leitura OBJ",
                                                f"Múltiplas linhas 'mtllib' encontradas no arquivo '{os.path.basename(filepath)}'. Usando a primeira: '{mtl_filename}'.")

            return obj_lines, mtl_filename

        except FileNotFoundError:
            QMessageBox.critical(self._parent, "Erro de Leitura",
                                 f"Arquivo OBJ não encontrado: {filepath}")
            return None
        except Exception as e:
            QMessageBox.critical(self._parent, "Erro de Leitura OBJ",
                                 f"Não foi possível ler o arquivo '{os.path.basename(filepath)}':\n{e}")
            return None

    def read_mtl_file(self, filepath: str) -> Tuple[Dict[str, QColor], List[str]]:
        """
        Analisa um arquivo de biblioteca de materiais (.mtl).
        Foca principalmente na cor difusa (Kd) para definir a cor do objeto.
        Args:
            filepath: O caminho para o arquivo MTL.
        Returns:
            Uma tupla contendo:
             - Um dicionário mapeando nomes de materiais para objetos QColor.
             - Uma lista de mensagens de aviso geradas durante a análise.
        """
        material_colors: Dict[str, QColor] = {}
        warnings: List[str] = []
        current_mtl_name: Optional[str] = None
        mtl_basename = os.path.basename(filepath) # Para mensagens de erro

        try:
            with open(filepath, "r", encoding='utf-8') as f: # Especifica encoding
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    # Ignora linhas vazias ou comentários
                    if not stripped_line or stripped_line.startswith("#"):
                        continue

                    parts = stripped_line.split()
                    command = parts[0].lower()

                    if command == "newmtl":
                        if len(parts) > 1:
                            current_mtl_name = " ".join(parts[1:]) # Permite nomes com espaços
                            # Define uma cor padrão inicial (cinza) que será sobrescrita por Kd
                            material_colors[current_mtl_name] = QColor(Qt.gray)
                        else:
                            warnings.append(f"MTL '{mtl_basename}' Linha {line_num}: 'newmtl' sem nome de material.")
                            current_mtl_name = None # Reseta o material ativo

                    elif command == "kd":  # Cor difusa (a mais comum para cor base)
                        if current_mtl_name:
                            if len(parts) >= 4: # Precisa de 'Kd' e R, G, B
                                try:
                                    # Converte para float, permitindo valores fora de [0, 1] e clampeando
                                    r = float(parts[1])
                                    g = float(parts[2])
                                    b = float(parts[3])
                                    # Converte para int [0, 255], clampando entre 0.0 e 1.0 antes
                                    q_r = int(max(0.0, min(1.0, r)) * 255)
                                    q_g = int(max(0.0, min(1.0, g)) * 255)
                                    q_b = int(max(0.0, min(1.0, b)) * 255)
                                    # Cria a QColor e armazena no dicionário
                                    material_colors[current_mtl_name] = QColor(q_r, q_g, q_b)
                                except (ValueError):
                                    warnings.append(f"MTL '{mtl_basename}' Linha {line_num}: Ignorando cor 'Kd' com valores não numéricos para '{current_mtl_name}'.")
                            else:
                                warnings.append(f"MTL '{mtl_basename}' Linha {line_num}: Ignorando cor 'Kd' malformada (valores R, G, B ausentes) para '{current_mtl_name}'.")
                        else:
                            warnings.append(f"MTL '{mtl_basename}' Linha {line_num}: Ignorando 'Kd' pois nenhum material ('newmtl') está ativo.")

                    # Poderíamos adicionar suporte a outras propriedades (Ka, Ks, d, map_Kd, etc.) aqui se necessário

        except FileNotFoundError:
            warnings.append(f"Arquivo MTL não encontrado: {filepath}")
        except Exception as e:
            warnings.append(f"Erro inesperado ao ler o arquivo MTL '{mtl_basename}': {e}")

        return material_colors, warnings

    def write_obj_and_mtl(self, base_filepath: str, obj_lines: List[str],
                          mtl_lines: List[str]) -> bool:
        """
        Escreve as linhas OBJ e MTL para os arquivos correspondentes.
        Args:
            base_filepath: O caminho base para os arquivos (ex: 'meudir/meuarquivo').
                           As extensões '.obj' e '.mtl' serão adicionadas.
            obj_lines: Lista de strings para o arquivo .obj.
            mtl_lines: Lista de strings para o arquivo .mtl (pode ser vazia).
        Returns:
            True se ambos os arquivos (ou apenas OBJ se MTL for vazio) foram escritos com sucesso, False caso contrário.
        """
        obj_filepath = base_filepath + ".obj"
        mtl_filepath = base_filepath + ".mtl"
        obj_success = False
        mtl_success = False # Assume sucesso se não houver linhas MTL

        # --- Escreve Arquivo OBJ ---
        try:
            with open(obj_filepath, "w", encoding='utf-8') as f: # Especifica encoding
                for line in obj_lines:
                    f.write(line + "\n") # Adiciona nova linha ao final de cada string
            obj_success = True
        except IOError as e:
            QMessageBox.critical(self._parent, "Erro de Escrita OBJ",
                                 f"Não foi possível escrever no arquivo '{os.path.basename(obj_filepath)}':\n{e}")
        except Exception as e:
            QMessageBox.critical(self._parent, "Erro Inesperado OBJ",
                                 f"Ocorreu um erro inesperado ao salvar em '{os.path.basename(obj_filepath)}':\n{e}")

        if not obj_success:
            return False # Se falhou em escrever o OBJ, não adianta continuar

        # --- Escreve Arquivo MTL (se houver linhas) ---
        if mtl_lines:
            try:
                with open(mtl_filepath, "w", encoding='utf-8') as f: # Especifica encoding
                    for line in mtl_lines:
                        f.write(line + "\n")
                mtl_success = True
            except IOError as e:
                QMessageBox.critical(self._parent, "Erro de Escrita MTL",
                                     f"Não foi possível escrever no arquivo '{os.path.basename(mtl_filepath)}':\n{e}")
            except Exception as e:
                QMessageBox.critical(self._parent, "Erro Inesperado MTL",
                                     f"Ocorreu um erro inesperado ao salvar em '{os.path.basename(mtl_filepath)}':\n{e}")
        else:
            # Se não há linhas MTL para escrever, considera como sucesso
            mtl_success = True

        return obj_success and mtl_success # Retorna True apenas se ambos foram bem-sucedidos
