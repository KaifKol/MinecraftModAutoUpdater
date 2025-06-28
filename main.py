import os
import requests
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import re
import sys
import shutil

class ModrinthModUpdater:
    def __init__(self):
        self.api_base = "https://api.modrinth.com/v2"
        self.use_gui = sys.stdin.isatty()
        if self.use_gui:
            self.root = tk.Tk()
            self.mods_dir = tk.StringVar(value=str(Path("mods").absolute()))
            self.minecraft_version = tk.StringVar(value="1.21.6")
            self.loader = tk.StringVar(value="fabric")
            self.setup_gui()
        else:
            self.mods_dir = str(Path("mods").absolute())
            self.minecraft_version = "1.21.6"
            self.loader = "fabric"
            self.run_console()

    def setup_gui(self):
        self.root.title("Обновлятор модов для Minecraft")
        self.root.geometry("800x650")
        self.root.resizable(True, True)

        # Minecraft version selection
        ttk.Label(self.root, text="Версия Minecraft:", font=("Arial", 12)).pack(pady=10)
        version_entry = ttk.Entry(self.root, textvariable=self.minecraft_version, width=20)
        version_entry.pack(pady=5)

        # Loader selection
        ttk.Label(self.root, text="Ядро для модов:", font=("Arial", 12)).pack(pady=10)
        loader_combo = ttk.Combobox(self.root, textvariable=self.loader, values=["fabric", "forge"], state="readonly")
        loader_combo.pack(pady=5)

        # Mods directory selection
        ttk.Label(self.root, text="Папка с модами:", font=("Arial", 12)).pack(pady=10)
        dir_frame = ttk.Frame(self.root)
        dir_frame.pack(pady=5, fill=tk.X, padx=10)
        ttk.Entry(dir_frame, textvariable=self.mods_dir, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(dir_frame, text="Выбрать", command=self.browse_directory).pack(side=tk.LEFT, padx=5)

        # Progress text
        self.progress_text = tk.Text(self.root, height=15, width=80, font=("Arial", 10))
        self.progress_text.pack(pady=10)

        # Update button with label
        ttk.Label(self.root, text="Обновить моды для выбранного ядра:", font=("Arial", 12)).pack(pady=5)
        ttk.Button(self.root, text="Скачать и обновить", command=self.start_update, style="TButton").pack(pady=10)
        
        # Style for button
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 12, "bold"), padding=10)

    def browse_directory(self):
        selected_dir = filedialog.askdirectory(initialdir=self.mods_dir.get() if self.use_gui else self.mods_dir, 
                                             title="Выберите папку с модами")
        if selected_dir:
            if self.use_gui:
                self.mods_dir.set(selected_dir)
            else:
                self.mods_dir = selected_dir

    def log(self, message):
        if self.use_gui:
            self.progress_text.insert(tk.END, message + "\n")
            self.progress_text.see(tk.END)
            self.root.update()
        else:
            print(message)

    def get_mod_info(self, filename):
        """Extract mod slug from filename with special case for Fabric API"""
        name = filename.replace(".disabled", "").replace(".jar", "")
        name = re.sub(r'[-_]\d+\.\d+\.\d+[-_].*', '', name)
        name = re.sub(r'[-_]\d+\.\d+\.\d+', '', name)
        if "fabric-api" in name.lower():
            return "fabric"
        return name.lower().replace(" ", "-")

    def get_mod_id(self, slug):
        """Get mod ID from Modrinth API using slug"""
        try:
            self.log(f"Поиск мода по slug: {slug}")
            response = requests.get(f"{self.api_base}/search?query={slug}&facets=[[\"project_type:mod\"]]")
            response.raise_for_status()
            data = response.json()
            if data["hits"]:
                mod_id = data["hits"][0]["project_id"]
                self.log(f"Найден мод ID: {mod_id} для {slug}")
                return mod_id
            self.log(f"Мод '{slug}' не найден на Modrinth")
            return None
        except requests.RequestException as e:
            self.log(f"Ошибка при поиске мода '{slug}': {e}")
            return None

    def get_latest_version(self, mod_id, mc_version):
        """Get latest compatible version for the mod"""
        try:
            loader = self.loader.get() if self.use_gui else self.loader
            self.log(f"Поиск версий для мода {mod_id} под Minecraft {mc_version} и ядро {loader}")
            response = requests.get(
                f"{self.api_base}/project/{mod_id}/version",
                params={"game_versions": f'["{mc_version}"]', "loaders": f'["{loader}"]'}
            )
            response.raise_for_status()
            versions = response.json()
            if versions:
                self.log(f"Найдена версия: {versions[0]['version_number']}")
                return versions[0]
            self.log(f"Нет совместимой версии для мода с ID {mod_id} для Minecraft {mc_version} и ядра {loader}")
            return None
        except requests.RequestException as e:
            self.log(f"Ошибка при получении версий для мода {mod_id}: {e}")
            return None

    def download_mod(self, version_data):
        """Download mod file"""
        try:
            file_url = version_data["files"][0]["url"]
            filename = version_data["files"][0]["filename"]
            self.log(f"Скачивание: {filename} с {file_url}")
            response = requests.get(file_url)
            response.raise_for_status()
            return filename, response.content
        except requests.RequestException as e:
            self.log(f"Ошибка при скачивании мода: {e}")
            return None, None

    def start_update(self):
        """Main update process"""
        self.log("Запуск процесса обновления модов...")

        mc_version = self.minecraft_version.get().strip() if self.use_gui else self.minecraft_version.strip()
        if not mc_version:
            self.log("Ошибка: Укажите версию Minecraft!")
            if self.use_gui:
                messagebox.showerror("Ошибка", "Укажите версию Minecraft!")
            return

        mods_path = Path(self.mods_dir.get() if self.use_gui else self.mods_dir)
        if not mods_path.exists():
            self.log(f"Ошибка: Папка {mods_path} не найдена!")
            if self.use_gui:
                messagebox.showerror("Ошибка", f"Папка {mods_path} не найдена!")
            return

        # Create not_found and old directories
        not_found_path = mods_path / "not_found"
        old_path = mods_path / "old"
        not_found_path.mkdir(exist_ok=True)
        old_path.mkdir(exist_ok=True)

        mod_files = [f for f in mods_path.iterdir() if f.suffix in (".jar", ".disabled") and f.parent == mods_path]
        if not mod_files:
            self.log(f"В папке {mods_path} не найдено модов!")
            if self.use_gui:
                messagebox.showinfo("Информация", f"В папке {mods_path} не найдено модов!")
            return

        updated = 0
        failed = 0

        for mod_file in mod_files:
            self.log(f"\nОбрабатывается {mod_file.name}...")
            is_disabled = mod_file.suffix == ".disabled"
            
            slug = self.get_mod_info(mod_file.name)
            mod_id = self.get_mod_id(slug)
            
            if not mod_id:
                # Move to not_found
                shutil.move(mod_file, not_found_path / mod_file.name)
                self.log(f"Мод {mod_file.name} перемещён в {not_found_path}")
                failed += 1
                continue

            version_data = self.get_latest_version(mod_id, mc_version)
            if not version_data:
                # Move to not_found
                shutil.move(mod_file, not_found_path / mod_file.name)
                self.log(f"Мод {mod_file.name} перемещён в {not_found_path}")
                failed += 1
                continue

            new_filename, file_content = self.download_mod(version_data)
            if not file_content:
                # Move to not_found
                shutil.move(mod_file, not_found_path / mod_file.name)
                self.log(f"Мод {mod_file.name} перемещён в {not_found_path}")
                failed += 1
                continue

            # Move old mod to old directory
            shutil.move(mod_file, old_path / mod_file.name)
            self.log(f"Старая версия {mod_file.name} перемещена в {old_path}")

            new_filename = new_filename if not is_disabled else new_filename + ".disabled"
            new_path = mods_path / new_filename

            with open(new_path, "wb") as f:
                f.write(file_content)
            
            self.log(f"Успешно обновлён {mod_file.name} до {new_filename}")
            updated += 1

        self.log(f"\nОбновление завершено! Обновлено: {updated}, Не найдено/Ошибок: {failed}")
        if self.use_gui:
            messagebox.showinfo("Готово", f"Обновление завершено!\nОбновлено: {updated}\nНе найдено/Ошибок: {failed}")

    def run_console(self):
        print("Обновлятор модов для Minecraft (консольный режим)")
        mc_version = input("Введите версию Minecraft (например, 1.21.6): ").strip() or "1.21.6"
        loader = input("Введите ядро для модов (fabric/forge, Enter для fabric): ").strip().lower() or "fabric"
        mods_dir = input("Введите путь к папке с модами (Enter для ./mods): ").strip() or str(Path("mods").absolute())
        self.minecraft_version = mc_version
        self.loader = loader
        self.mods_dir = mods_dir
        print("Нажмите Enter, чтобы скачать и обновить моды...")
        input()
        self.start_update()

    def run(self):
        if self.use_gui:
            self.root.mainloop()
        else:
            self.run_console()

if __name__ == "__main__":
    updater = ModrinthModUpdater()
    updater.run()