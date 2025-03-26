import re
import os
import shutil


def sanitize_filename(name: str, max_length: int = 100) -> str:
    # Remove any forbidden characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores
    name = name.strip().replace(' ', '_')
    # Keep only alphanumerics, dashes and underscores
    name = re.sub(r'[^A-Za-z0-9_\-]', '', name)
    return name[:max_length]


def empty_folder(folder_name: str) -> None:
    for filename in os.listdir(folder_name):
        file_path = os.path.join(folder_name, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
