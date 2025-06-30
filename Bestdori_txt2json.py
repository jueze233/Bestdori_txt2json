# --- START OF FILE Bestdori_txt2json.py (MODIFIED) ---

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

# (日志、数据类、ConfigManager、解析器、QuoteHandler、TextConverter等核心逻辑部分... 无需任何修改)
# --- [此处省略未修改的核心逻辑代码，与您提供的版本完全相同] ---

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
                "户山香澄": [1], "花园多惠": [2], "牛込里美": [3], "山吹沙绫": [4], "市谷有咲": [5],
                "美竹兰": [6], "青叶摩卡": [7], "上原绯玛丽": [8], "宇田川巴": [9], "羽泽鸫": [10],
                "弦卷心": [11], "濑田薰": [12], "北泽育美": [13], "松原花音": [14], "奥泽美咲": [15],
                "丸山彩": [16], "冰川日菜": [17], "白鹭千圣": [18], "大和麻弥": [19], "若宫伊芙": [20],
                "凑友希那": [21], "冰川纱夜": [22], "今井莉莎": [23], "宇田川亚子": [24], "白金燐子": [25],
                "仓田真白": [26], "桐谷透子": [27], "广町七深": [28], "二叶筑紫": [29], "八潮瑠唯": [30],
                "LAYER": [31], "LOCK": [32], "MASKING": [33], "PAREO": [34], "CHU²": [35],
                "丰川祥子": [1], "若叶睦": [2], "三角初华": [3], "八幡海铃": [4], "祐天寺若麦": [5],
                "高松灯": [36], "千早爱音": [37], "要乐奈": [38], "长崎素世": [39], "椎名立希": [40]
            },
            "parsing": { "max_speaker_name_length": 50, "default_narrator_name": " " },
            "patterns": { "speaker_pattern": r'^([\w\s]+)\s*[：:]\s*(.*)$' },
            "quotes": {
                "quote_pairs": {'"': '"', '“': '”', "'": "'", '‘': '’', "「": "」", "『": "』"},
                "quote_categories": {
                    "中文引号 “...”": ["“", "”"], "中文单引号 ‘...’": ["‘", "’"],
                    "日文引号 「...」": ["「", "」"], "日文书名号 『...』": ["『", "』"],
                    "英文双引号 \"...\"": ['"', '"'], "英文单引号 '...'": ["'", "'"]
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
                    loaded_config["quotes"] = default_config["quotes"]
                    self._save_config(loaded_config)
                return loaded_config
        except Exception as e:
            logger.warning(f"配置文件加载失败: {e}"); return default_config
    
    def _save_config(self, config: Dict[str, Any]):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e: logger.error(f"配置文件保存失败: {e}")
    
    def get_character_mapping(self) -> Dict[str, List[int]]: return self.config.get("character_mapping", {})
    def get_parsing_config(self) -> Dict[str, Any]: return self.config.get("parsing", {})
    def get_patterns(self) -> Dict[str, str]: return self.config.get("patterns", {})
    def get_quotes_config(self) -> Dict[str, Any]: return self.config.get("quotes", {})


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
    """现代化的GUI界面"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.converter = TextConverter(self.config_manager)
        # --- 修改1：初始化用于存储自定义引号信息的列表 ---
        self.custom_quote_vars = []
        self.setup_gui()
    
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("文本转JSON转换器 v2.6 (自定义引号)")
        self.root.geometry("800x700") # 稍微增加高度以容纳新控件
        
        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # --- (输入/输出/旁白名称部分无变化) ---
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
        
        # --- 修改2：调整UI布局，添加自定义引号控件 ---
        self.quote_frame = ttk.LabelFrame(main_frame, text="引号处理选项", padding="10")
        self.quote_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        self.quote_frame.columnconfigure(0, weight=1) # 让内部网格可伸缩

        # 预设引号部分
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

        # 分隔线
        ttk.Separator(self.quote_frame, orient='horizontal').grid(row=1, column=0, sticky='ew', pady=10)

        # 自定义引号部分
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

        # 动态添加的自定义引号将显示在这里
        self.custom_quotes_display_frame = ttk.Frame(self.quote_frame)
        self.custom_quotes_display_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        
        # --- (进度条、按钮、状态栏、日志等部分无变化) ---
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="开始转换", command=self.start_conversion_threaded).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="预览结果", command=self.preview_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="配置管理", command=self.open_config_manager).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="测试引号", command=self.test_quote_processing).pack(side=tk.LEFT, padx=5)
        self.status_var = tk.StringVar(value="就绪 - 支持自定义引号")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        log_frame = ttk.LabelFrame(main_frame, text="转换日志", padding="5")
        log_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1); log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(7, weight=1)
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    # --- 修改3：实现动态添加自定义引号的函数 ---
    def add_custom_quote(self):
        open_char = self.custom_open_quote_var.get()
        close_char = self.custom_close_quote_var.get()

        if not open_char or not close_char:
            messagebox.showerror("错误", "起始和结束符号都不能为空！")
            return
        
        # 创建并存储新的引号变量和字符
        var = tk.BooleanVar(value=True)
        self.custom_quote_vars.append((var, open_char, close_char))
        
        # 在界面上创建新的复选框
        category_name = f"{open_char}...{close_char}"
        chk = ttk.Checkbutton(self.custom_quotes_display_frame, text=category_name, variable=var)
        # 使用 pack 让它们自动排列
        chk.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 清空输入框
        self.custom_open_quote_var.set("")
        self.custom_close_quote_var.set("")

    # --- 修改4：修改 _get_selected_quote_pairs 以包含自定义引号 ---
    def _get_selected_quote_pairs(self) -> Dict[str, str]:
        selected_pairs = {}
        quotes_config = self.config_manager.get_quotes_config()
        quote_categories = quotes_config.get("quote_categories", {})

        # 1. 收集预设的引号
        for category_name, var in self.quote_category_vars.items():
            if var.get():
                quote_chars = quote_categories.get(category_name)
                if quote_chars and len(quote_chars) == 2:
                    selected_pairs[quote_chars[0]] = quote_chars[1]
        
        # 2. 收集自定义的引号
        for var, open_char, close_char in self.custom_quote_vars:
            if var.get():
                selected_pairs[open_char] = close_char
                
        return selected_pairs
    
    # --- (其余所有方法，如 start_conversion, preview_result 等，都无需修改) ---
    def browse_input_file(self):
        filename = filedialog.askopenfilename(title="选择输入文本文件", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if filename: self.input_filepath_var.set(filename)
    
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(title="保存JSON文件", defaultextension=".json", filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")])
        if filename: self.output_filepath_var.set(filename)
    
    def log_message(self, message: str, level: str = "INFO"):
        self.log_text.insert(tk.END, f"[{level}] {message}\n"); self.log_text.see(tk.END); self.root.update_idletasks()
    
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
    
    def start_conversion(self):
        input_file = self.input_filepath_var.get(); output_file = self.output_filepath_var.get(); narrator_name = self.narrator_name_var.get() or " "
        selected_pairs = self._get_selected_quote_pairs()
        if not input_file: return messagebox.showerror("错误", "请选择输入文件！")
        if not output_file: return messagebox.showerror("错误", "请选择输出文件！")
        try:
            self.status_var.set("正在读取文件..."); self.progress_var.set(10); self.log_message("开始读取输入文件...")
            with open(input_file, 'r', encoding='utf-8') as f: input_text = f.read()
            self.progress_var.set(30); self.log_message(f"成功读取文件，共{len(input_text)}个字符")
            self.status_var.set("正在转换文本..."); self.progress_var.set(50); self.log_message(f"开始转换文本... (根据UI选项移除引号)")
            json_output = self.converter.convert_text_to_json_format(input_text, narrator_name, selected_quote_pairs=selected_pairs)
            self.progress_var.set(80); self.log_message("文本转换完成")
            self.status_var.set("正在保存文件..."); 
            with open(output_file, 'w', encoding='utf-8') as f: f.write(json_output)
            self.progress_var.set(100); self.status_var.set("转换完成！"); self.log_message("文件保存成功！")
            messagebox.showinfo("成功", "文件转换并保存成功！")
        except FileNotFoundError:
            error_msg = f"找不到输入文件: {input_file}"; self.log_message(error_msg, "ERROR"); messagebox.showerror("错误", error_msg)
        except Exception as e:
            error_msg = f"转换过程中发生错误: {str(e)}"; self.log_message(error_msg, "ERROR"); messagebox.showerror("错误", error_msg)
        finally:
            self.progress_var.set(0)
    
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

# (main 函数和 if __name__ == "__main__": 部分无变化)
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