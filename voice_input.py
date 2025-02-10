#!/usr/bin/env python3

import speech_recognition as sr
from pynput import keyboard
from pynput.keyboard import Controller, Key
import threading
import sys

class VoiceInputHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.keyboard = Controller()
        self.is_listening = False
        self.listen_thread = None
        self.running = True
        self.debug = True  # Enable debug output
        
    def listen_and_type(self):
        """Listen and type in real-time"""
        try:
            with sr.Microphone() as source:
                print("\nAdjusting for ambient noise... Please wait...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                print("Ready to listen!")
                
                while self.is_listening:
                    try:
                        print("Listening...") if self.debug else None
                        audio = self.recognizer.listen(source, phrase_time_limit=5)
                        print("Processing...") if self.debug else None
                        text = self.recognizer.recognize_google(audio)
                        if text:
                            print(f"Recognized: {text}") if self.debug else None
                            self.keyboard.type(text + " ")
                    except sr.UnknownValueError:
                        print("Could not understand audio") if self.debug else None
                        continue
                    except sr.RequestError as e:
                        print(f"Could not request results; {e}") if self.debug else None
                        continue
        except Exception as e:
            print(f"\nError initializing microphone: {e}")
            print("Please check your microphone settings and try again.")
            sys.exit(1)
                    
    def toggle_listening(self):
        """Toggle speech recognition"""
        self.is_listening = not self.is_listening
        
        if self.is_listening:
            print("\n[STARTED] Voice recognition activated!")
            self.listen_thread = threading.Thread(target=self.listen_and_type)
            self.listen_thread.start()
        else:
            print("\n[STOPPED] Voice recognition deactivated")
            if self.listen_thread:
                self.listen_thread.join()
                
    def on_press(self, key):
        """Handle key press events"""
        try:
            if key == Key.f9:  # Changed from F8 to F9
                print("Toggle key pressed!") if self.debug else None
                self.toggle_listening()
            elif key == Key.esc:
                print("\nExiting...")
                self.running = False
                self.is_listening = False
                if self.listen_thread:
                    self.listen_thread.join()
                return False
        except AttributeError:
            pass
            
    def run(self):
        """Main loop"""
        print("\nVoice Input System Ready!")
        print("------------------------")
        print("Controls:")
        print("  F9:  Start/Stop listening")
        print("  ESC: Exit")
        print("------------------------")
        
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

if __name__ == "__main__":
    try:
        handler = VoiceInputHandler()
        handler.run()
    except KeyboardInterrupt:
        print("\nExiting...") 