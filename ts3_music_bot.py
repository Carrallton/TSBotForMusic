import socket
import subprocess
import threading
import time
import re
import queue
import logging
import json
import os
import schedule
from yt_dlp import YoutubeDL

# === Загрузка конфига ===
with open("config.json", "r") as f:
    config = json.load(f)

TS_HOST = config["TS_HOST"]
TS_QUERY_PORT = config["TS_QUERY_PORT"]
TS_USER = config["TS_USER"]
TS_PASSWORD = config["TS_PASSWORD"]
TS_CHANNEL_ID = config["TS_CHANNEL_ID"]
BOT_NICKNAME = config["BOT_NICKNAME"]
QUEUE_FILE = config["QUEUE_FILE"]
HISTORY_FILE = config["HISTORY_FILE"]
PLAYLISTS_FILE = config["PLAYLISTS_FILE"]
VOTES_FILE = config["VOTES_FILE"]
AUTO_DISCONNECT_MINUTES = config["AUTO_DISCONNECT_MINUTES"] * 60

# === Логирование ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TS3MusicBot:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((TS_HOST, TS_QUERY_PORT))
        self.sock.recv(1024)  # приветствие
        self.send_command("login client_login_name={0} client_login_password={1}".format(TS_USER, TS_PASSWORD))
        self.send_command("use sid=1")
        self.send_command("clientupdate client_nickname={0}".format(BOT_NICKNAME))
        self.send_command("clientmove clid={0} cid={1}".format(self.get_client_id(), TS_CHANNEL_ID))
        self.queue = queue.Queue()
        self.current_process = None
        self.playing = False
        self.paused = False
        self.current_url = None
        self.current_title = None
        self.volume = 100  # по умолчанию 100%
        self.last_activity = time.time()
        self.autodisconnect_timer = AUTO_DISCONNECT_MINUTES
        self.load_queue()
        logging.info("Бот подключён к TeamSpeak.")

    def send_command(self, cmd):
        self.sock.send((cmd + "\n").encode())
        response = self.sock.recv(4096).decode()
        return response

    def get_client_id(self):
        response = self.send_command("clientlist")
        for line in response.splitlines():
            if BOT_NICKNAME in line:
                clid = re.search(r"clid=(\d+)", line)
                if clid:
                    return clid.group(1)
        return None

    def load_queue(self):
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r") as f:
                data = json.load(f)
                for item in data:
                    self.queue.put((item['url'], item['title']))
            logging.info("Очередь загружена из файла.")

    def save_queue(self):
        items = []
        temp_queue = list(self.queue.queue)
        for url, title in temp_queue:
            items.append({"url": url, "title": title})
        with open(QUEUE_FILE, "w") as f:
            json.dump(items, f)
        logging.info("Очередь сохранена в файл.")

    def add_to_history(self, title):
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        history.append({"title": title, "timestamp": time.time()})
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)

    def show_history(self):
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                hist = json.load(f)
            titles = [f"{i+1}. {item['title']}" for i, item in enumerate(hist[-10:])]
            msg = "\n".join(titles) or "История пуста."
        else:
            msg = "История пуста."
        self.send_message("Последние 10 треков:\n" + msg)

    def save_playlist(self, name, tracks):
        playlists = {}
        if os.path.exists(PLAYLISTS_FILE):
            with open(PLAYLISTS_FILE, "r") as f:
                playlists = json.load(f)
        playlists[name] = tracks
        with open(PLAYLISTS_FILE, "w") as f:
            json.dump(playlists, f)

    def load_playlist(self, name):
        if os.path.exists(PLAYLISTS_FILE):
            with open(PLAYLISTS_FILE, "r") as f:
                playlists = json.load(f)
            return playlists.get(name, [])
        return []

    def add_track_to_playlist(self, user, playlist_name, url, title):
        playlists = {}
        if os.path.exists(PLAYLISTS_FILE):
            with open(PLAYLISTS_FILE, "r") as f:
                playlists = json.load(f)
        key = f"{user}:{playlist_name}"
        if key not in playlists:
            playlists[key] = []
        playlists[key].append({"url": url, "title": title})
        with open(PLAYLISTS_FILE, "w") as f:
            json.dump(playlists, f)

    def init_vote(self, user):
        votes = {"skip": {"users": [], "needed": 3}}
        if os.path.exists(VOTES_FILE):
            with open(VOTES_FILE, "r") as f:
                votes = json.load(f)
        if "skip" not in votes:
            votes["skip"] = {"users": [], "needed": 3}
        if user not in votes["skip"]["users"]:
            votes["skip"]["users"].append(user)
            with open(VOTES_FILE, "w") as f:
                json.dump(votes, f)
            self.send_message(f"{user} проголосовал за пропуск. Голосов: {len(votes['skip']['users'])}/{votes['skip']['needed']}")
            if len(votes["skip"]["users"]) >= votes["skip"]["needed"]:
                self.skip()
                self.send_message("Достигнуто необходимое количество голосов. Трек пропущен.")
                votes["skip"]["users"] = []  # сброс
                with open(VOTES_FILE, "w") as f:
                    json.dump(votes, f)
        else:
            self.send_message(f"{user}, вы уже голосовали.")

    def play_radio(self, url):
        self.queue.put((url, f"Radio: {url}"))
        self.save_queue()
        self.send_message(f"Добавлена радиостанция: {url}")
        if not self.playing:
            self.start_playback()

    def reset_timer(self):
        self.last_activity = time.time()

    def check_disconnect_timer(self):
        while True:
            if time.time() - self.last_activity > self.autodisconnect_timer:
                self.send_message("Бот отключается из-за бездействия.")
                break
            time.sleep(60)  # проверка раз в минуту

    def listen_for_commands(self):
        threading.Thread(target=self.check_disconnect_timer).start()
        while True:
            try:
                response = self.sock.recv(4096).decode()
                self.reset_timer()
                if "!play" in response:
                    try:
                        url = response.split("!play ")[1].split("\\s")[0]
                        self.add_to_queue(url)
                    except IndexError:
                        self.send_message("Неправильное использование: !play <URL>")
                elif "!skip" in response:
                    self.skip()
                elif "!stop" in response:
                    self.stop()
                elif "!pause" in response:
                    self.pause()
                elif "!resume" in response:
                    self.resume()
                elif "!queue" in response:
                    self.show_queue()
                elif "!clear" in response:
                    self.clear_queue()
                elif "!volume" in response:
                    try:
                        vol = int(response.split("!volume ")[1].split("\\s")[0])
                        self.set_volume(vol)
                    except (IndexError, ValueError):
                        self.send_message("Неправильное использование: !volume <0-100>")
                elif "!history" in response:
                    self.show_history()
                elif "!playlist add" in response:
                    try:
                        parts = response.split("!playlist add ")[1].split(" ", 1)
                        playlist_name = parts[0]
                        url = parts[1]
                        user = "some_user"  # извлеките из сообщения
                        with YoutubeDL({'format': 'bestaudio/best'}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            title = info.get('title', 'Неизвестный трек')
                        self.add_track_to_playlist(user, playlist_name, url, title)
                        self.send_message(f"Трек добавлен в плейлист '{playlist_name}'.")
                    except (IndexError, Exception):
                        self.send_message("Неправильное использование: !playlist add <название> <URL>")
                elif "!vote-skip" in response:
                    user = "some_user"  # извлеките из сообщения
                    self.init_vote(user)
                elif "!radio" in response:
                    try:
                        url = response.split("!radio ")[1].split("\\s")[0]
                        self.play_radio(url)
                    except IndexError:
                        self.send_message("Неправильное использование: !radio <URL>")
                elif "!autodisconnect" in response:
                    try:
                        mins = int(response.split("!autodisconnect ")[1].split("\\s")[0])
                        self.autodisconnect_timer = mins * 60
                        self.send_message(f"Таймер автодиска отключен на {mins} минут.")
                    except (IndexError, ValueError):
                        self.send_message("Использование: !autodisconnect <минуты>")
                elif "!help" in response:
                    self.show_help()
            except Exception as e:
                logging.error(f"Ошибка при обработке команды: {e}")

    def add_to_queue(self, url):
        try:
            with YoutubeDL({'format': 'bestaudio/best'}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Неизвестный трек')
            self.queue.put((url, title))
            self.save_queue()
            self.send_message(f"Добавлено в очередь: {title}")
            if not self.playing:
                self.start_playback()
        except Exception as e:
            self.send_message(f"Ошибка при добавлении: {e}")
            logging.error(f"Ошибка добавления в очередь: {e}")

    def start_playback(self):
        while not self.queue.empty():
            url, title = self.queue.get()
            self.current_url = url
            self.current_title = title
            self.playing = True
            self.paused = False
            self.send_message(f"Воспроизводится: {title}")
            self.add_to_history(title)
            self.play_url(url)
        self.playing = False
        self.send_message("Очередь закончена.")

    def play_url(self, url):
        with YoutubeDL({'format': 'bestaudio/best'}) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        cmd = [
            "ffmpeg",
            "-i", audio_url,
            "-f", "s16le",
            "-ar", "48000",
            "-ac", "2",
            "-",
        ]
        self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        # Отправляем в PulseAudio
        playback_cmd = [
            "pacat",
            "--device=ts3audio.monitor",
            "--format=s16le",
            "--rate=48000",
            "--channels=2"
        ]
        self.playback_process = subprocess.Popen(playback_cmd, stdin=self.current_process.stdout)

        self.playback_process.communicate()  # ждём завершения
        self.current_process.wait()

    def skip(self):
        if self.current_process:
            self.current_process.terminate()
            self.send_message("Трек пропущен.")
        else:
            self.send_message("Нечего пропускать.")

    def stop(self):
        self.queue.queue.clear()
        if self.current_process:
            self.current_process.terminate()
        self.save_queue()
        self.send_message("Воспроизведение остановлено, очередь очищена.")

    def pause(self):
        if self.playing and not self.paused:
            if self.current_process:
                self.current_process.terminate()
                self.paused = True
                self.send_message("Воспроизведение на паузе.")
        else:
            self.send_message("Нечего ставить на паузу.")

    def resume(self):
        if self.paused and self.current_url:
            self.queue.put((self.current_url, self.current_title))
            self.paused = False
            self.save_queue()
            self.send_message("Воспроизведение возобновлено.")
        else:
            self.send_message("Нечего возобновлять.")

    def set_volume(self, vol):
        if 0 <= vol <= 100:
            self.volume = vol
            # Установка громкости через pactl
            subprocess.run(["pactl", "set-sink-volume", "ts3audio", f"{vol}%"])
            self.send_message(f"Громкость установлена: {vol}%")
        else:
            self.send_message("Громкость должна быть от 0 до 100.")

    def show_queue(self):
        if self.queue.empty():
            self.send_message("Очередь пуста.")
        else:
            items = []
            for i, (url, title) in enumerate(list(self.queue.queue)):
                items.append(f"{i+1}. {title}")
            msg = "\n".join(items)
            self.send_message("Очередь:\n" + msg)

    def clear_queue(self):
        self.queue.queue.clear()
        self.save_queue()
        self.send_message("Очередь очищена.")

    def show_help(self):
        help_msg = """
Доступные команды:
!play <URL> - добавить трек в очередь
!skip - пропустить текущий трек
!stop - остановить воспроизведение и очистить очередь
!pause - поставить на паузу
!resume - снять с паузы
!volume <0-100> - установить громкость
!queue - показать очередь
!clear - очистить очередь
!history - показать историю
!playlist add <название> <URL> - добавить в плейлист
!vote-skip - голосовать за пропуск
!radio <URL> - включить радио
!autodisconnect <минуты> - таймер автодиска
!help - показать эту помощь
        """
        self.send_message(help_msg)

    def send_message(self, msg):
        self.send_command(f"sendtextmessage targetmode=2 msg={msg}")

# === Запуск бота ===
if __name__ == "__main__":
    bot = TS3MusicBot()
    bot.listen_for_commands()