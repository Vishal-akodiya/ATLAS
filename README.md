# ATLAS - Advanced AI Screen Assistant

ATLAS is a lightweight, multimodal desktop AI assistant built with Python and PyWebView. Powered by Google's Gemini API, it can see your screen, hold contextual conversations, listen to your voice, and respond using highly realistic neural text-to-speech.

## ✨ Features

- **👀 Real-Time Screen Analysis:** Captures and analyzes your primary monitor to answer questions about what you are currently looking at.
- **🧠 Contextual Memory:** Utilizes Gemini Chat Sessions to remember ongoing conversation context.
- **🎙️ Neural Voice Engine:** Generates hyper-realistic, professional audio responses using Microsoft Edge-TTS.
- **⚡ Wake-Word Detection:** Runs a background listener—simply say **"Atlas"** to wake the assistant hands-free.
- **🖥️ Modern Desktop UI:** Features a sleek, dark-mode glassmorphism interface rendered natively via PyWebView.
- **🗣️ Instant Interruption:** Automatically cuts off ongoing audio playback if interrupted with a new voice command.

## 📋 Prerequisites

- **Python 3.10+** (Tested on Python 3.12+)
- A **Google Gemini API Key** (Free tier available via [Google AI Studio](https://aistudio.google.com/))
- A working microphone for voice input

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repository-url>
   cd ATLAS