# --- START OF FILE Bestdori_txt2json.py (FULL FINAL VERSION) ---

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yaml
import threading
import sys

# 安全地导入 tkinterdnd2，如果失败则禁用拖拽功能
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_ENABLED = True
except ImportError:
    DND_ENABLED = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ActionItem:
    """对话动作数据类"""
    type: str = "talk"
    delay: int = 0
    wait: bool = True
    characters: List[int] = None
    name: str = ""
    body: str = ""
    motions: List[str] = None
    voices: List[str] = None
    close: bool = False
    
    def __post_init__(self):
        if self.characters is None:
            self.characters = []
        if self.motions is None:
            self.motions = []
        if self.voices is None:
            self.voices = []


@dataclass
class ConversionResult:
    """转换结果数据类"""
    server: int = 0
    voice: str = ""
    background: Optional[str] = None
    bgm: Optional[str] = None
    actions: List[ActionItem] = None
    
    def __post_init__(self):
        if self.actions is None:
            self.actions = []


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "character_mapping": {
                # Poppin'Party
                "户山香澄": [1], "花园多惠": [2], "牛込里美": [3], "山吹沙绫": [4], "市谷有咲": [5],
                # Afterglow
                "美竹兰": [6], "青叶摩卡": [7], "上原绯玛丽": [8], "宇田川巴": [9], "羽泽鸫": [10],
                # Hello, Happy World!
                "弦卷心": [11], "濑田薰": [12], "北泽育美": [13], "松原花音": [14], "奥泽美咲": [15],
                # Pastel*Palettes
                "丸山彩": [16], "冰川日菜": [17], "白鹭千圣": [18], "大和麻弥": [19], "若宫伊芙": [20],
                # Roselia
                "凑友希那": [21], "冰川纱夜": [22], "今井莉莎": [23], "宇田川亚子": [24], "白金燐子": [25],
                # Morfonica
                "仓田真白": [26], "桐谷透子": [27], "广町七深": [28], "二叶筑紫": [29], "八潮瑠唯": [30],
                # RAISE A SUILEN
                "LAYER": [31], "LOCK": [32], "MASKING": [33], "PAREO": [34], "CHU²": [35],
                # mujica
                "丰川祥子": [1], "若叶睦": [2], "三角初华": [3], "八幡海铃": [4], "祐天寺若麦": [5],
                # MyGo
                "高松灯": [36], "千早爱音": [37], "要乐奈": [38], "长崎素世": [39], "椎名立希": [40]
            },
            "parsing": {
                "max_speaker_name_length": 50,
                "default_narrator_name": " "
            },
            "patterns": {
                "speaker_pattern": r'^([\w\s]+)\s*[：:]\s*(.*)$'
            },
            "quotes": {
                "quote_pairs": {
                    '"': '"', '“': '”', "'": "'", '‘': '’', "「": "」", "『": "』"
                },
                "quote_categories": {
                    "中文引号 “...”": ["“", "”"],
                    "中文单引号 ‘...’": ["‘", "’"],
                    "日文引号 「...」": ["「", "」"],
                    "日文书名号 『...』": ["『", "』"],
                    "英文双引号 \"...\"": ['"', '"'],
                    "英文单引号 '...'": ["'", "'"]
                }
            }
        }
        
        if not self.config_path.exists():
            self._save_config(default_config)
            return default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f) or default_config
                if "quote_categories" not in loaded_config.get("quotes", {}):
                    logger.warning("旧的配置文件缺少'quote_categories'，将从默认配置中添加。")
                    loaded_config["quotes"]["quote_categories"] = default_config["quotes"]["quote_categories"]
                    self._save_config(loaded_config)
                return loaded_config
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return default_config
    
    def _save_config(self, config: Dict[str, Any]):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"配置文件保存失败: {e}")
    
    def get_character_mapping(self) -> Dict[str, List[int]]:
        return self.config.get("character_mapping", {})
    
    def get_parsing_config(self) -> Dict[str, Any]:
        return self.config.get("parsing", {})
    
    def get_patterns(self) -> Dict[str, str]:
        return self.config.get("patterns", {})
    
    def get_quotes_config(self) -> Dict[str, Any]:
        return self.config.get("quotes", {})


