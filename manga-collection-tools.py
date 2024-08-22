import sys
import os
import re
import shutil
import zlib
import subprocess
from datetime import datetime

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

def normalize_filename(file_name):
    base_name = re.sub(r'\s*\(v\)\s*|\s*\[\w+\]\s*', '', file_name)
    base_name = re.sub(r'\W+', '', base_name).lower()
    return base_name

def process_files_in_directory(directory):
    log = []
    v_failures = []

    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')):
                file_path = os.path.join(root, file_name)
                if '[' in file_name and ']' in file_name:
                    log.append(f"Skipping file '{file_name}': CRC32 already exists in the filename.")
                    continue
                
                crc32 = calculate_crc32(file_path)
                log.append(f"Calculated CRC32: {crc32}")
                
                new_name = None

                if '(v)' not in file_name:
                    if run_7z_test(file_path):
                        new_name = f"{file_name.rsplit('.', 1)[0]} (v) [{crc32}].{file_name.rsplit('.', 1)[1]}"
                        log.append(f"7z test passed. New name will be: {new_name}")
                    else:
                        v_failures.append(file_name)
                        log.append(f"7z test failed for '{file_name}'. CRC32 will not be added.")
                else:
                    new_name = f"{file_name.rsplit('.', 1)[0]} [{crc32}].{file_name.rsplit('.', 1)[1]}"
                    log.append(f"File already has '(v)' in the filename. New name will be: {new_name}")
                
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
            if file_name.endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')) and '[' in file_name and ']' in file_name:
                file_path = os.path.join(root, file_name)
                
                crc32_in_name = file_name[file_name.index('[') + 1:file_name.index(']')]
                calculated_crc32 = calculate_crc32(file_path)
                
                if crc32_in_name == calculated_crc32:
                    matches += 1
                else:
                    mismatches += 1
                    mismatched_files.append(file_path)
                    log.append(f"Mismatch: {file_name} (Expected: {crc32_in_name}, Found: {calculated_crc32})")
    
    log.append(f"\nTotal Matches: {matches}")
    log.append(f"Total Mismatches: {mismatches}")
    
    return log, mismatched_files

def organize_manga_directory(directory):
    organized_files = {}

    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.cbz', '.cbr')):
                title_match = re.match(r'(.+?) (?:v(\d+)|(\d+)) \((\d{4})\) \(Digital\) \(([^()]+)\)', file_name)
                if title_match:
                    title = title_match.group(1).strip()
                    volume = title_match.group(2)
                    chapter = title_match.group(3)
                    year = title_match.group(4)
                    contributor = title_match.group(5)
                    v_match = '(v)' in file_name

                    key = normalize_filename(title)

                    if key not in organized_files:
                        organized_files[key] = {
                            'volumes': set(),
                            'chapters': set(),
                            'years': set(),
                            'contributors': set(),
                            'v_flag': v_match,
                            'files': []
                        }

                    if volume:
                        organized_files[key]['volumes'].add(int(volume))
                    if chapter:
                        organized_files[key]['chapters'].add(int(chapter))
                    if year:
                        organized_files[key]['years'].add(int(year))
                    if contributor:
                        organized_files[key]['contributors'].add(contributor)
                    if v_match:
                        organized_files[key]['v_flag'] = True
                    organized_files[key]['files'].append((os.path.join(root, file_name), calculate_crc32(os.path.join(root, file_name))))

    for title, info in organized_files.items():
        volume_range = f"v{min(info['volumes']):02d}-{max(info['volumes']):02d}" if len(info['volumes']) > 1 else f"v{list(info['volumes'])[0]:02d}" if info['volumes'] else ''
        chapter_range = f"{min(info['chapters']):03d}-{max(info['chapters']):03d}" if len(info['chapters']) > 1 else f"{list(info['chapters'])[0]:03d}" if info['chapters'] else ''
        year_range = f"{min(info['years'])}-{max(info['years'])}" if len(info['years']) > 1 else f"{list(info['years'])[0]}" if info['years'] else ''
        contributors_str = ', '.join(sorted(info['contributors']))

        if volume_range and chapter_range:
            combined_range = f"{volume_range}, {chapter_range}"
        else:
            combined_range = volume_range if volume_range else chapter_range

        new_folder_name = f"{title} ({combined_range}) ({year_range}) ({contributors_str})"
        if info['v_flag']:
            new_folder_name += ' (v)'

        new_folder_path = os.path.join(directory, new_folder_name)

        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)

        crc_to_file = {}
        for file_path, crc in info['files']:
            file_name = os.path.basename(file_path)
            normalized_name = normalize_filename(file_name)
            if normalized_name in crc_to_file:
                existing_file, existing_crc = crc_to_file[normalized_name]
                if crc == existing_crc:
                    existing_mtime = os.path.getmtime(existing_file)
                    current_mtime = os.path.getmtime(file_path)
                    if existing_mtime < current_mtime:
                        os.remove(file_path)
                    else:
                        os.remove(existing_file)
                        crc_to_file[normalized_name] = (file_path, crc)
                else:
                    shutil.move(file_path, new_folder_path)
                    crc_to_file[normalized_name] = (file_path, crc)
            else:
                shutil.move(file_path, new_folder_path)
                crc_to_file[normalized_name] = (file_path, crc)

if __name__ == "__main__":
    choice = input("Manga Collection Tools\nby rarenight\n\nSelect an option:\n1. Manga Hasher\n2. Manga Verifier\n3. Manga Organizer\n\nEnter 1, 2, or 3: ")

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
                print("\nSummary of Mismatched Files:")
                for entry in log:
                    print(entry)

            if mismatched_files:
                print(f"\n{len(mismatched_files)} mismatched files found.")
                export_choice = input("Would you like to export the mismatched files to a text file? (y/n): ")
                if export_choice.lower() == 'y':
                    export_path = input("Enter the path for the export file (e.g., /path/to/mismatches.txt): ")
                    try:
                        with open(export_path, 'w') as f:
                            for file in mismatched_files:
                                f.write(file + '\n')
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

    else:
        print("Invalid choice.")
