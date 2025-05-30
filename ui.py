import streamlit as st
import requests
import json
from streamlit_autorefresh import st_autorefresh
import time
import logging
from config import *
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
logger = logging.getLogger("rms_ui")

# Настройка страницы
st.set_page_config(
    page_title="RMS - Remote Management System",
    page_icon="🖥️",
    layout="wide"
)

# Инициализация состояния сессии
if "error" not in st.session_state:
    st.session_state.error = None
if "success" not in st.session_state:
    st.session_state.success = None

def show_messages():
    if st.session_state.error:
        st.error(st.session_state.error)
        st.session_state.error = None
    if st.session_state.success:
        st.success(st.session_state.success)
        st.session_state.success = None

def safe_request(method, url, **kwargs):
    try:
        response = method(url, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        st.session_state.error = f"Ошибка сети: {str(e)}"
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        st.session_state.error = f"Неожиданная ошибка: {str(e)}"
        return None

# Заголовок
st.title("🖥️ RMS - Remote Management System")

# Боковая панель с выбором хоста
with st.sidebar:
    st.header("Выбор хоста")
    
    # Получаем список клиентов
    try:
        logger.info(f"Запрос списка клиентов с {SERVER_URL}/ui/get_clients")
        response = requests.get(f"{SERVER_URL}/ui/get_clients", timeout=AGENT_TIMEOUT)
        response.raise_for_status()  # Проверяем статус ответа
        clients = response.json()
        logger.info(f"Получено {len(clients)} клиентов: {list(clients.keys())}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка получения списка клиентов: {e}")
        st.error(f"Ошибка получения списка клиентов: {e}")
        clients = {}
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении списка клиентов: {e}")
        st.error(f"Неожиданная ошибка: {e}")
    clients = {}

    # Создаем селектор хостов
    hostnames = list(clients.keys())
    if not hostnames:
        st.warning("""
        Нет доступных хостов. Убедитесь что:
        1. Сервер RMS запущен
        2. Агент запущен и подключен к серверу
        3. Сервер доступен по адресу: {SERVER_URL}
        """)
        selected_host = None
    else:
        selected_host = st.selectbox(
            "Выберите хост",
            hostnames,
            format_func=lambda x: f"{x} {'🟢' if clients[x]['online'] else '🔴'}"
        )

# Основной контент
if selected_host:
    # Информация о системе
    st.header("📊 Системная информация")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("CPU", f"{clients[selected_host]['cpu']}%")
    with col2:
        st.metric("RAM", f"{clients[selected_host]['memory']}%")
    with col3:
        st.metric("Статус", "Онлайн" if clients[selected_host]['online'] else "Оффлайн")
    
    # Диски
    st.subheader("💾 Диски")
    for disk, usage in clients[selected_host]['disks'].items():
        st.progress(usage/100, text=f"{disk}: {usage}%")
    
    # Управление службами
    st.header("⚙️ Управление службами")
    
    # Добавляем кнопку обновления списка служб
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Обновить список служб"):
            try:
                response = requests.post(
                    f"{SERVER_URL}/ui/push_task",
                    json={"host": selected_host, "cmd": "__list_services__"},
                    timeout=AGENT_TIMEOUT
                )
                response.raise_for_status()
                st.success("Запрос на обновление отправлен")
                time.sleep(1)  # Даем время на обновление
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при обновлении списка служб: {e}")
    
    # Получаем список служб
    try:
        services_response = requests.get(f"{SERVER_URL}/ui/get_services/{selected_host}", timeout=AGENT_TIMEOUT)
        services_response.raise_for_status()
        services = services_response.json()
    except Exception as e:
        st.error(f"Ошибка получения списка служб: {e}")
        services = []
    
    if services:
        # Добавляем фильтрацию и поиск
        col1, col2 = st.columns([2, 1])
        with col1:
            search_term = st.text_input("🔍 Поиск службы", "")
        with col2:
            status_filter = st.selectbox("Фильтр по статусу", ["Все", "Работает", "Остановлена", "Ошибка"])
        
        # Фильтруем службы
        filtered_services = services
        if search_term:
            filtered_services = [s for s in filtered_services if 
                               search_term.lower() in s.get("name", "").lower() or 
                               search_term.lower() in s.get("display", "").lower()]
        if status_filter != "Все":
            filtered_services = [s for s in filtered_services if s.get("status", "") == status_filter]
        
        # Создаем таблицу служб
        service_data = []
        for svc in filtered_services:
            status = svc.get("status", "N/A")
            status_color = {
                'Работает': '🟢',
                'Остановлена': '🔴',
                'Ошибка': '⚠️'
            }.get(status, '⚪')
            
            service_data.append({
                "Имя": svc.get("name", "N/A"),
                "Отображаемое имя": svc.get("display", "N/A"),
                "Статус": f"{status_color} {status}",
                "Тип запуска": svc.get("start_type", "N/A"),
                "Описание": svc.get("description", "N/A")
            })
        
        # Отображаем таблицу
        st.dataframe(
            service_data,
            use_container_width=True,
            height=400  # Фиксированная высота с прокруткой
        )
        
        # Управление выбранной службой
        st.subheader("Управление службой")
        service_name = st.selectbox("Выберите службу", [s["name"] for s in filtered_services])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("▶️ Запустить"):
                try:
                    response = requests.post(
                        f"{SERVER_URL}/ui/push_task",
                        json={"host": selected_host, "cmd": f"__service__::start::{service_name}"},
                        timeout=AGENT_TIMEOUT
                    )
                    response.raise_for_status()
                    st.success("Команда отправлена")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")
        
        with col2:
            if st.button("⏹️ Остановить"):
                try:
                    response = requests.post(
                        f"{SERVER_URL}/ui/push_task",
                        json={"host": selected_host, "cmd": f"__service__::stop::{service_name}"},
                        timeout=AGENT_TIMEOUT
                    )
                    response.raise_for_status()
                    st.success("Команда отправлена")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")
        
        with col3:
            if st.button("🔄 Перезапустить"):
                try:
                    response = requests.post(
                        f"{SERVER_URL}/ui/push_task",
                        json={"host": selected_host, "cmd": f"__service__::restart::{service_name}"},
                        timeout=AGENT_TIMEOUT
                    )
                    response.raise_for_status()
                    st.success("Команда отправлена")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")
    else:
        st.warning("""
        Нет доступных служб. Попробуйте:
        1. Нажать кнопку 'Обновить список служб'
        2. Убедиться, что агент имеет права на чтение служб Windows
        3. Проверить логи агента на наличие ошибок
        """)
    
    # Выполнение команд
    st.header("💻 Выполнение команд")
    command = st.text_area("Введите команду")
    if st.button("Выполнить"):
        if command:
            try:
                requests.post(
                    f"{SERVER_URL}/ui/push_task",
                    json={"host": selected_host, "cmd": command},
                    timeout=AGENT_TIMEOUT
                )
                st.success("Команда отправлена")
            except Exception as e:
                st.error(f"Ошибка: {e}")
        else:
            st.warning("Введите команду")
    
    # История выполнения команд
    st.header("📜 История выполнения команд")
    
    # Получаем историю
    try:
        results_response = requests.get(f"{SERVER_URL}/ui/get_results/{selected_host}", timeout=AGENT_TIMEOUT)
        results = results_response.json()
    except Exception as e:
        st.error(f"Ошибка получения истории: {e}")
        results = []
    
    # Отображаем историю
    if results:
        for result in reversed(results):
            with st.expander(f"Команда: {result['cmd']}"):
                st.code(result['result'])
        
        if st.button("Очистить историю"):
            try:
                requests.delete(f"{SERVER_URL}/ui/clear_results/{selected_host}", timeout=AGENT_TIMEOUT)
                st.success("История очищена")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка: {e}")
else:
        st.info("История пуста")

# Автообновление
time.sleep(5)
st.rerun()

# Показываем сообщения об ошибках/успехе
show_messages()
