from coder import CodeGenerator
from executor import UniversalRunner
from verifier import ResultVerifier
from system_monitor import SystemMonitor
import time

class DebugAgent:
    def __init__(self, task: str, output_dir: str, language: str = "python",
                 expected: str = "", model_path: str = "./DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf",
                 max_cpu_threads: int = None):
        self.task = task
        self.language = language
        self.expected = expected
        self.model_path = model_path
        self.max_cpu_threads = max_cpu_threads
        self.runner = UniversalRunner(output_dir, language)
        self.verifier = ResultVerifier(expected)
        self.coder = CodeGenerator(language, model_path, max_cpu_threads=max_cpu_threads)
        self.max_attempts = 5
        self.current_code = ""
        self.last_error = ""
        # 初始化系统监控（阈值可自行调整）
        self.monitor = SystemMonitor(cpu_threshold=80, mem_threshold=99, temp_threshold=85)
        sys_info = self.monitor.profile_system()
        print(f"💻 系统检测: CPU {sys_info['cpu_logical_cores']}核, "
              f"内存 {sys_info['total_ram_gb']:.1f}GB, "
              f"可用内存 {sys_info['available_ram_gb']:.1f}GB")

    def _generate_code_safe(self, task_desc, error_ctx):
        """在安全负载下生成代码（自动等待系统资源充足）"""
        return self.monitor.safe_execute(self.coder.generate_code, task_desc, error_ctx)

    def run(self):
        print(f"\n🎯 任务：{self.task}")
        print(f"📁 输出目录：{self.runner.output_dir}")
        print(f"🔧 语言：{self.language}")
        print(f"🧠 模型：{self.model_path}")

        # 初始等待系统安全
        safe, msg = self.monitor.is_safe()
        if not safe:
            print(f"⚠️ 系统过载: {msg}")
            if self.monitor.pause_on_overload:
                print("等待系统恢复...")
                while not self.monitor.is_safe()[0]:
                    time.sleep(2)
                print("系统已恢复安全状态")
            else:
                print("终止运行")
                return

        for attempt in range(1, self.max_attempts + 1):
            print(f"\n{'='*20} 第 {attempt} 次尝试 {'='*20}")

            try:
                if attempt == 1:
                    print("🧠 生成初始代码...")
                    self.current_code = self._generate_code_safe(self.task, "")
                else:
                    print("🔧 根据错误修正代码...")
                    self.current_code = self._generate_code_safe(self.task, self.last_error)
            except RuntimeError as e:
                print(f"❌ 生成代码时因系统过载跳过: {e}")
                continue

            if not self.current_code or not self.current_code.strip():
                print("❌ 生成的代码为空，跳过本次尝试")
                continue

            file_path = self.runner.save_code(self.current_code)
            print(f"💾 代码已保存：{file_path}")

            # 代码预览
            lines = self.current_code.splitlines()
            print("━━━━━━ 代码预览（前10行）━━━━━━")
            for line in lines[:10]:
                print(f"  {line}")
            if len(lines) > 10:
                print("  ...")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━")

            print("⚡ 执行代码...")
            stdout, stderr, retcode = self.runner.run(file_path)

            print(f"📤 标准输出：\n{stdout}")
            if stderr:
                print(f"⚠️ 错误输出：\n{stderr}")

            if self.verifier.check(stdout, stderr):
                print("✅ 程序运行成功，结果符合预期！")
                time.sleep(10)
                break
            else:
                print("❌ 结果不符合预期，准备修正...")
                self.last_error = f"标准输出：\n{stdout}\n\n错误输出：\n{stderr}"
                if self.expected:
                    self.last_error += f"\n\n期望输出中应包含：{self.expected}"
        else:
            print("\n💢 达到最大尝试次数，仍未能生成正确代码。")
            print("📄 最后一次生成的代码：")
            print(self.current_code)