import random
import os
import sys

# ------------------- COLORS CROSS-PLATFORM -------------------
if sys.platform.startswith("win"):
    # Windows: enable ANSI escape sequences
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# ------------------- ENCODER / DECODER -------------------
def _f2l_(s):
    return s[2:] + s[:2] if len(s) > 2 else s

def _forch_(s):
    mapping = {"a":"@", "c":"(", "h":"&", "i":"!", "o":"*", "r":"/", "s":"$", "x":"+"}
    return ''.join(mapping.get(ch, ch) for ch in s)

def _adchr_(s):
    if len(s) <= 4:
        return s
    rand = ''.join(chr(random.randint(97,122)) for _ in range(5))
    sub1 = _f2l_(rand)
    sub2 = rand[::-1]
    return rand + s[:4] + sub1 + s[4:] + sub2

def incode(s):
    return _adchr_(_forch_(_f2l_(s)))

def reachr(s):
    if len(s) <= 4:
        return s
    return s[5:9] + s[14:-5]

def repchr(s):
    mapping = {"@":"a","(":"c","&":"h","!":"i","*":"o","/":"r","$":"s","+":"x"}
    return ''.join(mapping.get(ch, ch) for ch in s)

def achr(s):
    return s[-2:] + s[:-2] if len(s) >= 2 else s

def decode_word(s):
    if len(s) <= 2:
        return repchr(s)
    return achr(repchr(reachr(s)))

# ------------------- FILE OPERATIONS -------------------
def save_file(text):
    path = input(f"{Colors.CYAN}Enter filename to save (.txt added if not present): {Colors.RESET}").strip()
    if not path:
        print(f"{Colors.RED}Cancelled save.{Colors.RESET}")
        return
    if not path.endswith(".txt"):
        path += ".txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{Colors.GREEN}Saved to {path}{Colors.RESET}")

def load_file():
    path = input(f"{Colors.CYAN}Enter filename to load: {Colors.RESET}").strip()
    if not os.path.exists(path):
        print(f"{Colors.RED}File not found!{Colors.RESET}")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"{Colors.GREEN}Loaded from {path}{Colors.RESET}")
    return content

# main functions

def encode_text(text):
    words = text.split()
    return ' '.join(incode(w) for w in words)

def decode_text(text):
    text = text.strip()
    words = text.split()
    return ' '.join(decode_word(w) for w in words)

# ------------------- CLI -------------------
def main():
    while True:
        print(f"\n{Colors.HEADER}--- Options ---{Colors.RESET}")
        print(f"{Colors.YELLOW}1{Colors.RESET}. Encode message")
        print(f"{Colors.YELLOW}2{Colors.RESET}. Decode message")
        print(f"{Colors.YELLOW}3{Colors.RESET}. Load from file")
        print(f"{Colors.YELLOW}4{Colors.RESET}. Save output to file")
        print(f"{Colors.YELLOW}5{Colors.RESET}. Exit")
        choice = input(f"{Colors.CYAN}Enter option (1-5): {Colors.RESET}").strip()

        if choice == "1":
            text = input(f"{Colors.CYAN}Enter text to encode: {Colors.RESET}").strip()
            words = text.split()
            out = ' '.join(incode(w) for w in words)
            print(f"\n{Colors.YELLOW}Encoded Output:{Colors.RESET}\n{Colors.BLUE}{out}{Colors.RESET}")
        elif choice == "2":
            text = input(f"{Colors.CYAN}Enter text to decode: {Colors.RESET}").strip()
            words = text.split()
            out = ' '.join(decode_word(w) for w in words)
            print(f"\n{Colors.YELLOW}Decoded Output:{Colors.RESET}\n{Colors.GREEN}{out}{Colors.RESET}")
        elif choice == "3":
            loaded = load_file()
            if loaded:
                print(f"\n{Colors.HEADER}Loaded Content:{Colors.RESET}\n{loaded}")
        elif choice == "4":
            text = input(f"{Colors.CYAN}Enter text to save: {Colors.RESET}").strip()
            save_file(text)
        elif choice == "5":
            print(f"{Colors.RED}Exiting program...{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Invalid choice! Try again.{Colors.RESET}")

if __name__ == "__main__":
    main()
