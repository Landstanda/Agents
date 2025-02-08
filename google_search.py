import webbrowser
import pyautogui
import time

def google_search():
    # Open Google in the default browser
    webbrowser.open("https://www.google.com")
    
    # Wait for the page to load
    time.sleep(3)  # Adjust this delay based on your internet speed
    
    # Google's search box is automatically focused, so we can just type
    pyautogui.write("weather")
    
    # Optional: Press enter to perform the search
    pyautogui.press('enter')

def main():
    print("=== Google Search Demo ===")
    print("This script will:")
    print("1. Open Google in your default browser")
    print("2. Type 'weather' in the search field")
    print("3. Perform the search")
    print("\nNote: Keep your mouse in a corner to abort if needed")
    
    # Set up PyAutoGUI safety features
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
    
    try:
        input("Press Enter to start the demo...")
        google_search()
        print("\nSearch completed successfully!")
        
    except Exception as e:
        print(f"\nError during demo: {str(e)}")

if __name__ == "__main__":
    main() 