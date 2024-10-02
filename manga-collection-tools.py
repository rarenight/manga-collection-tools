import os
import re
import shutil
import zlib
import subprocess

def calculate_crc32(file_path):
    buf_size = 1048576
    crc32 = 0
    with open(file_path, 'rb', buffering=0) as f:
        for chunk in iter(lambda: f.read(buf_size), b''):
            crc32 = zlib.crc32(chunk, crc32)
    return f"{crc32 & 0xFFFFFFFF:08X}"

def run_7z_test(file_path):
    result = subprocess.run(['7z', 't', file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def process_files_in_directory(directory):
    log = []
    v_failures = []

    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')):
                file_path = os.path.join(root, file_name)
                # Check if file already has the [v-CRC32] tag
                match = re.search(r'\[v-([A-F0-9]{8})\]', file_name)
                if match:
                    log.append(f"File '{file_name}' already contains the CRC32 pattern '[v-{match.group(1)}]', skipping calculations.")
                    continue
                # Calculate CRC32 and create the new name pattern
                crc32 = calculate_crc32(file_path)
                log.append(f"Calculated CRC32: {crc32}")
                new_name = None
                expected_pattern = f"[v-{crc32}]"
                # If the expected pattern is not in the filename, process it
                if expected_pattern not in file_name:
                    if run_7z_test(file_path):
                        new_name = f"{file_name.rsplit('.', 1)[0]} {expected_pattern}.{file_name.rsplit('.', 1)[1]}"
                        log.append(f"7z test passed. New name will be: {new_name}")
                    else:
                        v_failures.append(file_name)
                        log.append(f"7z test failed for '{file_name}'. CRC32 will not be added.")
                else:
                    log.append(f"File already contains the pattern '{expected_pattern}'.")
                # Rename the file if new_name is set
                if new_name:
                    new_file_path = os.path.join(root, new_name)
                    os.rename(file_path, new_file_path)
                    log.append(f"Renamed '{file_name}' to '{new_name}'")
                log.append("")
    return log, v_failures

def verify_files_in_directory(directory):
    log = []
    mismatched_files = []
    matches = 0
    mismatches = 0
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')) and re.search(r'\[v-([A-F0-9]{8})\]', file_name):
                file_path = os.path.join(root, file_name)
                try:
                    # Extract CRC32 from the filename
                    match = re.search(r'\[v-([A-F0-9]{8})\]', file_name)
                    if not match:
                        raise ValueError("Pattern not found in filename.")
                    crc32_in_name = match.group(1)
                except (ValueError, IndexError) as e:
                    log.append(f"Error parsing '{file_name}': {e}")
                    mismatched_files.append(file_path)
                    continue
                # Calculate CRC32 from the file
                calculated_crc32 = calculate_crc32(file_path)
                log_entry = (f"File: {file_name}\n"
                             f"Expected CRC32: {crc32_in_name}\n"
                             f"Actual CRC32:   {calculated_crc32}\n")
                if crc32_in_name == calculated_crc32:
                    matches += 1
                    log.append(f"Match:\n{log_entry}")
                else:
                    mismatches += 1
                    mismatched_files.append({
                        'file': file_path,
                        'expected_crc32': crc32_in_name,
                        'actual_crc32': calculated_crc32
                    })
                    log.append(f"Mismatch:\n{log_entry}")
    log.append(f"\nTotal Matches: {matches}")
    log.append(f"Total Mismatches: {mismatches}")
    return log, mismatched_files

def sanitize_title(title):
    title = re.sub(r'(\d+ - .+)', '', title)  # Remove patterns like '000 - Title'
    title = re.sub(r'\{[^}]*\}', '', title)  # Remove text inside curly braces
    title = re.sub(r'\([^)]*\)', '', title)  # Remove text inside parentheses
    title = title.strip()
    return title

def get_base_title(file_name):
    # Split the file name to extract the base title before volume/chapter info
    base_title_match = re.split(r'(\d{3}|c\d{3}|v\d{2,3})', file_name, 1)
    if base_title_match:
        return sanitize_title(base_title_match[0])
    return None

def move_and_rename_files(directory):
    organized_files = {}

    for root, dirs, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.cbz', '.cbr')):
                base_title = get_base_title(file_name)
                if base_title:
                    if base_title not in organized_files:
                        organized_files[base_title] = {
                            'files': [],
                            'all_files_have_v_tag': True
                        }

                    # Check if the file already has the [v-CRC32] tag
                    has_v_tag = bool(re.search(r'\[v-([A-F0-9]{8})\]', file_name))
                    if not has_v_tag:
                        organized_files[base_title]['all_files_have_v_tag'] = False

                    organized_files[base_title]['files'].append(os.path.join(root, file_name))

    for title, info in organized_files.items():
        new_folder_name = title.strip()
        if info['all_files_have_v_tag']:
            new_folder_name += " [v]"

        new_folder_path = os.path.join(directory, new_folder_name)

        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        for file_path in info['files']:
            new_file_path = os.path.join(new_folder_path, os.path.basename(file_path))

            if os.path.exists(new_file_path):
                print(f"Skipping '{new_file_path}' as it already exists.")
                continue

            shutil.move(file_path, new_file_path)
            print(f"Moved '{file_path}' to '{new_file_path}'")

    delete_empty_folders(directory)

def delete_empty_folders(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)

if __name__ == "__main__":
    while True:
        choice = input("\n\nManga Collection Tools\nby rarenight\n\nSelect an option:\n1. Manga Hasher\n2. Manga Verifier\n3. Manga Sorter\n4. Exit\n\nEnter 1, 2, 3, or 4: ")
        if choice == '1':
            directory = input("Enter the directory to process: ")
            if os.path.isdir(directory):
                log, v_failures = process_files_in_directory(directory)
                print("\nProcessing Log:")
                for entry in log:
                    print(entry)
                if v_failures:
                    print("\nFiles that failed the 7z integrity test:")
                    for failure in v_failures:
                        print(failure)
                print("Processing completed.")
            else:
                print("Invalid directory.")
        elif choice == '2':
            directory = input("Enter the directory to verify: ")
            if os.path.isdir(directory):
                log, mismatched_files = verify_files_in_directory(directory)
                if len(mismatched_files) > 0:
                    print("\nSummary of Mismatched Files:\n")
                    for mismatch in mismatched_files:
                        print(f"File: {mismatch['file']}")
                        print(f"Expected CRC32: {mismatch['expected_crc32']}")
                        print(f"Actual CRC32: {mismatch['actual_crc32']}")
                        print("")
                    export_choice = input("Would you like to export the mismatched files to a text file? (y/n): ")
                    if export_choice.lower() == 'y':
                        export_path = input("Enter the path for the export file (e.g., C:/path/to/mismatches.txt): ")
                        try:
                            with open(export_path, 'w', encoding='utf-8') as f:
                                for mismatch in mismatched_files:
                                    f.write(f"File: {mismatch['file']}\n")
                                    f.write(f"Expected CRC32: {mismatch['expected_crc32']}\n")
                                    f.write(f"Actual CRC32: {mismatch['actual_crc32']}\n\n")
                            print(f"Mismatched files exported to {export_path}.")
                        except Exception as e:
                            print(f"Error exporting mismatched files: {e}")
                else:
                    print("\nAll files verified successfully.")
            else:
                print("Invalid directory.")
        elif choice == '3':
            directory = input("Enter the directory to sort: ")
            if os.path.isdir(directory):
                move_and_rename_files(directory)
                print("Manga organization completed.")
            else:
                print("Invalid directory.")
        elif choice == '4':
            print("Exiting the program.")
            break
        else:
            print("Invalid choice.")
