# graphics_editor/io_handler.py
import os
from typing import List, Optional, Dict, Tuple

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QStandardPaths


class IOHandler:
    """
    Gerencia diálogos de arquivo e leitura/escrita de arquivos OBJ e MTL.
    """

    def __init__(self, parent_widget: QWidget):
        """Inicializa com o widget pai para diálogos."""
        self._parent = parent_widget
        # Começa no diretório de documentos ou home do usuário
        self._last_dir: str = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation
        ) or os.path.expanduser("~")

    def prompt_load_obj(self) -> Optional[str]:
        """Abre diálogo para selecionar um arquivo OBJ."""
        filepath, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Abrir Arquivo OBJ",
            self._last_dir,
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath)  # Atualiza último diretório
            return filepath
        return None

    def prompt_save_obj(
        self, default_filename: str = "sem_titulo.obj"
    ) -> Optional[str]:
        """
        Abre diálogo para selecionar um caminho BASE para salvar OBJ/MTL.
        Retorna o caminho base (sem extensão garantida), ou None se cancelado.
        """
        # Garante nome padrão com .obj
        if default_filename and not default_filename.lower().endswith(".obj"):
            default_filename += ".obj"

        full_default_path = os.path.join(self._last_dir, default_filename)

        filepath, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Salvar Como Arquivo OBJ",
            full_default_path,
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
            options=QFileDialog.Options(),  # Usa confirmação nativa do OS
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath)
            # Retorna o caminho completo escolhido pelo usuário
            # A extensão será gerenciada por quem chama (write_obj_and_mtl)
            base_path, _ = os.path.splitext(filepath)
            if not base_path:  # Caso digite só ".obj"
                QMessageBox.warning(
                    self._parent, "Nome Inválido", "Nome de arquivo inválido."
                )
                return None
            return base_path  # Retorna caminho sem extensão
        return None

    def read_obj_lines(
        self, filepath: str
    ) -> Optional[Tuple[List[str], Optional[str]]]:
        """
        Lê linhas relevantes de um arquivo OBJ e encontra a referência mtllib.

        Returns:
            Tupla: (linhas_obj, nome_mtl) ou None em caso de erro.
        """
        obj_lines: List[str] = []
        mtl_filename: Optional[str] = None
        encodings_to_try = ["utf-8", "iso-8859-1", "cp1252", "latin-1"]
        content = None

        try:
            for enc in encodings_to_try:
                try:
                    with open(filepath, "r", encoding=enc) as f:
                        content = f.readlines()
                    break  # Sucesso na leitura
                except UnicodeDecodeError:
                    continue  # Tenta próximo encoding
                except Exception as e_inner:
                    raise e_inner  # Outro erro (permissão, etc)

            if content is None:
                raise IOError(
                    f"Não foi possível decodificar usando: {', '.join(encodings_to_try)}."
                )

            # Processa linhas lidas
            for line in content:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    continue

                obj_lines.append(stripped_line)
                parts = stripped_line.split()
                # Procura 'mtllib' (case-insensitive), pega apenas a primeira ocorrência
                if (
                    len(parts) > 1
                    and parts[0].lower() == "mtllib"
                    and mtl_filename is None
                ):
                    mtl_filename = " ".join(parts[1:])

            return obj_lines, mtl_filename

        except FileNotFoundError:
            QMessageBox.critical(
                self._parent, "Erro", f"Arquivo OBJ não encontrado:\n{filepath}"
            )
            return None
        except IOError as e:
            QMessageBox.critical(
                self._parent,
                "Erro de Leitura OBJ",
                f"Não foi possível ler/decodificar:\n'{os.path.basename(filepath)}'\n{e}",
            )
            return None
        except Exception as e:
            QMessageBox.critical(
                self._parent,
                "Erro Inesperado OBJ",
                f"Erro ao ler '{os.path.basename(filepath)}':\n{e}",
            )
            return None

    def read_mtl_file(self, filepath: str) -> Tuple[Dict[str, QColor], List[str]]:
        """
        Analisa um arquivo MTL, focando em 'newmtl' e 'Kd' (cor difusa).

        Returns:
            Tupla: (dicionario_cores, lista_avisos)
        """
        material_colors: Dict[str, QColor] = {}
        warnings: List[str] = []
        current_mtl_name: Optional[str] = None
        mtl_basename = os.path.basename(filepath)
        encodings_to_try = ["utf-8", "iso-8859-1", "cp1252", "latin-1"]
        content = None

        try:
            for enc in encodings_to_try:
                try:
                    with open(filepath, "r", encoding=enc) as f:
                        content = f.readlines()
                        break
                except UnicodeDecodeError:
                    continue
                except Exception as e_inner:
                    raise e_inner

            if content is None:
                raise IOError(
                    f"Não foi possível decodificar usando: {', '.join(encodings_to_try)}."
                )

            # Processa linhas MTL
            for line_num, line in enumerate(content, 1):
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    continue

                parts = stripped_line.split()
                command = parts[0].lower()

                if command == "newmtl":
                    if len(parts) > 1:
                        current_mtl_name = " ".join(parts[1:])
                        # Define cor padrão (cinza) que pode ser sobrescrita por Kd
                        if current_mtl_name not in material_colors:
                            material_colors[current_mtl_name] = QColor(Qt.gray)
                        # else: # Material redefinido, sobrescreve silenciosamente
                        #     warnings.append(f"MTL Linha {line_num}: Material '{current_mtl_name}' redefinido.")
                    else:
                        warnings.append(f"MTL Linha {line_num}: 'newmtl' sem nome.")
                        current_mtl_name = None

                # Cor Difusa (Kd R G B) - principal cor
                elif command == "kd" and current_mtl_name:
                    if len(parts) >= 4:
                        try:
                            # Converte para float [0,1] e depois int [0,255]
                            r = max(0.0, min(1.0, float(parts[1])))
                            g = max(0.0, min(1.0, float(parts[2])))
                            b = max(0.0, min(1.0, float(parts[3])))
                            q_r, q_g, q_b = int(r * 255), int(g * 255), int(b * 255)
                            material_colors[current_mtl_name] = QColor(q_r, q_g, q_b)
                        except ValueError:
                            warnings.append(
                                f"MTL Linha {line_num}: Valores Kd inválidos para '{current_mtl_name}'."
                            )
                    else:
                        warnings.append(
                            f"MTL Linha {line_num}: Kd malformado para '{current_mtl_name}'."
                        )

                # Ignora outros comandos MTL (Ka, Ks, Ns, d, Tr, illum, map_*)

        except FileNotFoundError:
            warnings.append(
                f"Arquivo MTL '{mtl_basename}' não encontrado em '{filepath}'."
            )
        except IOError as e:
            warnings.append(f"Erro de leitura/decodificação MTL '{mtl_basename}': {e}")
        except Exception as e:
            warnings.append(f"Erro inesperado ao ler MTL '{mtl_basename}': {e}")

        return material_colors, warnings

    def write_obj_and_mtl(
        self, base_filepath: str, obj_lines: List[str], mtl_lines: Optional[List[str]]
    ) -> bool:
        """
        Escreve as linhas OBJ e (se houver) MTL nos arquivos correspondentes.

        Args:
            base_filepath: Caminho base (ex: 'meudir/arquivo'). Extensões serão adicionadas.
            obj_lines: Linhas do arquivo OBJ.
            mtl_lines: Linhas do arquivo MTL (ou None/vazio).

        Returns:
            True se sucesso, False se erro.
        """
        obj_filepath = base_filepath + ".obj"
        mtl_filepath = base_filepath + ".mtl"
        obj_success = False
        mtl_success = True  # Assume sucesso se não houver MTL para salvar

        # --- Escreve OBJ ---
        try:
            with open(obj_filepath, "w", encoding="utf-8") as f:
                f.write(
                    "\n".join(obj_lines) + "\n"
                )  # Junta linhas e adiciona uma no final
            obj_success = True
        except IOError as e:
            QMessageBox.critical(
                self._parent,
                "Erro de Escrita OBJ",
                f"Não foi possível escrever:\n'{os.path.basename(obj_filepath)}'\n{e}",
            )
            return False  # Falha crítica
        except Exception as e:
            QMessageBox.critical(
                self._parent,
                "Erro Inesperado OBJ",
                f"Erro ao salvar OBJ:\n'{os.path.basename(obj_filepath)}'\n{e}",
            )
            return False

        # --- Escreve MTL (se necessário) ---
        if mtl_lines:
            mtl_success = False  # Reseta, pois agora precisa salvar
            try:
                with open(mtl_filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(mtl_lines) + "\n")
                mtl_success = True
            except IOError as e:
                QMessageBox.critical(
                    self._parent,
                    "Erro de Escrita MTL",
                    f"Não foi possível escrever MTL:\n'{os.path.basename(mtl_filepath)}'\n{e}",
                )
                # OBJ pode ter sido salvo, mas o MTL falhou. Considera falha total.
            except Exception as e:
                QMessageBox.critical(
                    self._parent,
                    "Erro Inesperado MTL",
                    f"Erro ao salvar MTL:\n'{os.path.basename(mtl_filepath)}'\n{e}",
                )

        # Retorna True apenas se ambos (ou só OBJ se MTL não era necessário) foram salvos
        return obj_success and mtl_success
