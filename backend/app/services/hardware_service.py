from typing import Dict, Any

def _get_torch():
    try:
        import torch
        return torch
    except Exception:
        return None

class HardwareService:
    @staticmethod
    def get_hardware_info() -> Dict[str, Any]:
        """Returns static hardware information."""
        torch = _get_torch()
        cuda_available = bool(torch and torch.cuda.is_available())
        
        info = {
            "cuda_enabled": cuda_available,
            "device_name": "CPU",
            "vram_total_gb": 0.0,
            "device": "cpu"
        }
        
        if cuda_available:
            info["device_name"] = torch.cuda.get_device_name(0)
            info["vram_total_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
            info["device"] = "cuda"
            
        return info

    @staticmethod
    def get_telemetry() -> Dict[str, Any]:
        """Returns dynamic hardware telemetry (utilization, VRAM usage)."""
        torch = _get_torch()
        cuda_available = bool(torch and torch.cuda.is_available())
        if not cuda_available:
            return {
                "gpu_utilization_pct": 0,
                "vram_used_gb": 0.0
            }
            
        # Try to get memory allocated by torch
        allocated = torch.cuda.memory_allocated(0)
        vram_used_gb = round(allocated / (1024**3), 2)
        
        # GPU utilization is hard to get purely from torch without pynvml, 
        # so we return a placeholder or attempt pynvml if installed
        utilization = 0
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            utilization = util.gpu
            
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_used_gb = round(mem.used / (1024**3), 2)
        except Exception:
            pass # Fall back to torch memory

        return {
            "gpu_utilization_pct": utilization,
            "vram_used_gb": vram_used_gb
        }

    @staticmethod
    def print_startup_check():
        info = HardwareService.get_hardware_info()
        print("\n" + "="*40)
        print("Compute Device:")
        print(info["device_name"])
        print("\nCUDA:")
        print("Enabled" if info["cuda_enabled"] else "Disabled")
        print("\nVRAM:")
        print(f'{info["vram_total_gb"]} GB' if info["cuda_enabled"] else "N/A")
        print("="*40 + "\n")
        
        from app.core.config import settings
        if info["cuda_enabled"] and not settings.USE_REAL_MODELS:
            # We are falling back to simulation/CPU despite having CUDA
            print("WARNING: GPU detected but not being used. (USE_REAL_MODELS=False)")
