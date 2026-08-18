# ============================================================
# dataset/download_dataset.py
# ASAP Dataset Download Helper
# ============================================================
# Attempts to download the ASAP essay scoring dataset from Kaggle.
# Falls back to providing manual download instructions.
# ============================================================

import os
import sys


def download_from_kaggle():
    """
    Download the ASAP dataset using the Kaggle API.
    
    Requires:
        - kaggle Python package installed (pip install kaggle)
        - Kaggle API credentials configured (~/.kaggle/kaggle.json)
    """
    dataset_dir = os.path.dirname(os.path.abspath(__file__))
    target_file = os.path.join(dataset_dir, "training_set_rel3.tsv")

    # Check if already downloaded
    if os.path.exists(target_file):
        file_size = os.path.getsize(target_file) / (1024 * 1024)
        print(f"✓ Dataset already exists: {target_file} ({file_size:.1f} MB)")
        return True

    print("Attempting to download ASAP dataset from Kaggle...")
    print()

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()

        print("Downloading competition data...")
        api.competition_download_files(
            'asap-aes',
            path=dataset_dir,
            quiet=False
        )

        # Extract if zip file
        import zipfile
        zip_path = os.path.join(dataset_dir, "asap-aes.zip")
        if os.path.exists(zip_path):
            print("Extracting files...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(dataset_dir)
            os.remove(zip_path)

        if os.path.exists(target_file):
            print(f"✓ Dataset downloaded successfully: {target_file}")
            return True
        else:
            print("⚠ Download completed but training_set_rel3.tsv not found.")
            print("  Please check the downloaded files and rename if necessary.")
            return False

    except ImportError:
        print("⚠ Kaggle package not installed.")
        print("  Install it with: pip install kaggle")
        print()
        print_manual_instructions()
        return False

    except Exception as e:
        print(f"⚠ Kaggle API error: {e}")
        print()
        print_manual_instructions()
        return False


def print_manual_instructions():
    """Print manual download instructions."""
    dataset_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("  📥 Manual Download Instructions")
    print("=" * 60)
    print()
    print("  1. Go to: https://www.kaggle.com/c/asap-aes/data")
    print("     (You'll need a Kaggle account — sign up is free)")
    print()
    print("  2. Accept the competition rules (if prompted)")
    print()
    print("  3. Download 'training_set_rel3.tsv' (or the full zip)")
    print()
    print(f"  4. Place the file at:")
    print(f"     {os.path.join(dataset_dir, 'training_set_rel3.tsv')}")
    print()
    print("  Alternative: Use Kaggle CLI:")
    print("     pip install kaggle")
    print("     kaggle competitions download -c asap-aes")
    print()
    print("=" * 60)


def verify_dataset():
    """
    Verify the dataset file exists and has the expected structure.
    
    Returns:
        True if dataset is valid, False otherwise
    """
    dataset_dir = os.path.dirname(os.path.abspath(__file__))
    target_file = os.path.join(dataset_dir, "training_set_rel3.tsv")

    if not os.path.exists(target_file):
        print(f"❌ Dataset not found: {target_file}")
        return False

    try:
        import pandas as pd
        df = pd.read_csv(target_file, sep='\t', encoding='latin-1', nrows=5)

        required_columns = ['essay_id', 'essay_set', 'essay', 'domain1_score']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            print(f"❌ Dataset is missing required columns: {missing}")
            print(f"   Found columns: {list(df.columns)}")
            return False

        # Full row count
        df_full = pd.read_csv(target_file, sep='\t', encoding='latin-1')
        print(f"✓ Dataset verified: {len(df_full)} essays across "
              f"{df_full['essay_set'].nunique()} essay sets")
        return True

    except Exception as e:
        print(f"❌ Error reading dataset: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        verify_dataset()
    else:
        success = download_from_kaggle()
        if success:
            verify_dataset()
