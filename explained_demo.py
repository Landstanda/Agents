# Import just what we need for this demo
import webbrowser  # The simple, reliable way
import time       # For adding delays
import pyautogui  # For mouse control
from transformers import pipeline  # For AI capabilities

def simple_way():
    """The simple, reliable way that worked"""
    print("\nMethod 1: Simple and Reliable")
    print("This is what simple_browser.py used")
    webbrowser.open("https://www.google.com")
    return "✓ Browser opened directly!"

def test_mouse_control():
    """Demonstrate mouse control capabilities"""
    print("\nMethod 2: Mouse Control")
    print("Current mouse position:", pyautogui.position())
    
    input("Press Enter to see mouse movement (will move in a square pattern)...")
    print("Moving mouse... (move to corner to abort)")
    
    # Move in a square pattern
    moves = [
        (100, 0),   # Right
        (0, 100),   # Down
        (-100, 0),  # Left
        (0, -100)   # Up
    ]
    
    for dx, dy in moves:
        pyautogui.moveRel(dx, dy, duration=0.5)
        time.sleep(0.5)
    
    return "✓ Mouse movement completed!"

def test_ai_capabilities():
    """Demonstrate AI capabilities with sentiment analysis"""
    print("\nMethod 3: AI Capabilities")
    print("Initializing sentiment analysis model...")
    
    # Initialize the sentiment analyzer
    sentiment_analyzer = pipeline("sentiment-analysis")
    
    # Test texts with different sentiments
    texts = [
        "I love working with AI and automation!",
        "This is a challenging but interesting task.",
        "Debugging can be really frustrating sometimes."
    ]
    
    print("\nAnalyzing different texts:")
    for text in texts:
        result = sentiment_analyzer(text)
        print(f"\nText: '{text}'")
        print(f"Sentiment: {result[0]['label']}")
        print(f"Confidence: {result[0]['score']:.2%}")
    
    return "✓ AI analysis completed!"

def explained_test():
    """Explaining what the one-line test was trying to do"""
    print("\nWhat our earlier tests were checking:")
    print("1. Can we import the libraries?")
    print("2. Can we get screen size?")
    print("3. Can we wait for user input?")
    
    # Add a small delay for readability
    time.sleep(1)
    return "✓ Basic imports and screen info work!"

def main():
    print("=== Enhanced Explanation Demo ===")
    print("This demo shows all our tested capabilities")
    print("Note: Move mouse to any corner to abort mouse movements")
    
    # Set up PyAutoGUI safety features
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
    
    try:
        # Browser demo
        input("\nPress Enter to try browser opening...")
        result1 = simple_way()
        print(result1)
        
        # Mouse control demo
        input("\nPress Enter to try mouse control...")
        result2 = test_mouse_control()
        print(result2)
        
        # AI capabilities demo
        input("\nPress Enter to try AI capabilities...")
        result3 = test_ai_capabilities()
        print(result3)
        
        # Original test explanation
        input("\nPress Enter to see what the original tests were checking...")
        result4 = explained_test()
        print(result4)
        
        print("\nKey Lessons:")
        print("1. Simple is often better (like with browser control)")
        print("2. Mouse automation works well with X11")
        print("3. AI can analyze text sentiment effectively")
        print("4. Always include safety features in automation")
        
    except Exception as e:
        print(f"\nError during demo: {str(e)}")

if __name__ == "__main__":
    main() 