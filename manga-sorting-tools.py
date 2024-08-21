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

def run_7z_test(file_path):
    result = subprocess.run(['7z', 't', file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def process_files_in_directory(directory):
    log = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')):
                file_path = os.path.join(root, file_name)
                log.append(f"Processing file: {file_path}")
                
                if '[' in file_name and ']' in file_name:
                    log.append(f"Skipping file '{file_name}': CRC32 already exists in the filename.")
                    continue
                
                crc32 = calculate_crc32(file_path)
                log.append(f"Calculated CRC32: {crc32}")
                
                if '(v)' not in file_name:
                    if run_7z_test(file_path):
                        new_name = f"{file_name.rsplit('.', 1)[0]} (v) [{crc32}].{file_name.rsplit('.', 1)[1]}"
                        log.append(f"7z test passed. New name will be: {new_name}")
                    else:
                        new_name = f"{file_name.rsplit('.', 1)[0]} [{crc32}].{file_name.rsplit('.', 1)[1]}"
                        log.append(f"7z test failed or '(v)' already in filename. New name will be: {new_name}")
                else:
                    new_name = f"{file_name.rsplit('.', 1)[0]} [{crc32}].{file_name.rsplit('.', 1)[1]}"
                    log.append(f"File already has '(v)' in the filename. New name will be: {new_name}")
                
                new_file_path = os.path.join(root, new_name)
                os.rename(file_path, new_file_path)
                log.append(f"Renamed '{file_name}' to '{new_name}'")
                log.append("")

    return log

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
                    log.append(f"Match: {file_name}")
                else:
                    mismatches += 1
                    mismatched_files.append(file_path)
                    log.append(f"Mismatch: {file_name} (Expected: {crc32_in_name}, Found: {calculated_crc32})")
                    
    log.append(f"\nTotal Matches: {matches}")
    log.append(f"Total Mismatches: {mismatches}")
    
    if mismatches > 0:
        log.append("\nMismatched Files:")
        for file in mismatched_files:
            log.append(file)
    
    return log, mismatched_files

def organize_manga_directory(directory):
    for root, subdirs, files in os.walk(directory):
        for subdir in subdirs:
            subdir_path = os.path.join(root, subdir)
            archive_files = [f for f in os.listdir(subdir_path) if f.endswith(('.cbz', '.cbr'))]
            
            if not archive_files:
                continue

            volumes = []
            years = []
            contributors = set()
            
            for file_name in archive_files:
                volume_match = re.search(r'v(\d+)', file_name)
                year_match = re.search(r'\((\d{4})\)', file_name)
                contributor_match = re.search(r'\(([^()]+)\)\.cbz', file_name)

                if volume_match:
                    volumes.append(int(volume_match.group(1)))

                if year_match:
                    years.append(int(year_match.group(1)))

                if contributor_match:
                    contributors.add(contributor_match.group(1))

            if volumes:
                volume_range = f"v{min(volumes):02d}-{max(volumes):02d}"
            else:
                volume_range = ""

            if years:
                year_range = f"{min(years)}-{max(years)}" if len(set(years)) > 1 else f"{years[0]}"
            else:
                year_range = ""

            contributors_str = ', '.join(sorted(contributors))

            new_folder_name = f"{subdir} {volume_range} ({year_range}) (Digital) ({contributors_str})"
            new_folder_path = os.path.join(root, new_folder_name)

            if subdir_path != new_folder_path:
                os.rename(subdir_path, new_folder_path)
                print(f"Renamed folder '{subdir_path}' to '{new_folder_path}'")

    # Handle loose files
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(('.cbz', '.cbr')):
                title_match = re.match(r'(.+?) v\d+', file_name)
                if title_match:
                    title = title_match.group(1)
                    target_folder = os.path.join(directory, title)

                    if os.path.exists(target_folder):
                        shutil.move(os.path.join(root, file_name), target_folder)
                        print(f"Moved '{file_name}' to '{target_folder}'")

if __name__ == "__main__":
    choice = input("Manga Sorting Tools, by rarenight\n\nSelect an option:\n1. Manga Hasher\n2. Manga Verifier\n3. Manga Organizer\nEnter 1, 2, or 3: ")
    
    if choice == '1':
        directory = input("Enter the directory to process: ")
        if os.path.isdir(directory):
            log = process_files_in_directory(directory)
            print("\nProcessing Log:")
            for entry in log:
                print(entry)
            print("Processing completed.")
        else:
            print("Invalid directory.")
    
    elif choice == '2':
        directory = input("Enter the directory to verify: ")
        if os.path.isdir(directory):
            log, mismatched_files = verify_files_in_directory(directory)
            print("\nVerification Log:")
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
                print("All files verified successfully.")
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