class DialogueParser(ABC):
    @abstractmethod
    def parse(self, line: str) -> Optional[Tuple[str, str]]: pass


class SpeakerParser(DialogueParser):
    def __init__(self, pattern: str, max_name_length: int):
        self.pattern = re.compile(pattern, re.UNICODE)
        self.max_name_length = max_name_length
    def parse(self, line: str) -> Optional[Tuple[str, str]]:
        match = self.pattern.match(line.strip())
        if match:
            try:
                speaker_name = match.group(1).strip()
                if len(speaker_name) < self.max_name_length:
                    return speaker_name, match.group(2).strip()
            except IndexError:
                logger.error(f"正则表达式 '{self.pattern.pattern}' 中缺少捕获组。")
                return None
        return None
    
    
class QuoteHandler:
    def remove_quotes(self, text: str, active_quote_pairs: Dict[str, str]) -> str:
        stripped = text.strip()
        if len(stripped) < 2: return text
        first_char = stripped[0]
        expected_closing = active_quote_pairs.get(first_char)
        if expected_closing and stripped[-1] == expected_closing:
            return stripped[1:-1].strip()
        return text    


class TextConverter:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.character_mapping = config_manager.get_character_mapping()
        self.parsing_config = config_manager.get_parsing_config()
        self.patterns = config_manager.get_patterns()
        self._init_parsers()
    
    def _init_parsers(self):
        speaker_pattern = self.patterns.get("speaker_pattern", r'^([\w\s]+)\s*[：:]\s*(.*)$')
        self.parser = SpeakerParser(speaker_pattern, self.parsing_config.get("max_speaker_name_length", 50))
        self.quote_handler = QuoteHandler()

    def convert_text_to_json_format(self, input_text: str, narrator_name: str = None, selected_quote_pairs: Optional[Dict[str, str]] = None) -> str:
        if narrator_name is None: narrator_name = self.parsing_config.get("default_narrator_name", " ")
        if selected_quote_pairs is None: selected_quote_pairs = {} 
        
        actions = []
        current_action_name = narrator_name
        current_action_body_lines = []
        
        def finalize_current_action():
            if current_action_body_lines:
                body = "\n".join(current_action_body_lines).strip()
                finalized_body = self.quote_handler.remove_quotes(body, selected_quote_pairs)
                if finalized_body:
                    actions.append(ActionItem(
                        characters=self.character_mapping.get(current_action_name, []),
                        name=current_action_name,
                        body=finalized_body
                    ))
        
        for line in input_text.split('\n'):
            stripped_line = line.strip()
            if not stripped_line:
                finalize_current_action()
                current_action_name = narrator_name
                current_action_body_lines = []
                continue
            
            parse_result = self.parser.parse(stripped_line)
            if parse_result:
                speaker, content = parse_result
                if speaker != current_action_name and current_action_body_lines:
                    finalize_current_action()
                    current_action_body_lines = []
                current_action_name = speaker
                current_action_body_lines.append(content)
            else:
                current_action_body_lines.append(stripped_line)
        
        finalize_current_action()
        result = ConversionResult(actions=actions)
        return json.dumps(asdict(result), ensure_ascii=False, indent=2)

