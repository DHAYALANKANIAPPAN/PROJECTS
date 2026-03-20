
from pathlib import Path

testfolder = Path(r'C:\Users\DHAYA\Desktop\New folder')

mapping = {
    "Images": [".jpg", ".png"],
    "Documents": [".pdf", ".docx", ".txt"],
    "Videos": [".mp4", ".mkv"],
    "Security": [".log", ".pcap", ".exe"]
}
def move_file(file, subfolder):
    destination = subfolder / file.name
    counter = 1

    while destination.exists():
        destination = subfolder / f"{file.stem}_{counter}{file.suffix}"
        counter += 1

    file.rename(destination)

def safe_move(file, subfolder):
    try:
        move_file(file, subfolder)
        return True
    except Exception as e:
        print(f"Error moving {file.name}: {e}")
        return False

for file in testfolder.iterdir():
    if file.is_file():
        ext = file.suffix.lower()
        moved = False

        if ext == "":
           subfolder = testfolder / "NoExtension"
           subfolder.mkdir(exist_ok=True)

           if safe_move(file, subfolder):
            print(f"Moved {file.name} → NoExtension/")
           moved = True
           continue

        for folder, extensions in mapping.items():
            if ext in extensions:
                subfolder = testfolder / folder
                subfolder.mkdir(exist_ok=True)

                if safe_move(file, subfolder):
                 print(f"Moved {file.name} → {folder}/")
                moved = True
                break

        if not moved:
            subfolder = testfolder / "Others"
            subfolder.mkdir(exist_ok=True)

            if safe_move(file, subfolder):
             print(f"Moved {file.name} → Others/")
