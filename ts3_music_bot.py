import socket
import subprocess
import threading
import time
import re
import queue
from yt_dlp import YoutubeDL

# === Настройки ===
TS_HOST = "127.0.0.1"
TS_QUERY_PORT = 10011
TS_USER = "serveradmin"
TS_PASSWORD = "tspeakbot"
TS_CHANNEL_ID = "1"  # ID канала
BOT_NICKNAME = "MusicBot"

class TS3MusicBot:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((TS_HOST, TS_QUERY_PORT))
        self.sock.recv(1024)  # приветствие
        self.send_command("login client_login_name={0} client_login_password={1}".format(TS_USER, TS_PASSWORD))
        self.send_command("use sid=1")  # используем первый виртуальный сервер
        self.send_command("clientupdate client_nickname={0}".format(BOT_NICKNAME))
        self.send_command("clientmove clid={0} cid={1}".format(self.get_client_id(), TS_CHANNEL_ID))
        self.queue = queue.Queue()
        self.current_process = None
        self.playing = False

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

    def listen_for_commands(self):
        while True:
            response = self.sock.recv(4096).decode()
            if "!play" in response:
                try:
                    url = response.split("!play ")[1].split("\\s")[0]
                    self.queue.put(url)
                    if not self.playing:
                        self.start_playback()
                except IndexError:
                    print("Неправильная команда !play")
            elif "!skip" in response:
                self.skip()
            elif "!stop" in response:
                self.stop()

    def start_playback(self):
        while not self.queue.empty():
            self.playing = True
            url = self.queue.get()
            self.play_url(url)
        self.playing = False

    def play_url(self, url):
        with YoutubeDL({'format': 'bestaudio/best'}) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        # Воспроизводим через FFmpeg и отправляем в PulseAudio
        cmd = [
            "ffmpeg",
            "-i", audio_url,
            "-f", "s16le",
            "-ar", "48000",
            "-ac", "2",
            "-",
        ]
        self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE)

        # Отправляем в PulseAudio
        playback_cmd = [
            "pacat",
            "--device=ts3audio.monitor",
            "--format=s16le",
            "--rate=48000",
            "--channels=2"
        ]
        playback_process = subprocess.Popen(playback_cmd, stdin=self.current_process.stdout)
        playback_process.wait()
        self.current_process.wait()

    def skip(self):
        if self.current_process:
            self.current_process.terminate()

    def stop(self):
        self.queue.queue.clear()
        if self.current_process:
            self.current_process.terminate()

# === Запуск бота ===
if __name__ == "__main__":
    bot = TS3MusicBot()
    bot.listen_for_commands()