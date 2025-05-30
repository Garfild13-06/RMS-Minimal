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
AGENT_POLL_INTERVAL = int(os.getenv("AGENT_POLL_INTERVAL", "5"))  # секунды
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "30"))  # секунды
AGENT_SERVER_URL = os.getenv("AGENT_SERVER_URL", SERVER_URL)  # URL сервера для агента

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOG_DIR / "rms.log"

# Настройки CORS
CORS_ORIGINS = [
    "http://localhost:8501",  # Streamlit по умолчанию
    "http://127.0.0.1:8501",
    "http://localhost:8800",
    "http://127.0.0.1:8800",
]

# Настройки безопасности
MAX_RESULTS_PER_HOST = int(os.getenv("MAX_RESULTS_PER_HOST", "100"))  # Максимальное количество результатов на хост
MAX_TASKS_PER_HOST = int(os.getenv("MAX_TASKS_PER_HOST", "10"))  # Максимальное количество задач в очереди 