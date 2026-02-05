#!/usr/bin/env python3
"""
WiDS Project - Complete Cleanup (Move ALL Loose Files)
=======================================================

This script moves ALL files from root into proper folders,
including the loose visualization folders and CSV files.

Author: WiDS Team
Date: 2025-01-25
"""

import os
import shutil

print("🧹 Complete Project Cleanup - Moving ALL Loose Files")
print("="*70)

moved = []
skipped = []

# ============================================================================
# Step 1: Move Loose Visualization Folders
# ============================================================================

print("\n📊 Step 1: Moving visualization folders...")

viz_folders_to_move = ['geo_viz', 'signal_viz', 'timeline_viz']

for folder in viz_folders_to_move:
    if os.path.exists(folder) and os.path.isdir(folder):
        dest = f'05_visualizations/{folder}'
        if os.path.exists(dest):
            print(f"  ⚠️  {folder}/ already exists in 05_visualizations/")
            
            # Check if root version has files
            root_files = os.listdir(folder)
            dest_files = os.listdir(dest)
            
            if len(root_files) > len(dest_files):
                print(f"     Root has {len(root_files)} files, destination has {len(dest_files)}")
                print(f"     Merging folders...")
                
                # Copy files from root to destination
                for file in root_files:
                    src_file = os.path.join(folder, file)
                    dst_file = os.path.join(dest, file)
                    if not os.path.exists(dst_file):
                        shutil.copy2(src_file, dst_file)
                        print(f"     → Copied {file}")
                
                # Remove root folder
                shutil.rmtree(folder)
                print(f"  ✓ Merged and removed root {folder}/")
                moved.append(f"{folder}/")
            else:
                # Root is duplicate, just remove it
                shutil.rmtree(folder)
                print(f"  ✓ Removed duplicate {folder}/ from root")
                moved.append(f"{folder}/")
        else:
            # Move entire folder
            os.makedirs('05_visualizations', exist_ok=True)
            shutil.move(folder, dest)
            print(f"  ✓ Moved {folder}/ → 05_visualizations/")
            moved.append(f"{folder}/")

# ============================================================================
# Step 2: Move Loose CSV and TXT Files
# ============================================================================

print("\n📄 Step 2: Moving loose result files...")

result_files = [
    'delay_metrics.csv',
    'zone_linkage_details.csv',
    'summary_stats.txt',
]

for file in result_files:
    if os.path.exists(file):
        dest = f'04_results/{file}'
        if os.path.exists(dest):
            print(f"  ⚠️  {file} already exists in 04_results/, removing duplicate from root")
            os.remove(file)
            skipped.append(file)
        else:
            os.makedirs('04_results', exist_ok=True)
            shutil.move(file, dest)
            print(f"  ✓ Moved {file} → 04_results/")
            moved.append(file)

# ============================================================================
# Step 3: Move Documentation Files
# ============================================================================

print("\n📚 Step 3: Moving documentation files...")

doc_files = [
    'WiDS_-_-_Watch_Duty_Data_Dictionary.docx',
]

for file in doc_files:
    if os.path.exists(file):
        dest = f'02_documentation/{file}'
        if os.path.exists(dest):
            print(f"  ⚠️  {file} already in 02_documentation/, removing duplicate")
            os.remove(file)
            skipped.append(file)
        else:
            os.makedirs('02_documentation', exist_ok=True)
            shutil.move(file, dest)
            print(f"  ✓ Moved {file} → 02_documentation/")
            moved.append(file)

# ============================================================================
# Step 4: Move Scripts
# ============================================================================

print("\n🐍 Step 4: Moving scripts...")

scripts = [
    'organize_project.py',
]

for file in scripts:
    if os.path.exists(file):
        dest = f'03_analysis_scripts/{file}'
        if os.path.exists(dest):
            print(f"  ⚠️  {file} already in 03_analysis_scripts/, removing duplicate")
            os.remove(file)
            skipped.append(file)
        else:
            os.makedirs('03_analysis_scripts', exist_ok=True)
            shutil.move(file, dest)
            print(f"  ✓ Moved {file} → 03_analysis_scripts/")
            moved.append(file)

# ============================================================================
# Step 5: Keep Important Root Files
# ============================================================================

print("\n📌 Step 5: Keeping important root files...")

keep_in_root = [
    '.gitattributes',
    '.gitignore',
    'PROJECT_INDEX.txt',
    'run_all_analysis.sh',
    'push_to_github.py',
    'README.md',  # If exists
]

print("\nFiles to keep in root:")
for file in keep_in_root:
    if os.path.exists(file):
        print(f"  ✓ {file}")

# ============================================================================
# Step 6: Show Final Structure
# ============================================================================

print("\n📂 Final directory structure:")
print("-"*70)

folders = [
    '01_raw_data',
    '02_documentation', 
    '03_analysis_scripts',
    '04_results',
    '05_visualizations',
    '06_working_files',
]

for folder in folders:
    if os.path.exists(folder):
        items = os.listdir(folder)
        print(f"  {folder}/ ({len(items)} items)")
        
        # Show subfolders if any
        subfolders = [f for f in items if os.path.isdir(os.path.join(folder, f))]
        if subfolders:
            for subfolder in subfolders:
                subfolder_path = os.path.join(folder, subfolder)
                subfolder_items = len(os.listdir(subfolder_path))
                print(f"    └─ {subfolder}/ ({subfolder_items} items)")

# ============================================================================
# Step 7: List Remaining Root Files
# ============================================================================

print("\n📋 Remaining files in root:")
print("-"*70)

root_files = [f for f in os.listdir('.') if os.path.isfile(f)]
root_folders = [f for f in os.listdir('.') if os.path.isdir(f) and not f.startswith('.')]

if root_files:
    print("Files:")
    for f in root_files:
        if f in keep_in_root:
            print(f"  ✓ {f} (should be here)")
        else:
            print(f"  • {f}")
else:
    print("  (no loose files)")

if root_folders:
    print("\nFolders:")
    expected_folders = folders + ['06_working_files']
    for f in root_folders:
        if f in expected_folders:
            print(f"  ✓ {f}/ (organized folder)")
        else:
            print(f"  ⚠️  {f}/ (unexpected folder)")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*70)
print("✅ Cleanup Complete!")
print("="*70)
print(f"Files/folders moved: {len(moved)}")
print(f"Duplicates removed: {len(skipped)}")

if len(moved) > 0:
    print("\nMoved:")
    for item in moved:
        print(f"  • {item}")

print("\n🎯 Project is now organized and ready to push!")
print("Next step: python3 push_to_github.py")
print("="*70)