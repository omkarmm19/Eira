import asyncio
import datetime
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
import edge_tts
import pygame
import pyautogui
import requests
import speech_recognition as sr
from googleapiclient.discovery import build
from PIL import Image, ImageTk, ImageSequence

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

if not OPENROUTER_API_KEY:
    print("CRITICAL: OPENROUTER_API_KEY not set. AI chat features disabled.")
if not (GOOGLE_API_KEY and SEARCH_ENGINE_ID):
    print("CRITICAL: Google API Key or Search Engine ID not set. Google Search disabled.")

is_speaking = False
listener = sr.Recognizer()

async def get_ai_response(prompt):
    """Fetches a response from the OpenRouter AI model for conversation."""
    if not OPENROUTER_API_KEY:
        return "My AI brain isn't configured."
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    data = {"model": "mistralai/mistral-7b-instruct", "messages": [{"role": "user", "content": prompt}]}
    try:
        response = await asyncio.to_thread(requests.post, "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"API error: {e}")
        return "Sorry, I had a brain freeze..."

async def speak(text):
    """Synthesizes text to speech and plays it with pygame."""
    global is_speaking
    if is_speaking or not text: return
    is_speaking = True
    print("AI:", text)
    filename = f"output_{int(time.time() * 1000)}.mp3"
    try:
        communicate = edge_tts.Communicate(text=text, voice="en-US-JennyNeural", rate="-10%", pitch="+30Hz")
        await communicate.save(filename)
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Error during speech: {e}")
    finally:
        if 'pygame' in locals() and pygame.mixer.get_init():
             pygame.mixer.music.unload()
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except PermissionError:
                print(f"Could not delete {filename}, it's still in use.")
        is_speaking = False

def listen_command():
    """Listens for a voice command and returns it as text."""
    with sr.Microphone() as source:
        print("Listening...")
        listener.adjust_for_ambient_noise(source)
        try:
            audio = listener.listen(source, phrase_time_limit=5)
            command = listener.recognize_google(audio).lower()
            print("You:", command)
            return command
        except Exception:
            return ""

async def search_google(command):
    if not (GOOGLE_API_KEY and SEARCH_ENGINE_ID):
        await speak("My Google Search is not configured.")
        return
    query = command.replace("google search", "").replace("search for", "").strip()
    await speak(f"Searching Google for {query}")
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = await asyncio.to_thread(service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=1).execute)
        if 'items' in res:
            item = res['items'][0]
            snippet = item.get('snippet', 'No snippet available.').replace("\n", " ")
            await speak(f"According to Google: {snippet}")
        else:
            await speak(f"Sorry, I couldn't find any results for {query}.")
    except Exception as e:
        print(f"Google Search Error: {e}")
        await speak("I ran into an error while searching Google.")

async def open_any_website(command):
    site_name = command.split("open", 1)[-1].strip().replace(" ", "")
    if site_name:
        url = f"https://www.{site_name}.com"
        await speak(f"Opening {site_name}")
        await asyncio.to_thread(webbrowser.open_new_tab, url)
        return True
    return False

async def close_current_tab():
    await speak("Closing the tab.")
    pyautogui.hotkey('command', 'w') 

class AssistantGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EIRA AI")
        self.root.geometry("450x400")
        self.root.resizable(False, False)
        self.root.wm_attributes("-topmost", True)
        self.canvas = tk.Canvas(self.root, width=450, height=400, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        try:
            gif_path = self.resource_path("eira.gif")
            gif = Image.open(gif_path)
            frame_size = (450, 280)
            self.frames = [ImageTk.PhotoImage(img.resize(frame_size, Image.Resampling.LANCZOS).convert('RGBA')) for img in ImageSequence.Iterator(gif)]
            self.gif_index = 0
            self.bg_image = self.canvas.create_image(0, 0, anchor='nw', image=self.frames[0])
            self.animate()
        except Exception as e:
            print(f"Warning: eira.gif not found. {e}")

        self.chat_log = tk.Text(self.root, bg="#000000", fg="sky blue", font=("Consolas", 9), wrap='word', bd=0, state=tk.DISABLED)
        self.chat_log.place(x=0, y=280, width=450, height=90)
        self.entry = tk.Entry(self.root, font=("Segoe UI", 10), bg="#1a1a1a", fg="white", bd=3, insertbackground='white')
        self.entry.place(x=10, y=375, width=350, height=25)
        self.entry.bind("<Return>", self.send_text)
        send_button = tk.Button(self.root, text="Send", command=self.send_text, bg="#444444", fg="white", relief='raised', font=("Segoe UI", 9, "bold"))
        send_button.place(x=370, y=375, width=70, height=25)
        self.root.bind("<F2>", lambda e: threading.Thread(target=self.listen_voice, daemon=True).start())
        self.add_text_to_gui("[System] EIRA AI initialized. Press F2 to speak.")
        threading.Thread(target=lambda: asyncio.run(speak("I am online and ready.")), daemon=True).start()

    def resource_path(self, relative_path):
        try: base_path = sys._MEIPASS
        except AttributeError: base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def animate(self):
        self.canvas.itemconfig(self.bg_image, image=self.frames[self.gif_index])
        self.gif_index = (self.gif_index + 1) % len(self.frames)
        self.root.after(100, self.animate)

    def add_text_to_gui(self, text):
        def update_text():
            self.chat_log.config(state=tk.NORMAL)
            self.chat_log.insert(tk.END, text + "\n")
            self.chat_log.config(state=tk.DISABLED)
            self.chat_log.see(tk.END)
        self.root.after(0, update_text)

    def send_text(self, event=None):
        user_input = self.entry.get()
        if user_input:
            self.entry.delete(0, tk.END)
            self.add_text_to_gui(f"You: {user_input}")
            threading.Thread(target=lambda: asyncio.run(self.handle_command(user_input)), daemon=True).start()

    def listen_voice(self):
        self.add_text_to_gui("[System] Listening...")
        command = listen_command()
        if command:
            self.add_text_to_gui(f"You: {command}")
            threading.Thread(target=lambda: asyncio.run(self.handle_command(command)), daemon=True).start()

    async def handle_command(self, command):
        """Processes and routes user commands."""
        if "google search" in command or "search for" in command:
            await search_google(command)
        elif "open" in command:
            await open_any_website(command)
        elif "close tab" in command:
            await close_current_tab()
        else: 
            self.add_text_to_gui("[System] Thinking...")
            reply = await get_ai_response(command)
            self.add_text_to_gui("AI: " + reply)
            await speak(reply)

def main():
    root = tk.Tk()
    app = AssistantGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()