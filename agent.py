import time
import psutil
import requests
import socket
import subprocess
import platform
import json
import logging
from agent_config import *

# Настройка логирования
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rms_agent")

# Используем URL сервера из конфигурации
SERVER = f"{AGENT_SERVER_URL}/agent"

def collect_info():
    try:
        info = {
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disks": {
                d.mountpoint: psutil.disk_usage(d.mountpoint).percent
                for d in psutil.disk_partitions() if d.fstype
            }
        }
        logger.debug(f"Collected system info: {info}")
        return info
    except Exception as e:
        logger.error(f"Error collecting system info: {e}")
        raise

def list_services():
    try:
        if platform.system() == "Windows":
            output = subprocess.run(
                "sc query type= service state= all",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=SERVICE_COMMAND_TIMEOUT
            )
            lines = output.stdout.decode("cp866", errors="ignore").splitlines()
            services = []
            service = {}
            
            for line in lines:
                if line.strip().startswith("SERVICE_NAME") or line.strip().startswith("Имя_службы"):
                    if service:
                        services.append(service)
                    service = {"name": line.split(":")[-1].strip()}
                elif "STATE" in line or "Состояние" in line:
                    service["status"] = line.split(":")[-1].strip().split("  ")[-1]
                elif "DISPLAY_NAME" in line or "Выводимое_имя" in line:
                    service["display"] = line.split(":")[-1].strip()
            
            if service:
                services.append(service)
            
            logger.debug(f"Found {len(services)} Windows services")
            return services
        else:
            logger.warning("Services are only supported on Windows")
            return [{"name": "unsupported", "status": "N/A", "display": "Службы поддерживаются только на Windows"}]
    except subprocess.TimeoutExpired:
        logger.error("Timeout while listing services")
        return [{"name": "error", "status": "N/A", "display": "Timeout while listing services"}]
    except Exception as e:
        logger.error(f"Error listing services: {e}")
        return [{"name": "error", "status": "N/A", "display": f"Error: {str(e)}"}]

def get_service_status(name: str):
    try:
        for svc in list_services():
            if svc.get("name", "").lower() == name.lower():
                return svc
        logger.warning(f"Service not found: {name}")
        return {"name": name, "status": "unknown", "display": name}
    except Exception as e:
        logger.error(f"Error getting service status for {name}: {e}")
        return {"name": name, "status": "error", "display": f"Error: {str(e)}"}

def run_sc_command(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="cp866",
            errors="ignore",
            timeout=SERVICE_COMMAND_TIMEOUT
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while running command: {cmd}")
        return "[ERROR] Command timed out"
    except Exception as e:
        logger.error(f"Error running command {cmd}: {e}")
        return f"[ERROR] {e}"

def handle_command(cmd: str, hostname: str) -> str:
    try:
        logger.info(f"Handling command: {cmd}")
        
        if cmd == "__list_services__":
            services = list_services()
            requests.post(f"{SERVER}/post_services/{hostname}", json=services, timeout=AGENT_TIMEOUT)
            return json.dumps(services, ensure_ascii=False, indent=2)

        elif cmd.startswith("__service__"):
            parts = cmd.split("::")
            if len(parts) == 3:
                action, name = parts[1], parts[2]
                if action == "start":
                    output = run_sc_command(f'sc start "{name}"')
                elif action == "stop":
                    output = run_sc_command(f'sc stop "{name}"')
                elif action == "restart":
                    stop_output = run_sc_command(f'sc stop "{name}"')
                    time.sleep(1)
                    start_output = run_sc_command(f'sc start "{name}"')
                    output = f"[STOP OUTPUT]\n{stop_output}\n\n[START OUTPUT]\n{start_output}"
                else:
                    logger.error(f"Unknown service action: {action}")
                    return "[ERROR] Unknown action"
                return output

        elif cmd.startswith("__get_service_status__::"):
            name = cmd.split("::")[1]
            status = get_service_status(name)
            logger.debug(f"Service {name} status: {status}")
            return json.dumps(status, ensure_ascii=False)

        else:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="cp866",
                errors="ignore",
                timeout=COMMAND_TIMEOUT
            )
            return result.stdout
            
    except Exception as e:
        logger.error(f"Error handling command {cmd}: {e}")
        return f"[ERROR] {e}"

def main():
    logger.info(f"Starting RMS Agent, connecting to {SERVER}")
    
    while True:
        try:
            info = collect_info()
            response = requests.post(f"{SERVER}/post_info", json=info, timeout=AGENT_TIMEOUT)
            response.raise_for_status()
            
            tasks_response = requests.get(f"{SERVER}/get_tasks/{info['hostname']}", timeout=AGENT_TIMEOUT)
            tasks_response.raise_for_status()
            
            for cmd in tasks_response.json().get("commands", []):
                output = handle_command(cmd, info['hostname'])
                requests.post(f"{SERVER}/post_result", json={
                    "host": info['hostname'],
                    "cmd": cmd,
                    "result": output
                }, timeout=AGENT_TIMEOUT)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            
        time.sleep(AGENT_POLL_INTERVAL)

if __name__ == "__main__":
    main()
