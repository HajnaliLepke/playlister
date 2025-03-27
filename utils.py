import re
import os
import shutil
import time
import logging


def sanitize_filename(logger: logging.Logger, name: str, max_length: int = 100) -> str:
    main_start_time = time.time()
    received_name = name
    # Remove any forbidden characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores
    name = name.strip().replace(' ', '_')
    # Keep only alphanumerics, dashes and underscores
    name = re.sub(r'[^A-Za-z0-9_\-]', '', name)

    main_end_time = time.time()
    main_elapsed_time = main_end_time - main_start_time
    logger.info(
        f"Sanitized Filename from {received_name} to {name}, időtartam: {main_elapsed_time:.2f} másodperc")
    return name[:max_length]


def empty_folder(logger: logging.Logger, folder_name: str) -> None:
    main_start_time = time.time()
    logger.info(f"Emptying folder: {folder_name}")
    for filename in os.listdir(folder_name):
        file_path = os.path.join(folder_name, filename)
        logger.info(f"Deleting file: {file_path}")

        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.info('Failed to delete %s. Reason: %s' % (file_path, e))
            continue
        logger.info(f"Deleted file: {file_path}")

    main_end_time = time.time()
    main_elapsed_time = main_end_time - main_start_time
    logger.info(
        f"Folder emptied: {folder_name}, időtartam: {main_elapsed_time:.2f} másodperc")


def check_or_create_folder(folder_name: str):
    """
    Ellenőrzi, hogy létezik-e az 'folder_name' mappa.
    Ha nem létezik, létrehozza.

    Returns:
        str: Az 'folder_name' mappa elérési útja
    """
    folder_path = folder_name

    # Ellenőrizzük, hogy létezik-e a mappa
    if not os.path.exists(folder_path):
        # Ha nem létezik, létrehozzuk
        os.makedirs(folder_path)
        # print(f"Az '{folder_path}' mappa létrehozva.")
    else:
        pass
        # print(f"Az '{folder_path}' mappa már létezik.")

    return folder_path
