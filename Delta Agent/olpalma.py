import requests
import json
import re
import os
import shutil
import subprocess
import traceback

# === CONFIG ===
API_URL = "https://orloxmyctxxhtotvxeyu.supabase.co/functions/v1/ai-proxy"
API_KEY = "kf_live_LchIHukNIxxMYi5FmcfRj9v6aSR9BVuSdUmE9LCy"
MODEL = "gpt-4o-mini"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_MESSAGE = """
You are an AI assistant running inside a Python terminal environment.

You may speak normally, answer questions, explain things, and hold conversations.
You must NEVER create, delete, run, list, or read files unless the USER explicitly requests it.

When the user explicitly asks for a file, folder, delete, run, list, or read operation, you MUST output ONLY the exact command formats below.
When the user does NOT request file operations, you MUST speak normally and produce NO command blocks.

---------------------------------------
ALLOWED COMMAND FORMATS (USE EXACTLY)
---------------------------------------

Create a file:
>>>FILE: filename.ext
file content here
>>>

Create a folder:
fol>>>foldername

Create a file inside a folder:
>>>foldername:filename.ext
file content here
>>>

Delete a file:
>>>del: filename.ext

Delete a folder:
delfol>>>foldername

Run a file:
>>>run: filename.ext

List all files and folders:
>>>ls

List contents of a folder:
>>>ls.foldername
>>>ls.folder1/folder2

Read a file:
>>>cat: filename.ext
>>>cat: foldername/filename.ext

---------------------------------------
STRICT RULES
---------------------------------------

1. You MUST speak normally unless the user explicitly requests file operations.
2. You MUST output command blocks ONLY when the user explicitly asks for them.
3. When outputting command blocks:
   - No explanations.
   - No comments.
   - No markdown.
   - No text before or after the commands.
4. Every file block MUST end with >>> on its own line.
5. The FIRST characters of a file-operation response MUST be one of:
   >>>FILE:
   >>>run:
   >>>del:
   delfol>>>
   fol>>>
   >>>foldername:
   >>>ls
   >>>ls.
   >>>cat:
6. No spaces before >>>.
7. No extra text, no greetings, no summaries, no apologies.
8. If multiple commands are needed, output them in sequence with NO extra text between them.
9. NEVER invent filenames. If unclear, ask the user.
10. NEVER create files automatically. Only when the user explicitly asks.
"""

# === REGEX PATTERNS ===
FILE_BLOCK_PATTERN = re.compile(
    r">>>FILE:\s*(.*?)\s*\n(.*?)\n>>>",
    re.DOTALL
)

FOLDER_PATTERN = re.compile(r"fol>>>([A-Za-z0-9_\-\/]+)")

FOLDER_FILE_PATTERN = re.compile(
    r">>>([A-Za-z0-9_\-\/]+):([A-Za-z0-9_\-\.]+)\s*\n(.*?)\n>>>",
    re.DOTALL
)

DEL_PATTERN = re.compile(r">>>del:\s*(.+)")
RUN_PATTERN = re.compile(r">>>run:\s*(.+)")
DELFOL_PATTERN = re.compile(r"delfol>>>(.+)")
LS_ALL_PATTERN = re.compile(r">>>ls$")
LS_FOLDER_PATTERN = re.compile(r">>>ls\.(.+)")
CAT_PATTERN = re.compile(r">>>cat:\s*(.+)")


# === SAFE PATH ===
def safe_path(path: str):
    if ":" in path or path.startswith("/") or path.startswith("\\"):
        return None
    if ".." in path:
        return None
    joined = os.path.join(BASE_DIR, path)
    norm = os.path.normpath(joined)
    if not norm.startswith(BASE_DIR):
        return None
    return norm


