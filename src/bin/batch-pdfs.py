#!/usr/bin/env python3
"""
Script to batch PDF files from artifacts directory.
Usage: python batch-pdfs.py [badges|checksheets] <batch_size>
"""

import sys
import os
import glob
import shutil
from pathlib import Path
from PyPDF2 import PdfWriter, PdfReader


def main():
    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Error: Missing required arguments", file=sys.stderr)
        print("Usage: python batch-pdfs.py [badges|checksheets] <batch_size>", file=sys.stderr)
        sys.exit(1)
    
    # Check for valid types
    valid_types = ['badges', 'checksheets']
    types_to_process = []
    batch_size = None
    
    for arg in sys.argv[1:]:
        if arg in valid_types:
            types_to_process.append(arg)
        else:
            # Try to parse as integer for batch size
            try:
                batch_size = int(arg)
            except ValueError:
                print(f"Error: Invalid argument '{arg}'. Expected 'badges', 'checksheets', or an integer batch size.", file=sys.stderr)
                sys.exit(1)
    
    # Validate we have at least one type
    if not types_to_process:
        print("Error: Must specify at least one of 'badges' or 'checksheets'", file=sys.stderr)
        sys.exit(1)
    
    # Validate we have batch size
    if batch_size is None:
        print("Error: Must specify batch size as an integer", file=sys.stderr)
        sys.exit(1)
    
    if batch_size <= 0:
        print("Error: Batch size must be a positive integer", file=sys.stderr)
        sys.exit(1)
    
    # Process each type
    for pdf_type in types_to_process:
        process_type(pdf_type, batch_size)


def process_type(pdf_type, batch_size):
    """Process a single type (badges or checksheets)."""
    print(f"Processing {pdf_type} with batch size {batch_size}...")
    
    # Define paths
    artifacts_path = Path("artifacts") / pdf_type
    batches_path = artifacts_path / "batches"
    
    # List all PDF files in alphabetical order
    pdf_pattern = str(artifacts_path / "*.pdf")
    pdf_files = sorted(glob.glob(pdf_pattern))
    
    if not pdf_files:
        print(f"Warning: No PDF files found in {artifacts_path}")
        return
    
    print(f"Found {len(pdf_files)} PDF files")
    
    # Remove existing batches directory if it exists
    if batches_path.exists():
        shutil.rmtree(batches_path)
    
    # Create batches directory
    batches_path.mkdir(parents=True, exist_ok=True)
    
    # Create batches
    for i in range(0, len(pdf_files), batch_size):
        batch_files = pdf_files[i:i + batch_size]
        batch_num = i // batch_size
        batch_filename = f"batch-{batch_num:03d}.pdf"
        batch_path = batches_path / batch_filename
        
        print(f"Creating {batch_filename} with {len(batch_files)} files...")
        
        # Merge PDFs
        merge_pdfs(batch_files, batch_path)
    
    print(f"Completed processing {pdf_type}")


def merge_pdfs(pdf_files, output_path):
    """Merge multiple PDF files into a single PDF."""
    writer = PdfWriter()
    
    for pdf_file in pdf_files:
        try:
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            print(f"Warning: Could not process {pdf_file}: {e}", file=sys.stderr)
            continue
    
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)


if __name__ == "__main__":
    main()
