# src/bt_dl/bot.py
import os
import asyncio
import re
from pathlib import Path
from urllib.parse import urljoin, quote
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from dotenv import dotenv_values
from httpx import AsyncClient, TimeoutException
from bs4 import BeautifulSoup
from typing import Optional

config = dotenv_values()

BOT_TOKEN = config.get("BOT_TOKEN")
RUTRACKER_LOGIN = config.get("RUTRACKER_LOGIN")
RUTRACKER_PASSWORD = config.get("RUTRACKER_PASSWORD")
TORRENTS_DIR = config.get("TORRENTS_DIR", "./torrents")
USER_AGENT = config.get("USER_AGENT", "bt-dl-bot/0.1")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в .env")


Path(TORRENTS_DIR).mkdir(parents=True, exist_ok=True)
USE_RUTRACKER_AUTH = bool(RUTRACKER_LOGIN and RUTRACKER_PASSWORD)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кэш: user_id -> { "query": "...", "results": [...], "forum_filter": None }
user_search_sessions = {}

class RutrackerClient:
    def __init__(self, login: str, password: str, user_agent: str):
        self.username = login
        self.password = password
        self.user_agent = user_agent
        self.base_url = "https://rutracker.org/forum/"
        self.client = AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=20.0,
            follow_redirects=True
        )
        self.is_logged_in = False




    async def login(self) -> bool:
        try:
            print("\n" + "="*60)
            print("🔍 НАЧАЛО ПРОЦЕССА ВХОДА НА RUTRACKER")
            print("="*60)
            
            # Шаг 1: Запрос страницы входа
            print("➡️ 1. Запрашиваем https://rutracker.org/forum/login.php")
            resp = await self.client.get(f"{self.base_url}login.php")
            print(f"   Статус: {resp.status_code}")
            print(f"   URL после редиректа: {resp.url}")
            
            # Сохраняем HTML для анализа
            with open("/tmp/rutracker_debug_login.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            print("   📄 HTML сохранён в /tmp/rutracker_debug_login.html")
    
            # Проверяем, не перенаправило ли на CAPTCHA или блокировку
            if "captcha" in resp.text.lower() or "blocked" in resp.text.lower():
                print("   ⚠️ Обнаружена CAPTCHA или блокировка!")
                return False
    
            # Шаг 2: Парсим форму
            print("\n➡️ 2. Ищем форму входа...")
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Ищем по новому ID
            form = soup.find("form", {"id": "login-form-quick"})
            if not form:
                print("   ❌ Форма с id='login-form-quick' НЕ НАЙДЕНА")
                # Попробуем найти любую форму с login_username
                form = soup.find("input", {"name": "login_username"})
                if form:
                    print("   ⚠️ Найдено поле login_username, но форма не распознана")
                    form = form.find_parent("form")
                    if form:
                        print("   ✅ Найдена форма через родителя поля login_username")
                    else:
                        print("   ❌ Родительская форма не найдена")
                else:
                    print("   ❌ Поле login_username не найдено в HTML")
                    return False
            else:
                print("   ✅ Форма найдена по id='login-form-quick'")
    
            # Шаг 3: Собираем данные формы
            print("\n➡️ 3. Собираем данные формы:")
            data = {}
            for inp in form.find_all("input"):
                name = inp.get("name")
                if name:
                    value = inp.get("value") or ""
                    data[name] = value
                    print(f"   {name} = {value}")
    
            # Добавляем учётные данные
            data["login_username"] = self.username
            data["login_password"] = self.password
            data["login"] = "вход"  # именно строчная буква!
            print(f"   login_username = {self.username}")
            print(f"   login_password = {'*' * len(self.password)}")
            print(f"   login = вход")
    
            # Шаг 4: Отправляем форму
            print("\n➡️ 4. Отправляем данные на сервер...")
            post_resp = await self.client.post(f"{self.base_url}login.php", data=data)
            print(f"   Статус ответа: {post_resp.status_code}")
            print(f"   URL после отправки: {post_resp.url}")
    
            # Сохраняем ответ
            with open("/tmp/rutracker_debug_after_login.html", "w", encoding="utf-8") as f:
                f.write(post_resp.text)
            print("   📄 Ответ сохранён в /tmp/rutracker_debug_after_login.html")
    
            # Шаг 5: Проверяем успешность
            print("\n➡️ 5. Проверяем, вошли ли мы...")
            if "profile.php" in post_resp.text:
                print("   ✅ УСПЕХ: найдена ссылка на profile.php")
                self.is_logged_in = True
                return True
            elif "Выход" in post_resp.text:
                print("   ✅ УСПЕХ: найдена кнопка 'Выход'")
                self.is_logged_in = True
                return True
            elif "Неверное имя или пароль" in post_resp.text:
                print("   ❌ ОШИБКА: Неверный логин или пароль")
                return False
            elif "captcha" in post_resp.text.lower():
                print("   ❌ ОШИБКА: Требуется CAPTCHA")
                return False
            else:
                print("   ❌ НЕИЗВЕСТНАЯ ОШИБКА: не удалось определить статус входа")
                # Покажем фрагмент HTML
                snippet = post_resp.text[:500].replace('\n', ' ')
                print(f"   Первые 500 символов ответа: {snippet}...")
                return False
    
        except Exception as e:
            print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            print("="*60)
            print("КОНЕЦ ПРОЦЕССА ВХОДА")
            print("="*60 + "\n")



    async def search(self, query: str, forum_id: Optional[str] = None):
        if not self.is_logged_in:
            raise RuntimeError("Не авторизован")

        url = f"{self.base_url}tracker.php?nm={quote(query)}"
        if forum_id:
            url += f"&f={forum_id}"

        resp = await self.client.get(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table#tor-tbl tr.tor-tr")
        results = []

        for row in rows:
            try:
                # Название раздачи
                title_tag = row.select_one("a.tor-topic-title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                topic_url = urljoin(self.base_url, title_tag["href"])

                # Форум
                forum_tag = row.select_one("td.forum_name a.gen.f")
                forum_name = forum_tag.get_text(strip=True) if forum_tag else "Неизвестно"
                forum_id_match = forum_tag.get("href", "") if forum_tag else ""
                forum_id = None
                if "f=" in forum_id_match:
                    forum_id = forum_id_match.split("f=")[-1].split("&")[0]

                # Размер и сиды
                size_tag = row.select_one("td:nth-child(5)")
                size = size_tag.get_text(strip=True) if size_tag else "?"

                seeders_tag = row.select_one("b.seedmed")
                seeders = seeders_tag.get_text(strip=True) if seeders_tag else "0"

                results.append({
                    "title": title,
                    "forum_name": forum_name,
                    "forum_id": forum_id,
                    "size": size,
                    "seeders": seeders,
                    "topic_url": topic_url,
                })
            except Exception as e:
                continue
        return results

    async def download_torrent(self, topic_url: str):
        resp = await self.client.get(topic_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        torrent_tag = soup.select_one("a[href*='/forum/dl.php?t=']")
        if not torrent_tag:
            raise ValueError("Torrent link not found")

        torrent_url = urljoin(self.base_url, torrent_tag["href"])
        torrent_resp = await self.client.get(torrent_url)
        torrent_resp.raise_for_status()
        return torrent_resp.content

    async def close(self):
        await self.client.aclose()

rutracker_client = None

async def get_rutracker_client():
    global rutracker_client
    if rutracker_client is None and USE_RUTRACKER_AUTH:
        rutracker_client = RutrackerClient(RUTRACKER_LOGIN, RUTRACKER_PASSWORD, USER_AGENT)
        if not await rutracker_client.login():
            rutracker_client = None
    return rutracker_client

def build_keyboard_with_forums(results: list) -> InlineKeyboardMarkup:
    buttons = []

    # Собираем уникальные форумы
    forums = {}
    for r in results:
        fid = r.get("forum_id")
        fname = r.get("forum_name", "Без названия")
        if fid and fid not in forums:
            forums[fid] = fname

    # Добавляем кнопки форумов (если есть)
    if forums:
        buttons.append([InlineKeyboardButton(text="📂 Фильтры по разделам:", callback_data="noop")])
        for fid, fname in list(forums.items())[:10]:  # макс. 10 форумов
            fname_short = (fname[:25] + "...") if len(fname) > 25 else fname
            buttons.append([InlineKeyboardButton(text=f"📁 {fname_short}", callback_data=f"forum_{fid}")])
        buttons.append([])  # пустая строка

    # Кнопки раздач
    for i, r in enumerate(results[:30]):  # ограничим 30 раздачами
        title_short = (r["title"][:35] + "...") if len(r["title"]) > 35 else r["title"]
        btn = InlineKeyboardButton(
            text=f"🎬 {title_short} ({r['seeders']})",
            callback_data=f"select_{i}"
        )
        buttons.append([btn])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("🔍 Напиши название раздачи для поиска на Rutracker.")

@dp.message()
async def handle_search(message: Message):
    query = message.text.strip()
    if not query:
        await message.answer("Введите запрос.")
        return

    if not USE_RUTRACKER_AUTH:
        await message.answer("❌ Бот не настроен для Rutracker.")
        return

    await message.answer("🔍 Ищу... (10–20 секунд)")

    client = await get_rutracker_client()
    if not client:
        await message.answer("❌ Ошибка авторизации.")
        return

    try:
        results = await client.search(query)
    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {e}")
        return

    if not results:
        await message.answer("Ничего не найдено 😕")
        return

    # Сохраняем сессию поиска
    user_search_sessions[message.from_user.id] = {
        "query": query,
        "results": results,
        "forum_filter": None
    }

    # Формируем текст
    text = f"Найдено {len(results)} результатов:\n\n"
    for i, r in enumerate(results[:8]):
        text += f"{i+1}. {r['title']}\n   📁 {r['forum_name']}\n   📦 {r['size']} | 💎 {r['seeders']}\n\n"

    if len(results) > 8:
        text += f"... и ещё {len(results) - 8} раздач."

    try:
        await message.answer(
            text,
            reply_markup=build_keyboard_with_forums(results),
            disable_web_page_preview=True
        )
    except TelegramBadRequest:
        await message.answer("Слишком много данных. Уточните запрос.")

@dp.callback_query(F.data.startswith("forum_"))
async def handle_forum_filter(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = user_search_sessions.get(user_id)
    if not session:
        await callback.answer("Сессия устарела.", show_alert=True)
        return

    forum_id = callback.data.split("_", 1)[1]
    query = session["query"]

    await callback.answer(f"🔍 Ищу в разделе...", show_alert=False)
    await callback.message.edit_text("🔄 Выполняю поиск в выбранном разделе...")

    client = await get_rutracker_client()
    if not client:
        await callback.message.answer("❌ Нет сессии Rutracker.")
        return

    try:
        results = await client.search(query, forum_id=forum_id)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
        return

    if not results:
        await callback.message.edit_text("В этом разделе ничего не найдено.")
        return

    # Обновляем сессию
    user_search_sessions[user_id] = {
        "query": query,
        "results": results,
        "forum_filter": forum_id
    }

    text = f"Результаты в разделе:\n\n"
    for i, r in enumerate(results[:8]):
        text += f"{i+1}. {r['title']}\n   📦 {r['size']} | 💎 {r['seeders']}\n\n"

    try:
        await callback.message.edit_text(
            text,
            reply_markup=build_keyboard_with_forums(results)
        )
    except TelegramBadRequest:
        await callback.message.answer("Слишком много результатов.")

@dp.callback_query(F.data.startswith("select_"))
async def handle_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = user_search_sessions.get(user_id)
    if not session:
        await callback.answer("Сессия устарела.", show_alert=True)
        return

    try:
        index = int(callback.data.split("_")[1])
        results = session["results"]
        selected = results[index]
    except (IndexError, ValueError, KeyError):
        await callback.answer("Неверный выбор.", show_alert=True)
        return

    await callback.answer("📥 Скачиваю торрент...", show_alert=False)

    client = await get_rutracker_client()
    if not client:
        await callback.message.answer("❌ Ошибка сессии.")
        return

    try:
        torrent_data = await client.download_torrent(selected["topic_url"])
    except Exception as e:
        await callback.message.answer(f"❌ Не удалось скачать торрент: {e}")
        return

    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', selected["title"])[:100]
    filename = f"{safe_title}.torrent"
    filepath = Path(TORRENTS_DIR) / filename

    counter = 1
    while filepath.exists():
        filepath = Path(TORRENTS_DIR) / f"{safe_title}_{counter}.torrent"
        counter += 1

    with open(filepath, "wb") as f:
        f.write(torrent_data)

    await callback.message.answer(
        f"✅ Торрент сохранён:\n📁 `{filepath.name}`\n\n"
        f"Woodpecker/qBittorrent автоматически добавит раздачу."
    )
    user_search_sessions.pop(user_id, None)

@dp.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery):
    user_search_sessions.pop(callback.from_user.id, None)
    await callback.message.edit_text("❌ Поиск отменён.")
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()

async def main():
    print("✅ bt-dl-bot запущен...")
    print(f"📁 TORRENTS_DIR: {TORRENTS_DIR}")
    if USE_RUTRACKER_AUTH:
        print(f"🔐 Rutracker: {RUTRACKER_LOGIN}")
    try:
        await dp.start_polling(bot)
    finally:
        if rutracker_client:
            await rutracker_client.close()

def cli():
    """CLI entry point for Poetry script."""
    asyncio.run(main())

if __name__ == "__main__":
    cli()