# === SUPABASE AI CALL ===
def call_ai(messages):
    try:
        payload = {"messages": messages}
        headers = {
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
        }
        resp = requests.post(API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        if "message" in data:
            return data["message"]["content"]

        return str(data)

    except Exception:
        traceback.print_exc()
        return ""


# === FILE OPS ===
def write_files(files):
    for filename, content in files:
        safe = safe_path(filename)
        if not safe:
            print(f"[BLOCKED] Unsafe file path: {filename}")
            continue
        os.makedirs(os.path.dirname(safe) or BASE_DIR, exist_ok=True)
        with open(safe, "w", encoding="utf-8") as f:
            f.write(content.rstrip())
        print(f"Agent created file: {filename}")


def write_folders(folders):
    for folder in folders:
        safe = safe_path(folder)
        if not safe:
            print(f"[BLOCKED] Unsafe folder path: {folder}")
            continue
        os.makedirs(safe, exist_ok=True)
        print(f"Agent created folder: {folder}")


def write_folder_files(folder_files):
    for folder, filename, content in folder_files:
        safe_folder = safe_path(folder)
        if not safe_folder:
            print(f"[BLOCKED] Unsafe folder path: {folder}")
            continue
        os.makedirs(safe_folder, exist_ok=True)
        safe_file = os.path.join(safe_folder, filename)
        with open(safe_file, "w", encoding="utf-8") as f:
            f.write(content.rstrip())
        print(f"Agent created file: {folder}/{filename}")


def delete_files(paths):
    for raw in paths:
        safe = safe_path(raw.strip())
        if not safe:
            print(f"[BLOCKED] Unsafe delete: {raw}")
            continue
        if os.path.exists(safe):
            os.remove(safe)
            print(f"Agent deleted file: {raw.strip()}")
        else:
            print(f"Agent could not delete (not found): {raw.strip()}")


def delete_folders(paths):
    for raw in paths:
        folder = raw.strip()
        safe = safe_path(folder)
        if not safe:
            print(f"[BLOCKED] Unsafe folder delete: {folder}")
            continue
        if os.path.isdir(safe):
            shutil.rmtree(safe)
            print(f"Agent deleted folder: {folder}")
        else:
            print(f"Agent could not delete folder (not found): {folder}")


def run_files(paths):
    for raw in paths:
        safe = safe_path(raw.strip())
        if not safe or not os.path.exists(safe):
            print(f"Agent could not run (not found): {raw.strip()}")
            continue
        print(f"Agent ran file: {raw.strip()}")
        result = subprocess.run(["python", safe], capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)


def list_all():
    items = os.listdir(BASE_DIR)
    listing = "\n".join(f"- {i}" for i in items)
    print("AI:", listing)
    return listing


def list_folder(folder):
    safe = safe_path(folder)
    if not safe or not os.path.isdir(safe):
        print(f"AI: Folder not found: {folder}")
        return f"Folder not found: {folder}"

    items = os.listdir(safe)
    listing = "\n".join(f"- {i}" for i in items)
    print(f"AI (folder {folder}):\n{listing}")
    return listing


def cat_file(path):
    safe = safe_path(path)
    if not safe or not os.path.isfile(safe):
        print(f"AI: File not found: {path}")
        return f"File not found: {path}"

    with open(safe, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"AI (cat {path}):\n{content}")
    return content


# === MAIN LOOP ===
def main():
    print("=== Supabase AI Terminal ===")
    print("Base dir:", BASE_DIR)
    print("AI can speak normally. File ops only when requested.\n")

    messages = [{"role": "system", "content": SYSTEM_MESSAGE}]

    while True:
        try:
            user_input = input("You: ")
        except KeyboardInterrupt:
            break

        messages.append({"role": "user", "content": user_input})
        response = call_ai(messages)

        if not response:
            print("[NO RESPONSE]")
            continue

        # Detect commands
        files = FILE_BLOCK_PATTERN.findall(response)
        folders = FOLDER_PATTERN.findall(response)
        folder_files = FOLDER_FILE_PATTERN.findall(response)
        deletes = DEL_PATTERN.findall(response)
        runs = RUN_PATTERN.findall(response)
        delete_fols = DELFOL_PATTERN.findall(response)
        ls_all = LS_ALL_PATTERN.findall(response)
        ls_folders = LS_FOLDER_PATTERN.findall(response)
        cat_files = CAT_PATTERN.findall(response)

        # If no commands → normal speech
        if not (files or folders or folder_files or deletes or runs or delete_fols or ls_all or ls_folders or cat_files):
            print("AI:", response)
        else:
            write_folders(folders)
            write_files(files)
            write_folder_files(folder_files)
            delete_files(deletes)
            delete_folders(delete_fols)
            run_files(runs)

            # ls
            if ls_all:
                listing = list_all()
                messages.append({"role": "assistant", "content": listing})

            for folder in ls_folders:
                listing = list_folder(folder)
                messages.append({"role": "assistant", "content": listing})

            # cat
            for path in cat_files:
                content = cat_file(path)
                messages.append({"role": "assistant", "content": content})

        messages.append({"role": "assistant", "content": response})
        print()


if __name__ == "__main__":
    main()
