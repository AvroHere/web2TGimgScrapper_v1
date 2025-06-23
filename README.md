# 🧾 Header
# 🖼️ Telegram Image Downloader Bot 🤖

A powerful Python bot that scrapes and downloads images from URLs, with queue management and Telegram integration.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python) 
![Platform](https://img.shields.io/badge/Platform-Telegram-blue?logo=telegram)
![Author](https://img.shields.io/badge/Author-AvroHere-green?logo=github)

# 🧩 Features
## ✨ Key Features

- **🌐 Web Scraper**: Extracts images from any webpage URL
- **📥 Batch Downloader**: Downloads multiple images in parallel
- **🗂️ Queue System**: Processes links in order with status updates
- **⏯️ Flow Control**: Pause/resume processing with commands
- **📤 Auto-Forwarding**: Sends images to different chats based on source
- **📊 Progress Tracking**: Shows remaining links count
- **⚡ Over Mode**: Priority processing for urgent links
- **📄 TXT File Support**: Process multiple URLs from text files

# 💾 Installation
## 🛠️ Setup Instructions

```bash
# Clone the repository
git clone https://github.com/AvroHere/telegram-image-downloader.git
cd telegram-image-downloader

# Install dependencies
pip install -r requirements.txt

# Configure your bot
# Edit main.py with your Telegram bot token and admin ID and Group ID

# Run the bot
python main.py
```

# 🧠 Usage
## 🤖 Bot Commands

1. **/start** - Show welcome message and instructions 🏁
2. **/help** - Display detailed help ℹ️
3. **/stopnow** - Pause processing ⏸️
4. **/startnow** - Resume processing ▶️
5. **/list** - Show current queue 📋
6. **/clean** - Clear all queued links 🧹
7. **/remain** - Get remaining links as text file 📄
8. **/over** - Enter priority processing mode ⚡
9. **/overstop** - Exit priority mode ↩️

**Usage Flow**:
- Send URLs directly or in .txt files
- Bot processes one URL at a time
- Automatically forwards images to target chat
- Shows progress updates

# 📁 Folder Structure
## 📂 Project Layout

```
telegram-image-downloader/
├── main.py # Main bot application
├── requirements.txt # Python dependencies
├── temp_images/ # Temporary image storage
├── README.md # This documentation
└── LICENSE.txt # MIT License file
```

```markdown
# 🛠 Built With
## 🔧 Technologies Used

**Core Libraries**:
- `python-telegram-bot` - Telegram Bot API wrapper
- `requests` - HTTP requests
- `BeautifulSoup4` - HTML parsing
- `concurrent.futures` - Parallel processing

**Standard Library**:
- `asyncio` - Asynchronous operations
- `os` - File system operations
- `logging` - Error tracking
- `urllib.parse` - URL handling
```

# ❓ FAQ
## ❔ Common Questions

**Q: Why are some images not downloading?**  
A: The bot may fail with sites that have anti-scraping measures or require JavaScript.

**Q: How to change the target group?**  
A: Modify the `TARGET_GROUP` and `GROUP_ID` variables in the main.py file.

# 📄 License
## ⚖️ MIT License

Copyright (c) 2025 AvroHere

Permission is hereby granted... [standard MIT license text]


# 👨‍💻 Author
## 🤝 AvroHere

- GitHub: [https://github.com/AvroHere](https://github.com/AvroHere)
- Quote: *"Code is poetry in motion"*

⭐ **If you find this project useful, please consider starring it on GitHub!** ⭐



