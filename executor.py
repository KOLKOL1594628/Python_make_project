import subprocess
import os
import sys
import platform

LANGUAGE_CONFIG = {
    "python": {
        "ext": "py",
        "compile_cmd": None,
        "run_cmd": ["{python}", "{file}"]
    },
    "c": {
        "ext": "c",
        "compile_cmd": ["gcc", "{file}", "-o", "{exe}"],
        "run_cmd": ["{exe}"]
    },
    "cpp": {
        "ext": "cpp",
        "compile_cmd": ["g++", "{file}", "-o", "{exe}"],
        "run_cmd": ["{exe}"]
    },
    "java": {
        "ext": "java",
        "compile_cmd": ["javac", "{file}"],
        "run_cmd": ["java", "{basename}"]
    },
}

class UniversalRunner:
    def __init__(self, output_dir: str, language: str = "python"):
        self.language = language.lower()
        self.config = LANGUAGE_CONFIG.get(self.language)
        if not self.config:
            raise ValueError(f"不支持的语言: {language}。目前支持: {list(LANGUAGE_CONFIG.keys())}")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def save_code(self, code: str, filename: str = "main") -> str:
        ext = self.config["ext"]
        file_path = os.path.join(self.output_dir, f"{filename}.{ext}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return file_path

    def _fill_cmd(self, template: list, file_path: str) -> list:
        basename = os.path.splitext(os.path.basename(file_path))[0]
        exe_path = os.path.join(
            self.output_dir,
            f"{basename}.exe" if platform.system() == "Windows" else basename
        )
        replacements = {
            "{python}": sys.executable,
            "{file}": file_path,
            "{exe}": exe_path,
            "{basename}": basename,
        }
        return [replacements.get(part, part) for part in template]

    def run(self, file_path: str, timeout: int = 10) -> tuple:
        # 编译阶段
        compile_cmd = self.config.get("compile_cmd")
        if compile_cmd is not None:
            cmd = self._fill_cmd(compile_cmd, file_path)
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if proc.returncode != 0:
                    return "", f"[编译失败]\n{proc.stderr}", proc.returncode
            except subprocess.TimeoutExpired:
                return "", "编译超时", -1
            except FileNotFoundError:
                return "", f"编译器未找到，请安装 {cmd[0]} 并加入 PATH", -1

        # 运行阶段
        run_cmd = self._fill_cmd(self.config["run_cmd"], file_path)
        proc = None
        try:
            proc = subprocess.Popen(
                run_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.output_dir
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return stdout, stderr, proc.returncode
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
                stdout, stderr = proc.communicate()
            return "", "运行超时（已强制终止）", -1
        except Exception as e:
            if proc:
                proc.kill()
            return "", f"运行异常: {e}", -1