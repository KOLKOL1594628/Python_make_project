import psutil
import time
import logging
import sys
from typing import Dict, Optional, Tuple

logger = logging.getLogger("SystemMonitor")

try:
    import GPUtil
except ImportError:
    GPUtil = None

try:
    from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU
    NVML_AVAILABLE = True
    nvmlInit()
except (ImportError, FileNotFoundError):
    NVML_AVAILABLE = False

try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False

class SystemMonitor:
    def __init__(self,
                 cpu_threshold: float = 80.0,
                 mem_threshold: float = 90.0,
                 temp_threshold: float = 85.0,
                 check_interval: float = 2.0,
                 pause_on_overload: bool = True,
                 max_pause_seconds: float = 30.0):
        self.cpu_threshold = cpu_threshold
        self.mem_threshold = mem_threshold
        self.temp_threshold = temp_threshold
        self.check_interval = check_interval
        self.pause_on_overload = pause_on_overload
        self.max_pause_seconds = max_pause_seconds
        self.cpu_count = psutil.cpu_count(logical=False) or 1

    def get_system_status(self) -> Dict[str, float]:
        status = {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "mem_percent": psutil.virtual_memory().percent
        }
        temp = self._get_cpu_temperature()
        if temp is not None:
            status["cpu_temp"] = temp
        return status

    def _get_cpu_temperature(self) -> Optional[float]:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current is not None:
                        return entry.current
        if WMI_AVAILABLE:
            try:
                w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                for sensor in w.Sensor():
                    if sensor.SensorType == 'Temperature' and 'CPU' in sensor.Name:
                        return float(sensor.Value)
            except Exception:
                pass
        return None

    def is_safe(self) -> Tuple[bool, str]:
        status = self.get_system_status()
        cpu = status["cpu_percent"]
        mem = status["mem_percent"]
        temp = status.get("cpu_temp", 0.0)

        reasons = []
        if cpu > self.cpu_threshold:
            reasons.append(f"CPU 使用率 {cpu:.1f}% > 阈值 {self.cpu_threshold}%")
        if mem > self.mem_threshold:
            reasons.append(f"内存使用率 {mem:.1f}% > 阈值 {self.mem_threshold}%")
        if temp > self.temp_threshold:
            reasons.append(f"CPU 温度 {temp:.1f}°C > 阈值 {self.temp_threshold}°C")

        if reasons:
            return False, "; ".join(reasons)
        return True, "系统负载正常"

    def safe_execute(self, func, *args, **kwargs):
        start_wait = time.time()
        while True:
            safe, msg = self.is_safe()
            if safe:
                return func(*args, **kwargs)
            logger.warning(f"系统过载: {msg}")
            if not self.pause_on_overload:
                raise RuntimeError(f"系统过载且不允许暂停: {msg}")
            if time.time() - start_wait > self.max_pause_seconds:
                raise RuntimeError(f"等待系统安全超时 ({self.max_pause_seconds}s)，放弃执行")
            time.sleep(self.check_interval)

    def profile_system(self) -> Dict:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "cpu_physical_cores": self.cpu_count,
            "cpu_logical_cores": psutil.cpu_count(logical=True),
            "total_ram_gb": mem.total / (1024**3),
            "available_ram_gb": mem.available / (1024**3),
            "ram_percent": mem.percent,
            "swap_gb": swap.total / (1024**3),
            "os": sys.platform,   # 修正点：使用 sys.platform 替代 psutil.PLATFORM
        }