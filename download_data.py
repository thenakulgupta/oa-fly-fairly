"""
download_data.py - Works on Windows, Mac, and Linux
Run: python download_data.py
"""

import os
import zipfile
import urllib.request

# Files to download
FILES = [
    {
        "url": "https://davidmegginson.github.io/ourairports-data/airports.csv",
        "filename": "airports.csv",
        "unzip": False
    },
    {
        "url": "https://davidmegginson.github.io/ourairports-data/countries.csv",
        "filename": "countries.csv",
        "unzip": False
    },
    {
        "url": "https://davidmegginson.github.io/ourairports-data/regions.csv",
        "filename": "regions.csv",
        "unzip": False
    },
    {
        "url": "https://download.geonames.org/export/dump/alternateNames.zip",
        "filename": "alternateNames.zip",
        "unzip": True
    },
    {
        "url": "https://download.geonames.org/export/dump/cities15000.zip",
        "filename": "cities15000.zip",
        "unzip": True
    },
    {
        "url": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat",
        "filename": "airports.dat",
        "unzip": False
    },
]

DELETE_FILES = [
    "iso-languagecodes.txt",
]

def download_file(url, destination):
    """Download a file with progress indicator."""
    print(f"Downloading {destination}...")

    def show_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(int(downloaded * 100 / total_size), 100)
            bar = "#" * (percent // 5) + "-" * (20 - percent // 5)
            print(f"\r  [{bar}] {percent}%", end="", flush=True)

    urllib.request.urlretrieve(url, destination, show_progress)
    print()  # newline after progress bar
    print(f"  ✓ Saved to {destination}")


def unzip_file(zip_path, extract_to):
    """Unzip a file into the same folder."""
    print(f"  Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)
    os.remove(zip_path)  # delete zip after extracting
    print(f"  ✓ Extracted and removed zip")


def main():
    # Create data folder if it doesn't exist
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    print(f"\n📁 Saving all files to /{data_dir} folder\n")

    for file in FILES:
        destination = os.path.join(data_dir, file["filename"])

        # Skip if file already exists (unzipped version)
        final_name = file["filename"].replace(".zip", ".txt")
        final_path = os.path.join(data_dir, final_name)
        if os.path.exists(final_path) or os.path.exists(destination):
            print(f"  ⚡ Skipping {file['filename']} (already exists)")
            continue

        try:
            download_file(file["url"], destination)
            if file["unzip"]:
                unzip_file(destination, data_dir)
        except Exception as e:
            print(f"  ✗ Failed to download {file['filename']}: {e}")

    for file in DELETE_FILES:
        destination = os.path.join(data_dir, file)
        if os.path.exists(destination):
            os.remove(destination)

    print("\n✅ All files downloaded successfully!")
    print("\nYour /data folder should now have:")
    print("  - airports.csv")
    print("  - countries.csv")
    print("  - regions.csv")
    print("  - alternateNames.txt")
    print("  - cities15000.txt")
    print("  - airports.dat")
    print("\nNext step: python ingest.py")


if __name__ == "__main__":
    main()