class ModernConverterGUI:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.converter = TextConverter(self.config_manager)
        self.custom_quote_vars = []
        self.setup_gui()
    
    def setup_gui(self):
        if DND_ENABLED:
            self.root = TkinterDnD.Tk()
            logger.info("tkinterdnd2已加载，拖拽功能已启用。")
        else:
            self.root = tk.Tk()
            logger.warning("tkinterdnd2未安装，拖拽功能不可用。请运行 'pip install tkinterdnd2' 来安装。")
            
        self.root.title("文本转JSON转换器 v2.9 (批量处理)")
        self.root.geometry("800x700")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        ttk.Label(main_frame, text="输入文本文件:").grid(row=0, column=0, sticky="w", pady=5)
        self.input_filepath_var = tk.StringVar()
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        input_frame.columnconfigure(0, weight=1)
        ttk.Entry(input_frame, textvariable=self.input_filepath_var).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(input_frame, text="浏览...", command=self.browse_input_file).grid(row=0, column=1)
        
        ttk.Label(main_frame, text="输出JSON文件:").grid(row=1, column=0, sticky="w", pady=5)
        self.output_filepath_var = tk.StringVar()
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        output_frame.columnconfigure(0, weight=1)
        ttk.Entry(output_frame, textvariable=self.output_filepath_var).grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(output_frame, text="浏览...", command=self.browse_output_file).grid(row=0, column=1)
        
        ttk.Label(main_frame, text="旁白名称:").grid(row=2, column=0, sticky="w", pady=5)
        self.narrator_name_var = tk.StringVar(value=" ")
        ttk.Entry(main_frame, textvariable=self.narrator_name_var).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        self.quote_frame = ttk.LabelFrame(main_frame, text="引号处理选项", padding="10")
        self.quote_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        self.quote_frame.columnconfigure(0, weight=1)

        preset_frame = ttk.Frame(self.quote_frame)
        preset_frame.grid(row=0, column=0, sticky="ew")
        
        self.quote_category_vars = {}
        quotes_config = self.config_manager.get_quotes_config()
        quote_categories = quotes_config.get("quote_categories", {})
        
        self.quote_col_count = 0
        for category_name in quote_categories.keys():
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(preset_frame, text=category_name, variable=var)
            chk.pack(side=tk.LEFT, padx=5, pady=5)
            self.quote_category_vars[category_name] = var
            self.quote_col_count += 1

        ttk.Separator(self.quote_frame, orient='horizontal').grid(row=1, column=0, sticky='ew', pady=10)

        custom_frame = ttk.Frame(self.quote_frame)
        custom_frame.grid(row=2, column=0, sticky="ew")

        ttk.Label(custom_frame, text="添加自定义引号对:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.custom_open_quote_var = tk.StringVar()
        open_entry = ttk.Entry(custom_frame, textvariable=self.custom_open_quote_var, width=5)
        open_entry.pack(side=tk.LEFT, padx=5)

        self.custom_close_quote_var = tk.StringVar()
        close_entry = ttk.Entry(custom_frame, textvariable=self.custom_close_quote_var, width=5)
        close_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(custom_frame, text="➕ 添加", command=self.add_custom_quote).pack(side=tk.LEFT, padx=5)

        self.custom_quotes_display_frame = ttk.Frame(self.quote_frame)
        self.custom_quotes_display_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="开始转换", command=self.start_conversion_threaded).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="批量处理...", command=self.open_batch_converter).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="预览结果", command=self.preview_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="配置管理", command=self.open_config_manager).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="测试引号", command=self.test_quote_processing).pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="就绪 - F1查看帮助 | 支持拖拽文件")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").grid(
            row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5
        )
        
        log_frame = ttk.LabelFrame(main_frame, text="转换日志", padding="5")
        log_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.setup_shortcuts()
        self.enable_drag_drop()

    def open_batch_converter(self):
        batch_window = tk.Toplevel(self.root)
        batch_window.title("批量转换")
        batch_window.geometry("500x250")
        batch_window.transient(self.root)
        batch_window.grab_set()

        frame = ttk.Frame(batch_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="输入文件夹:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.batch_input_dir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.batch_input_dir_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(frame, text="浏览...", command=lambda: self.browse_directory(self.batch_input_dir_var)).grid(row=0, column=2, padx=5)

        ttk.Label(frame, text="输出文件夹:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.batch_output_dir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.batch_output_dir_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(frame, text="浏览...", command=lambda: self.browse_directory(self.batch_output_dir_var)).grid(row=1, column=2, padx=5)

        self.batch_progress_var = tk.DoubleVar()
        self.batch_progress_bar = ttk.Progressbar(frame, variable=self.batch_progress_var, maximum=100)
        self.batch_progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)

        self.batch_status_var = tk.StringVar(value="请选择输入和输出文件夹")
        ttk.Label(frame, textvariable=self.batch_status_var).grid(row=3, column=0, columnspan=3, sticky="w", pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10)
        ttk.Button(btn_frame, text="开始批量转换", command=self.start_batch_conversion_threaded).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="关闭", command=batch_window.destroy).pack(side=tk.LEFT, padx=10)

    def browse_directory(self, var_to_set):
        directory = filedialog.askdirectory(title="请选择一个文件夹")
        if directory:
            var_to_set.set(directory)

    def convert_file(self, input_path: str, output_path: str):
        try:
            narrator_name = self.narrator_name_var.get() or " "
            selected_pairs = self._get_selected_quote_pairs()
            self.log_message(f"开始处理: {Path(input_path).name}")
            with open(input_path, 'r', encoding='utf-8') as f:
                input_text = f.read()
            json_output = self.converter.convert_text_to_json_format(
                input_text, narrator_name, selected_quote_pairs=selected_pairs
            )
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_output)
            self.log_message(f"成功保存到: {Path(output_path).name}", "SUCCESS")
            return True, "Success"
        except Exception as e:
            error_msg = f"处理文件 {Path(input_path).name} 失败: {e}"
            self.log_message(error_msg, "ERROR")
            return False, error_msg
            
    def start_conversion(self):
        input_file = self.input_filepath_var.get()
        output_file = self.output_filepath_var.get()
        
        if not input_file: return messagebox.showerror("错误", "请选择输入文件！")
        if not output_file: return messagebox.showerror("错误", "请选择输出文件！")
        
        self.status_var.set("正在转换...")
        self.progress_bar.grid()
        self.progress_var.set(50)
        
        success, message = self.convert_file(input_file, output_file)
        
        self.progress_var.set(100)
        if success:
            self.status_var.set("转换完成！")
            messagebox.showinfo("成功", "文件转换并保存成功！")
        else:
            self.status_var.set("转换失败！")
            messagebox.showerror("错误", message)
        
        self.progress_var.set(0)
        self.progress_bar.grid_remove()

    def start_batch_conversion_threaded(self):
        thread = threading.Thread(target=self.batch_convert)
        thread.daemon = True
        thread.start()

    def batch_convert(self):
        input_dir = self.batch_input_dir_var.get()
        output_dir = self.batch_output_dir_var.get()

        if not input_dir or not output_dir:
            self.batch_status_var.set("错误: 输入和输出文件夹都必须选择！")
            return

        self.log_message("===== 开始批量处理 =====", "INFO")
        self.log_message(f"输入目录: {input_dir}")
        self.log_message(f"输出目录: {output_dir}")

        try:
            txt_files = list(Path(input_dir).glob("*.txt"))
            if not txt_files:
                self.batch_status_var.set("未在输入目录中找到任何.txt文件。")
                self.log_message("警告: 未找到.txt文件。", "WARNING")
                return

            total_files = len(txt_files)
            self.batch_progress_bar['maximum'] = total_files
            self.batch_progress_var.set(0)
            
            success_count = 0
            fail_count = 0

            for i, txt_file in enumerate(txt_files):
                self.batch_status_var.set(f"正在处理 ({i+1}/{total_files}): {txt_file.name}")
                output_file = Path(output_dir) / f"{txt_file.stem}.json"
                success, _ = self.convert_file(str(txt_file), str(output_file))
                if success: success_count += 1
                else: fail_count += 1
                self.batch_progress_var.set(i + 1)

            final_message = f"批量处理完成！成功: {success_count}, 失败: {fail_count}."
            self.batch_status_var.set(final_message)
            self.log_message(f"===== {final_message} =====", "INFO")
            messagebox.showinfo("批量处理完成", final_message)

        except Exception as e:
            error_msg = f"批量处理过程中发生严重错误: {e}"
            self.log_message(error_msg, "ERROR")
            self.batch_status_var.set(error_msg)
            messagebox.showerror("严重错误", error_msg)

    def enable_drag_drop(self):
        if DND_ENABLED:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_file_drop)

    def on_file_drop(self, event):
        try:
            filepaths = self.root.tk.splitlist(event.data)
            if filepaths:
                dropped_file = filepaths[0]
                self.input_filepath_var.set(dropped_file)
                self.log_message(f"已通过拖拽加载文件: {dropped_file}")
                if dropped_file.lower().endswith(".txt"):
                    output_path = Path(dropped_file).with_suffix(".json")
                    self.output_filepath_var.set(str(output_path))
        except Exception as e:
            self.log_message(f"拖拽文件处理失败: {e}", "ERROR")

    def setup_shortcuts(self):
        self.root.bind('<Control-o>', lambda e: self.browse_input_file())
        self.root.bind('<Control-s>', lambda e: self.browse_output_file())
        self.root.bind('<F5>', lambda e: self.start_conversion_threaded())
        self.root.bind('<F1>', lambda e: self.show_help())
    
    def show_help(self):
        help_title = "帮助 / 快捷键"
        help_message = """
文本转JSON转换器 v2.9

功能简介:
本工具用于将特定格式的对话文本转换为JSON文件，
支持批量处理、拖拽文件、多种引号移除和自定义角色配置。

快捷键列表:
  - Ctrl + O:   打开文件选择框，选择输入文件。
  - Ctrl + S:   打开文件保存框，指定输出文件。
  - F5:         开始转换当前指定的文件。
  - F1:         显示此帮助信息。
"""
        messagebox.showinfo(help_title, help_message)

    def add_custom_quote(self):
        open_char = self.custom_open_quote_var.get(); close_char = self.custom_close_quote_var.get()
        if not open_char or not close_char: return messagebox.showerror("错误", "起始和结束符号都不能为空！")
        var = tk.BooleanVar(value=True); self.custom_quote_vars.append((var, open_char, close_char))
        category_name = f"{open_char}...{close_char}"
        chk = ttk.Checkbutton(self.custom_quotes_display_frame, text=category_name, variable=var)
        chk.pack(side=tk.LEFT, padx=5, pady=5)
        self.custom_open_quote_var.set(""); self.custom_close_quote_var.set("")

    def _get_selected_quote_pairs(self) -> Dict[str, str]:
        selected_pairs = {}
        quotes_config = self.config_manager.get_quotes_config()
        quote_categories = quotes_config.get("quote_categories", {})
        for category_name, var in self.quote_category_vars.items():
            if var.get():
                quote_chars = quote_categories.get(category_name)
                if quote_chars and len(quote_chars) == 2:
                    selected_pairs[quote_chars[0]] = quote_chars[1]
        for var, open_char, close_char in self.custom_quote_vars:
            if var.get(): selected_pairs[open_char] = close_char
        return selected_pairs
    
    def browse_input_file(self):
        filename = filedialog.askopenfilename(title="选择输入文本文件", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if filename: 
            self.input_filepath_var.set(filename)
            if filename.lower().endswith(".txt"):
                output_path = Path(filename).with_suffix(".json")
                self.output_filepath_var.set(str(output_path))
    
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(title="保存JSON文件", defaultextension=".json", filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")])
        if filename: self.output_filepath_var.set(filename)
    
    def log_message(self, message: str, level: str = "INFO"):
        tag = level.upper()
        # 为不同级别的日志添加颜色标签
        if tag == "SUCCESS":
            self.log_text.tag_config("SUCCESS", foreground="green")
        elif tag == "ERROR":
            self.log_text.tag_config("ERROR", foreground="red")
        elif tag == "WARNING":
            self.log_text.tag_config("WARNING", foreground="orange")
        elif tag == "HEADER":
            self.log_text.tag_config("HEADER", font=("TkDefaultFont", 10, "bold"))
        
        self.log_text.insert(tk.END, f"[{level}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def test_quote_processing(self):
        test_window = tk.Toplevel(self.root); test_window.title("引号处理测试"); test_window.geometry("500x400")
        ttk.Label(test_window, text="输入测试文本:").pack(pady=5)
        input_text = tk.Text(test_window, height=5, wrap=tk.WORD); input_text.pack(fill=tk.X, padx=10, pady=5)
        test_samples = ['「这是日文引号」', '『这是日文书名号』', '“这是中文双引号”', '‘这是中文单引号’', '角色名:「带名字的引号」', '兰: “分かった。\nじゃあ、始めよっか”']
        input_text.insert(tk.END, "\n\n".join(test_samples))
        def process_test():
            content = input_text.get(1.0, tk.END)
            selected_pairs = self._get_selected_quote_pairs()
            json_output = self.converter.convert_text_to_json_format(content, self.narrator_name_var.get(), selected_quote_pairs=selected_pairs)
            result_text.config(state=tk.NORMAL); result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "--- 转换结果 (JSON) ---\n" + json_output); result_text.config(state=tk.DISABLED)
        ttk.Button(test_window, text="处理测试", command=process_test).pack(pady=5)
        ttk.Label(test_window, text="处理结果:").pack(pady=5)
        result_text = tk.Text(test_window, height=10, wrap=tk.WORD); result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5); result_text.config(state=tk.DISABLED)
    
    def start_conversion_threaded(self):
        thread = threading.Thread(target=self.start_conversion); thread.daemon = True; thread.start()
    
    def preview_result(self):
        input_file = self.input_filepath_var.get(); narrator_name = self.narrator_name_var.get() or " "
        if not input_file: return messagebox.showerror("错误", "请先选择输入文件！")
        try:
            selected_pairs = self._get_selected_quote_pairs()
            with open(input_file, 'r', encoding='utf-8') as f: input_text = f.read()
            preview_text = input_text[:500]
            json_output = self.converter.convert_text_to_json_format(preview_text, narrator_name, selected_quote_pairs=selected_pairs)
            preview_window = tk.Toplevel(self.root); preview_window.title("转换预览"); preview_window.geometry("600x400")
            text_widget = tk.Text(preview_window, wrap=tk.WORD)
            scrollbar = ttk.Scrollbar(preview_window, orient=tk.VERTICAL, command=text_widget.yview); text_widget.configure(yscrollcommand=scrollbar.set)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget.insert(tk.END, json_output); text_widget.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("错误", f"预览失败: {str(e)}")
    
    def open_config_manager(self):
        config_window = tk.Toplevel(self.root); config_window.title("配置管理"); config_window.geometry("500x400")
        ttk.Label(config_window, text="角色映射配置 (格式: 角色名=ID,ID...)").pack(pady=5)
        config_text = tk.Text(config_window, wrap=tk.WORD); config_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        current_mapping = self.config_manager.get_character_mapping(); config_content = ""
        for name, ids in current_mapping.items(): config_content += f"{name}={','.join(map(str, ids))}\n"
        config_text.insert(tk.END, config_content)
        def save_config():
            try:
                content = config_text.get(1.0, tk.END).strip(); new_mapping = {}
                for line in content.split('\n'):
                    if '=' in line:
                        name, ids_str = line.split('=', 1); ids = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()]
                        new_mapping[name.strip()] = ids
                self.config_manager.config['character_mapping'] = new_mapping
                self.config_manager._save_config(self.config_manager.config)
                self.converter.character_mapping = new_mapping
                messagebox.showinfo("成功", "配置保存成功！"); config_window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"配置保存失败: {str(e)}")
        ttk.Button(config_window, text="保存配置", command=save_config).pack(pady=5)
    
    def run(self):
        self.root.mainloop()


def main():
    try:
        app = ModernConverterGUI()
        app.run()
    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        if 'tk' in str(e).lower():
            print("错误：GUI环境初始化失败。请确保您正在图形用户界面环境中运行此脚本。", file=sys.stderr)
        else:
            try:
                root = tk.Tk(); root.withdraw(); messagebox.showerror("严重错误", f"应用程序启动失败: {str(e)}")
            except: pass


if __name__ == "__main__":
    main()