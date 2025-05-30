from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import uvicorn, time
import logging
from server_config import *

# Настройка логирования
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rms_server")

app = FastAPI(title="RMS Server", version="1.0.0")

# Разрешаем кросс-доменные запросы
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⬇️ Основные хранилища ⬇️

# Информация о каждом подключённом клиенте (имя, IP, CPU, RAM, диски)
clients_info: Dict[str, Dict] = {}

# Очередь команд для каждого клиента
tasks: Dict[str, List[str]] = {}

# История выполнения команд (результаты)
results: Dict[str, List[Dict]] = {}

# Временные метки последнего пинга от клиента (для определения "онлайн/оффлайн")
online_status: Dict[str, float] = {}

# Состояние служб по каждому клиенту (список словарей: name, status, display)
service_states: Dict[str, List[Dict]] = {}

# 🧱 Pydantic-модели для API

class ClientInfo(BaseModel):
    hostname: str
    ip: str
    cpu: float
    memory: float
    disks: Dict[str, float]

class Result(BaseModel):
    host: str
    cmd: str
    result: str

class Command(BaseModel):
    host: str
    cmd: str

def limit_results(host: str):
    """Ограничивает количество результатов для хоста"""
    if host in results and len(results[host]) > MAX_RESULTS_PER_HOST:
        results[host] = results[host][-MAX_RESULTS_PER_HOST:]

def limit_tasks(host: str):
    """Ограничивает количество задач для хоста"""
    if host in tasks and len(tasks[host]) > MAX_TASKS_PER_HOST:
        tasks[host] = tasks[host][-MAX_TASKS_PER_HOST:]

# ✅ Получение информации от агента
@app.post("/agent/post_info")
async def post_info(info: ClientInfo):
    try:
        clients_info[info.hostname] = info.model_dump()
        online_status[info.hostname] = time.time()
        logger.info(f"Received info from {info.hostname}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing info from {info.hostname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Агент присылает состояние всех служб
@app.post("/agent/post_services/{hostname}")
async def post_services(hostname: str, data: List[Dict]):
    try:
        service_states[hostname.lower()] = data
        logger.info(f"Updated services for {hostname}")
        return {"status": "services updated"}
    except Exception as e:
        logger.error(f"Error updating services for {hostname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Получение команд, которые надо выполнить агенту
@app.get("/agent/get_tasks/{hostname}")
async def get_tasks(hostname: str):
    try:
        commands = tasks.pop(hostname, [])
        if commands:
            logger.info(f"Sending {len(commands)} tasks to {hostname}")
        return {"commands": commands}
    except Exception as e:
        logger.error(f"Error getting tasks for {hostname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Получение результатов команд от агента
@app.post("/agent/post_result")
async def post_result(res: Result):
    try:
        if res.host not in results:
            results[res.host] = []
        results[res.host].append(res.model_dump())
        limit_results(res.host)  # Ограничиваем количество результатов
        logger.info(f"Received result from {res.host} for command: {res.cmd[:50]}...")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error processing result from {res.host}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# пойнты для UI
# ✅ Список клиентов и их статус (онлайн/оффлайн)
@app.get("/ui/get_clients")
async def get_clients():
    try:
        current_time = time.time()
        return {
            k: {
                **v,
                "online": current_time - online_status.get(k, 0) < AGENT_TIMEOUT
            }
            for k, v in clients_info.items()
        }
    except Exception as e:
        logger.error(f"Error getting clients list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Получение истории выполнения команд (для UI)
@app.get("/ui/get_results/{hostname}")
async def get_results(hostname: str):
    try:
        return results.get(hostname, [])
    except Exception as e:
        logger.error(f"Error getting results for {hostname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Отправка новой команды агенту
@app.post("/ui/push_task")
async def push_task(cmd: Command):
    try:
        if cmd.host not in tasks:
            tasks[cmd.host] = []
        tasks[cmd.host].append(cmd.cmd)
        limit_tasks(cmd.host)  # Ограничиваем количество задач
        logger.info(f"Pushed task to {cmd.host}: {cmd.cmd[:50]}...")
        return {"status": "task added"}
    except Exception as e:
        logger.error(f"Error pushing task to {cmd.host}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Очистка истории выполнения команд
@app.delete("/ui/clear_results/{hostname}")
async def clear_results(hostname: str):
    try:
        results[hostname] = []
        logger.info(f"Cleared results for {hostname}")
        return {"status": f"cleared for {hostname}"}
    except Exception as e:
        logger.error(f"Error clearing results for {hostname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ UI запрашивает актуальное состояние служб
@app.get("/ui/get_services/{hostname}")
async def get_services(hostname: str):
    try:
        return service_states.get(hostname.lower(), [])
    except Exception as e:
        logger.error(f"Error getting services for {hostname}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ UI запрашивает актуальное состояние всех служб
@app.get("/ui/get_all_services")
async def get_all_services():
    try:
        return service_states
    except Exception as e:
        logger.error(f"Error getting all services: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ▶️ Запуск сервера
if __name__ == "__main__":
    logger.info(f"Starting RMS Server on {SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
