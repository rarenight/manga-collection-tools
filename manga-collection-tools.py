import sys
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

def get_file_size(file_path):
    return os.path.getsize(file_path)

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
                match = re.search(r'\[v(\d+)([A-F0-9]{8})\]', file_name)
                if match:
                    log.append(f"File '{file_name}' already contains the version pattern '[v{match.group(1)}{match.group(2)}]', skipping calculations.")
                    continue
                crc32 = calculate_crc32(file_path)
                size_in_bytes = get_file_size(file_path)
                log.append(f"Calculated CRC32: {crc32} and size: {size_in_bytes} bytes")
                new_name = None
                expected_pattern = f"[v{size_in_bytes}{crc32}]"
                if expected_pattern not in file_name:
                    if run_7z_test(file_path):
                        new_name = f"{file_name.rsplit('.', 1)[0]} {expected_pattern}.{file_name.rsplit('.', 1)[1]}"
                        log.append(f"7z test passed. New name will be: {new_name}")
                    else:
                        v_failures.append(file_name)
                        log.append(f"7z test failed for '{file_name}'. CRC32 will not be added.")
                else:
                    log.append(f"File already contains the pattern '{expected_pattern}'.")
                if new_name:
                    new_file_path = os.path.join(root, new_name)
                    os.rename(file_path, new_file_path)
                    log.append(f"Renamed '{file_name}' to '{new_name}'")
                log.append("")
    return log, v_failures

def verify_files_in_directory(directory):
    log = []
    mismatched_files = []
    matched_files = []
    matches = 0
    mismatches = 0
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')) and re.search(r'\[v(\d+)([A-F0-9]{8})\]', file_name):
                file_path = os.path.join(root, file_name)
                try:
                    match = re.search(r'\[v(\d+)([A-F0-9]{8})\]', file_name)
                    if not match:
                        raise ValueError("Pattern not found in filename.")
                    size_in_name = int(match.group(1))
                    crc32_in_name = match.group(2)
                except (ValueError, IndexError) as e:
                    log.append(f"Error parsing '{file_name}': {e}")
                    mismatched_files.append(file_path)
                    continue
                calculated_crc32 = calculate_crc32(file_path)
                file_size = get_file_size(file_path)
                log_entry = (f"File: {file_name}\n"
                             f"Expected: Size={size_in_name}, CRC32={crc32_in_name}\n"
                             f"Actual:   Size={file_size}, CRC32={calculated_crc32}\n")
                if crc32_in_name == calculated_crc32 and size_in_name == file_size:
                    matches += 1
                    matched_files.append(file_name)
                    log.append(f"Match:\n{log_entry}")
                else:
                    mismatches += 1
                    mismatched_files.append({
                        'file': file_path,
                        'expected_size': size_in_name,
                        'actual_size': file_size,
                        'expected_crc32': crc32_in_name,
                        'actual_crc32': calculated_crc32
                    })
                    log.append(f"Mismatch:\n{log_entry}")
    log.append(f"\nTotal Matches: {matches}")
    log.append(f"Total Mismatches: {mismatches}")
    if matches > 0:
        print("\nMatched Files:")
        for entry in log:
            if "Match" in entry:
                print(entry)
    return log, mismatched_files

def get_base_title(file_name):
    base_title_match = re.match(r'^[^\dv]*', file_name)
    if base_title_match:
        return base_title_match.group(0).strip()
    return None

def combine_chapter_and_volume_ranges(chapters, volumes=None):
    chapter_range = ""
    volume_range = ""

    if chapters:
        chapters = sorted(chapters)
        chapter_range = f"c{chapters[0]:03d}-{chapters[-1]:03d}" if len(chapters) > 1 else f"c{chapters[0]:03d}"

    if volumes:
        volumes = sorted(volumes)
        volume_range = f"v{volumes[0]:02d}-{volumes[-1]:02d}" if len(volumes) > 1 else f"v{volumes[0]:02d}"

    return ', '.join(filter(None, [volume_range, chapter_range]))

def delete_empty_folders(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)

def rename_folder_based_on_contents(directory, title, info):
    combined_range = combine_chapter_and_volume_ranges(info['chapters'], info.get('volumes', []))
    folder_name = f"{title.strip()} ({combined_range}) [v]"
    new_folder_path = os.path.join(directory, folder_name)
    return new_folder_path

def organize_manga_directory(directory):
    organized_files = {}

    for root, dirs, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.cbz', '.cbr')):
                base_title = get_base_title(file_name)

                if base_title:
                    if base_title not in organized_files:
                        organized_files[base_title] = {
                            'chapters': set(),
                            'volumes': set(),
                            'files': []
                        }

                    volume_match = re.search(r'(?<!\[)v(\d+)', file_name)
                    chapter_match = re.search(r'c?(\d{3,4})', file_name)

                    if volume_match:
                        volume = int(volume_match.group(1))
                        organized_files[base_title]['volumes'].add(volume)
                    elif chapter_match:
                        chapter = int(chapter_match.group(1))
                        organized_files[base_title]['chapters'].add(chapter)

                    organized_files[base_title]['files'].append(os.path.join(root, file_name))

    for title, info in organized_files.items():
        new_folder_path = rename_folder_based_on_contents(directory, title, info)

        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        for file_path in info['files']:
            new_file_path = os.path.join(new_folder_path, os.path.basename(file_path))
            if not os.path.exists(new_file_path):
                shutil.move(file_path, new_file_path)

    delete_empty_folders(directory)

if __name__ == "__main__":
    while True:
        choice = input("\n\nManga Collection Tools\nby rarenight\n\nSelect an option:\n1. Manga Hasher\n2. Manga Verifier\n3. Manga Organizer\n4. Exit\n\nEnter 1, 2, 3, or 4: ")
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
                        print(f"Expected: Size={mismatch['expected_size']}, CRC32={mismatch['expected_crc32']}")
                        print(f"Actual:   Size={mismatch['actual_size']}, CRC32={mismatch['actual_crc32']}")
                        print("")
                    export_choice = input("Would you like to export the mismatched files to a text file? (y/n): ")
                    if export_choice.lower() == 'y':
                        export_path = input("Enter the path for the export file (e.g., C:/path/to/mismatches.txt): ")
                        try:
                            with open(export_path, 'w', encoding='utf-8') as f:
                                for mismatch in mismatched_files:
                                    f.write(f"File: {mismatch['file']}\n")
                                    f.write(f"Expected: Size={mismatch['expected_size']}, CRC32={mismatch['expected_crc32']}\n")
                                    f.write(f"Actual:   Size={mismatch['actual_size']}, CRC32={mismatch['actual_crc32']}\n\n")
                            print(f"Mismatched files exported to {export_path}.")
                        except Exception as e:
                            print(f"Error exporting mismatched files: {e}")
                else:
                    print("\nAll files verified successfully.")
            else:
                print("Invalid directory.")
        elif choice == '3':
            directory = input("Enter the directory to organize: ")
            if os.path.isdir(directory):
                organize_manga_directory(directory)
                print("Manga organization completed.")
            else:
                print("Invalid directory.")
        elif choice == '4':
            print("Exiting the program.")
            break
        else:
            print("Invalid choice.")
