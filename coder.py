from llama_cpp import Llama
import os
import re
import ast
import psutil
import time

class CodeGenerator:
    def __init__(self, language: str = "python",
                 model_path: str = "./DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf",
                 max_cpu_threads: int = None,
                 n_ctx: int = 4096):
        self.language = language
        self.model_path = model_path
        self.n_ctx = n_ctx

        if max_cpu_threads is None:
            physical_cores = psutil.cpu_count(logical=False) or 2
            max_cpu_threads = max(1, physical_cores // 2)
        self.max_cpu_threads = max_cpu_threads
        print(f"[Coder] 限制推理线程数: {self.max_cpu_threads}")

        self._set_cpu_affinity()

        print(f"[Coder] 加载 DeepSeek R1 模型: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=self.n_ctx,
            n_threads=self.max_cpu_threads,   # ✅ 初始化时设置
            n_gpu_layers=0,
            verbose=False,
        )
        print("[Coder] 模型加载完成")

    def _set_cpu_affinity(self, cores=None):
        try:
            p = psutil.Process()
            if cores is None:
                total_cores = psutil.cpu_count(logical=False) or 1
                cores = list(range(0, total_cores, 2))
                if not cores:
                    cores = [0]
            p.cpu_affinity(cores)
            print(f"[Coder] CPU 亲和性设置为: {p.cpu_affinity()}")
        except Exception as e:
            print(f"[Coder] 设置 CPU 亲和性失败（不影响运行）: {e}")

    def _throttle_cpu(self, limit_percent=60):
        process = psutil.Process()
        cpu_usage_total = process.cpu_percent(interval=0.3)
        cpu_count = psutil.cpu_count()
        normalized = cpu_usage_total / cpu_count if cpu_count else cpu_usage_total
        if normalized > limit_percent:
            sleep_time = min(0.3, (normalized - limit_percent) / 100 * 0.3)
            time.sleep(sleep_time)

    def _build_prompt(self, task_description: str, error_context: str = "") -> str:
        sys_msg = (
            "你是一个代码生成专家。你的回答必须仅包含可直接运行的代码，不要有任何解释、注释（除代码自身必需外），"
            "不要输出 Markdown 代码块标记（如 ```python），不要输出任何前后的文字，不要输出思考过程（如 <think>）。"
            "直接输出代码，从第一行代码开始。"
        )
        if error_context:
            user_msg = f"""请修正以下 {self.language} 代码的错误。

原始任务: {task_description}
错误反馈:
{error_context}

请直接输出修正后的完整代码，不要附加任何说明。"""
        else:
            user_msg = f"""请生成一个 {self.language} 程序，实现以下功能:
{task_description}

要求:
- 程序运行后自动退出，无死循环或等待输入。
- 只输出代码，无解释。
- 确保语法正确，导入完整。

代码:"""
        return (f"<|im_start|>system\n{sys_msg}<|im_end|>\n"
                f"<|im_start|>user\n{user_msg}<|im_end|>\n"
                f"<|im_start|>assistant\n")

    def _clean_code(self, raw_text: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)
        cleaned = re.sub(r"```[a-zA-Z]*\n?(.*?)```", r"\1", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"^(代码|Code):\s*", "", cleaned, flags=re.IGNORECASE)
        lines = cleaned.splitlines()
        code_lines = []
        capture = False
        for line in lines:
            if not capture and line.strip() == "":
                continue
            capture = True
            code_lines.append(line)
        return "\n".join(code_lines).strip()

    def _is_valid_python(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def generate_code(self, task_description: str, error_context: str = "") -> str:
        max_retries = 2
        last_code = ""
        for attempt in range(max_retries):
            self._throttle_cpu(limit_percent=65)
            prompt = self._build_prompt(task_description, error_context)
            output = self.llm(
                prompt,
                max_tokens=1200,
                temperature=0.1,
                top_p=0.9,
                stop=["<|im_end|>", "<|im_start|>", "\n\n\n"],
                echo=False,
                # ✅ 注意：此处不能传 n_threads，已在初始化时设置
            )
            raw = output["choices"][0]["text"].strip()
            code = self._clean_code(raw)
            last_code = code

            if not code:
                print(f"[Coder] 清洗后代码为空，重试 {attempt+1}/{max_retries}")
                continue

            if self.language == "python" and not self._is_valid_python(code):
                print(f"[Coder] 生成的 Python 代码语法错误，重试 {attempt+1}/{max_retries}")
                continue

            return code

        print("[Coder] 多次重试后仍无法得到有效代码，返回最后输出（可能包含错误）")
        return last_code if last_code else "# 代码生成失败，请检查模型输出"