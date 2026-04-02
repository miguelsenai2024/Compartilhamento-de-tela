import os
import sys
import urllib.request
import zipfile
import subprocess

TOOLS_DIR = "tools"
ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
SCRCPY_URL = "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64-v2.4.zip"

def download_file(url, filename):
    print(f"Baixando {filename}...")
    urllib.request.urlretrieve(url, filename)
    print("Download concluído.")

def extract_zip(zip_path, extract_to):
    print(f"Extraindo {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print("Extração concluída.")

def install_python_requirements():
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(req_path):
        print("Instalando bibliotecas Python...")
        subprocess.call([sys.executable, "-m", "pip", "install", "-r", req_path])

def setup_tools():
    os.makedirs(TOOLS_DIR, exist_ok=True)

    adb_zip = os.path.join(TOOLS_DIR, "adb.zip")
    scrcpy_zip = os.path.join(TOOLS_DIR, "scrcpy.zip")

    # Download ADB
    if not os.path.exists(os.path.join(TOOLS_DIR, "platform-tools")):
        download_file(ADB_URL, adb_zip)
        extract_zip(adb_zip, TOOLS_DIR)

    # Download scrcpy
    if not os.path.exists(os.path.join(TOOLS_DIR, "scrcpy")):
        download_file(SCRCPY_URL, scrcpy_zip)
        extract_zip(scrcpy_zip, TOOLS_DIR)

def run_project():
    adb_path = os.path.join(TOOLS_DIR, "platform-tools", "adb.exe")
    scrcpy_path = None

    # encontrar scrcpy.exe
    for root, dirs, files in os.walk(TOOLS_DIR):
        if "scrcpy.exe" in files:
            scrcpy_path = os.path.join(root, "scrcpy.exe")
            break

    if not scrcpy_path:
        print("Erro: scrcpy não encontrado.")
        return
    os.system(f'"{adb_path}" start-server')
    os.system(f'"{adb_path}" devices')
    os.system(f'"{scrcpy_path}" --stay-awake')

if __name__ == "__main__":
    print("=== SETUP AUTOMÁTICO ===")

    install_python_requirements()
    setup_tools()

    print("\nTudo pronto!")
    run_project()
