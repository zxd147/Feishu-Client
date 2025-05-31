import GPUtil
import psutil


def get_system_status():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    memory_total = f"{memory_info.total / (1024 ** 3):.2f} GB"
    memory_available = f"{memory_info.available / (1024 ** 3):.2f} GB"
    memory_used = f"{memory_info.used / (1024 ** 3):.2f} GB"
    memory_percent = memory_info.percent
    gpuInfo = []
    devices = ["cpu", "cuda:0"]
    gpus = GPUtil.getGPUs()
    for gpu in gpus:
        gpuInfo.append(
            {
                "gpu_id": gpu.id,
                "gpu_load": f"{gpu.load}%",
                "gpu_memory": {
                    "total_MB": f"{gpu.memoryTotal} MiB",
                    "total_GB": f"{gpu.memoryTotal / 1024:.2f} GiB",
                    "used": f"{gpu.memoryUsed} MiB",
                    "free": f"{gpu.memoryFree} MiB"
                }
            }
        )
    status_data = {
        "devices": devices,
        "cpu_percent": cpu_percent,
        "memory_total": memory_total,
        "memory_available": memory_available,
        "memory_used": memory_used,
        "memory_percent": memory_percent,
        "gpu": gpuInfo,
    }
    return status_data