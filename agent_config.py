import os
from pathlib import Path

# Базовые настройки
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Настройки сервера
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8800"))
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Настройки агента
AGENT_POLL_INTERVAL = int(os.getenv("AGENT_POLL_INTERVAL", "5"))  # секунды между опросами
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "30"))  # таймаут для сетевых запросов
AGENT_SERVER_URL = os.getenv("AGENT_SERVER_URL", SERVER_URL)  # URL сервера для агента

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOG_DIR / "rms_agent.log"

# Настройки команд
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))  # таймаут для выполнения команд
SERVICE_COMMAND_TIMEOUT = int(os.getenv("SERVICE_COMMAND_TIMEOUT", "60"))  # таймаут для команд служб 