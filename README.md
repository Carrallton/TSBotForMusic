# TS3 Music Bot

Музыкальный бот для TeamSpeak 3 с поддержкой YouTube, Spotify, радио, очереди, голосования, истории и т.д.

## Функции

- Воспроизведение музыки с YouTube, Spotify, и других сервисов (через `yt-dlp`)
- Очередь треков
- Команды: `!play`, `!skip`, `!stop`, `!pause`, `!resume`, `!volume`, `!queue`, `!clear`, `!history`, `!playlist`, `!vote-skip`, `!radio`, `!autodisconnect`, `!help`
- История прослушивания
- Персональные плейлисты
- Система голосования за пропуск трека
- Поддержка радиостанций
- Таймер автодиска
- Веб-панель управления (в разработке)

## Установка

```bash
git clone https://github.com/yourusername/ts3_music_bot.git
cd ts3_music_bot
pip3 install -r requirements.txt


Настройка
1. Установите TeamSpeak 3 сервер.
2. Настройте PulseAudio:

pactl load-module module-null-sink sink_name=ts3audio sink_properties=device.description="TS3Audio"

3. Установите TeamSpeak 3 клиент и настройте его на использование Monitor of TS3Audio как входное устройство.
4. Отредактируйте ts3_music_bot.py, указав 
*TS_HOST
*TS_USER
*TS_PASSWORD
*TS_CHANNEL_ID

Запуск:
python3 ts3_music_bot.py

Автозапуск:

sudo cp ts3musicbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ts3musicbot
sudo systemctl start ts3musicbot