# ATLAS Operator: Vision & Desktop AI Assistant

ATLAS is a fast, modular, and autonomous personal AI desktop operator powered by **Gemini 3.1 Flash-Lite**. Built on a native 60 FPS CustomTkinter UI, ATLAS features a zero-latency Instant Reflex Router, a custom Relative-Peak Voice Activity Detector (VAD), and a Vision-Action screen agent that can autonomously locate and interact with any UI element on your monitor.

## ✨ Key Features

* **Autonomous Vision-Action Agent:** Takes a screenshot, visually locates any button, input box, or chat using normalized coordinates, draws a targeting reticle, and interacts via mouse and keyboard automatically.
* **Instant Local Reflex Router:** Everyday commands (time checks, system health, local app launching) execute in under `0.05s` with zero API latency.
* **Universal App Launcher:** Dynamically scans Windows `Get-StartApps` (including Microsoft Store/UWP apps like WhatsApp), Start Menu `.lnk` shortcuts, and Registry paths to launch *any* installed application.
* **Smart WhatsApp Integration:** Features a dedicated visual agent that brings WhatsApp to the foreground, locates the search bar, selects contacts, and sends messages safely using thread-safe native Windows clipboard injection.
* **Zero-Hang Speech Engine:** Uses a custom relative-peak VAD over raw 16kHz PCM audio frames. Automatically stops recording `0.85s-1.0s` after you finish speaking—even in noisy rooms with fan hum.
* **Resilient Model Failover:** Features a 16-model deep redundancy chain. If a Gemini endpoint experiences high traffic (e.g., `503 UNAVAILABLE`), ATLAS instantly fails over to the next available model.
* **60 FPS Cyber-HUD UI:** Native Python UI featuring an animated orbital AI core reactor, a physics-interpolated mirrored audio spectrum analyzer, procedural anti-aliased vector icons, and smooth slide-in memory/task drawers.

## 📋 Prerequisites

- **Python 3.10+** (Tested on Python 3.12+)
- A **Google Gemini API Key** (Free tier available via [Google AI Studio](https://aistudio.google.com/))
- A working microphone for voice input

## 🚀 Installation & Setup

Follow these steps to get ATLAS running on your Windows machine:

1. `git clone https://github.com/Vishal-akodiya/ATLAS.git`  
   `cd ATLAS`
2. `python -m venv venv`
3. `venv\Scripts\activate.bat`
4. `pip install -r requirements.txt`
5. Create a file named `.env` in the folder and add:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.1-flash-lite