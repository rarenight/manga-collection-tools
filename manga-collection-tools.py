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


    folder_name = f"【{title}】"

    if info['chapters']:
        chapter_range = format_chapter_range(list(info['chapters']))
        folder_name += f" ({chapter_range})"
    if info['volumes']:
        volume_range = format_volume_range(list(info['volumes']))
        if 'chapters' in info and info['chapters']:
            folder_name += f" & {volume_range}"
        else:
            folder_name += f" ({volume_range})"

    folder_contains_v = all_files_have_v_pattern([os.path.basename(f) for f in info['files']])
    if folder_contains_v:
        folder_name += " [v]"

    new_folder_path = os.path.join(directory, folder_name)
    return new_folder_path

def normalize_filename(file_name):
    base_name = re.sub(r'\s*\[v\d+[\w]{8}\]\s*', '', file_name)
    base_name = re.sub(r'\W+', '', base_name).lower()
    return base_name

def format_chapter_range(chapters):
    chapters = sorted(chapters)
    ranges = []
    start = chapters[0]
    prev = chapters[0]

    for i in range(1, len(chapters)):
        if chapters[i] == prev + 1:
            prev = chapters[i]
        else:
            if start == prev:
                ranges.append(f"c{start:03d}")
            else:
                ranges.append(f"c{start:03d}-{prev:03d}")
            start = chapters[i]
            prev = chapters[i]

    if start == prev:
        ranges.append(f"c{start:03d}")
    else:
        ranges.append(f"c{start:03d}-{prev:03d}")

    return ', '.join(ranges)

def format_volume_range(volumes):
    volumes = sorted(volumes)
    ranges = []
    start = volumes[0]
    prev = volumes[0]

    for i in range(1, len(volumes)):
        if volumes[i] == prev + 1:
            prev = volumes[i]
        else:
            if start == prev:
                ranges.append(f"v{start:02d}")
            else:
                ranges.append(f"v{start:02d}-{prev:02d}")
            start = volumes[i]
            prev = volumes[i]

    if start == prev:
        ranges.append(f"v{start:02d}")
    else:
        ranges.append(f"v{start:02d}-{prev:02d}")

    return ', '.join(ranges)

def combine_chapter_and_volume_ranges(chapters, volumes):
    volume_range = format_volume_range(list(volumes)) if volumes else ''
    chapter_range = format_chapter_range(list(chapters)) if chapters else ''
    
    combined = ', '.join(filter(None, [volume_range, chapter_range]))
    return combined

def all_files_have_v_pattern(files):
    v_pattern = re.compile(r'\[v\d+[A-F0-9]{8}\]')
    return all(v_pattern.search(file) for file in files)

def delete_empty_folders(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)
                print(f"Deleted empty folder: {folder_path}")

def get_base_title(file_name):
    base_title_match = re.match(r'【(.+?)】', file_name)
    if base_title_match:
        return base_title_match.group(1).strip()
    return None

def rename_folder_based_on_contents(directory, title, info):
    folder_name = f"【{title}】"

    combined_range = combine_chapter_and_volume_ranges(info['chapters'], info['volumes'])
    if combined_range:
        folder_name += f" ({combined_range})"

    folder_contains_v = all_files_have_v_pattern([os.path.basename(f) for f in info['files']])
    if folder_contains_v:
        folder_name += " [v]"

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

                    chapter_match = re.match(r'.+? c(\d{3,4})', file_name)
                    volume_match = re.match(r'.+? v(\d+)', file_name)

                    if chapter_match:
                        chapter = int(chapter_match.group(1))
                        organized_files[base_title]['chapters'].add(chapter)
                    elif volume_match:
                        volume = int(volume_match.group(1))
                        organized_files[base_title]['volumes'].add(volume)

                    organized_files[base_title]['files'].append(os.path.join(root, file_name))

    for title, info in organized_files.items():
        new_folder_path = rename_folder_based_on_contents(directory, title, info)

        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        else:
            existing_files = [f for f in os.listdir(new_folder_path) if f.endswith(('.cbz', '.cbr'))]
            if existing_files:
                for f in existing_files:
                    chapter_match = re.match(r'.+? c(\d{3,4})', f)
                    volume_match = re.match(r'.+? v(\d+)', f)
                    if chapter_match:
                        chapter = int(chapter_match.group(1))
                        if chapter not in info['chapters']:
                            info['chapters'].add(chapter)
                    if volume_match:
                        volume = int(volume_match.group(1))
                        if volume not in info['volumes']:
                            info['volumes'].add(volume)

            updated_folder_path = rename_folder_based_on_contents(directory, title, info)
            if updated_folder_path != new_folder_path:
                os.rename(new_folder_path, updated_folder_path)
                new_folder_path = updated_folder_path

        for file_path in info['files']:
            new_file_path = os.path.join(new_folder_path, os.path.basename(file_path))
            if os.path.exists(new_file_path):
                print(f"File '{new_file_path}' already exists. Skipping.")
            else:
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
