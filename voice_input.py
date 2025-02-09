#!/usr/bin/env python3

import speech_recognition as sr
from pynput import keyboard
from pynput.keyboard import Controller
import threading

class VoiceInputHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.keyboard = Controller()
        self.is_listening = False
        self.listen_thread = None
        self.running = True
        
    def listen_and_type(self):
        """Listen and type in real-time"""
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source, phrase_time_limit=1)
                    text = self.recognizer.recognize_google(audio)
                    if text:
                        self.keyboard.type(text + " ")
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    continue
                    
    def toggle_listening(self):
        """Toggle speech recognition"""
        self.is_listening = not self.is_listening
        
        if self.is_listening:
            self.listen_thread = threading.Thread(target=self.listen_and_type)
            self.listen_thread.start()
        else:
            if self.listen_thread:
                self.listen_thread.join()
                
    def on_press(self, key):
        """Handle key press events"""
        try:
            if key == keyboard.Key.f8:
                self.toggle_listening()
            elif key == keyboard.Key.esc:
                self.running = False
                self.is_listening = False
                if self.listen_thread:
                    self.listen_thread.join()
                return False
        except AttributeError:
            pass
            
    def run(self):
        """Main loop"""
        print("F8: Start/Stop | Esc: Exit")
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

if __name__ == "__main__":
    handler = VoiceInputHandler()
    handler.run() 