"""Diagnostic: inspect what list_files / walk return and how the filter behaves."""
import asyncio
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Apply same auth patch as data_loader
from utils import data_loader  # noqa: F401  (triggers patch)
from gex_msgraph import GraphClient


async def main():
    root_dir = os.environ.get("ROOT_DIR")
    print(f"ROOT_DIR = {root_dir}\n")

    client = GraphClient("das_u1")
    items = await client.list_files(root_dir)
    xlsx_files = await client.walk(root_dir, pattern="*.xls*")

    print(f"list_files returned {len(items)} items")
    print(f"walk returned {len(xlsx_files)} xlsx files\n")

    df_folders = pd.DataFrame(items)[["name", "path"]].rename(
        columns={"name": "folder_name", "path": "folder_path"}
    )
    df_xlsx = pd.DataFrame(xlsx_files)[["name", "path"]].rename(
        columns={"name": "file_name", "path": "file_path"}
    )
    df_xlsx["folder_path"] = df_xlsx["file_path"].str.rsplit("/", n=1).str[0]

    print("=== df_folders sample (first 10) ===")
    print(df_folders.head(10).to_string())
    print(f"\nTotal folders: {len(df_folders)}")
    print(f"Folders starting with '00': {df_folders['folder_name'].str.startswith('00').sum()}\n")

    print("=== files whose path contains 'THI' ===")
    thi_files = df_xlsx[df_xlsx["file_path"].str.contains("THI", case=False, na=False)]
    print(thi_files[["file_name", "file_path", "folder_path"]].to_string())
    print(f"\nTHI file count: {len(thi_files)}\n")

    print("=== files whose folder_path has any segment starting with '00' ===")
    def _has_skip(p):
        return any(seg.startswith("00") for seg in str(p).split("/"))
    skip_files = df_xlsx[df_xlsx["folder_path"].apply(_has_skip)]
    print(skip_files[["file_name", "folder_path"]].head(20).to_string())
    print(f"\nSkip-match count: {len(skip_files)}\n")

    # Reproduce the merge + filter
    df_list_files = df_folders.merge(df_xlsx, on="folder_path", how="left")
    print(f"=== After merge ===\nTotal rows: {len(df_list_files)}")
    print(f"Rows with file_path: {df_list_files['file_path'].notna().sum()}\n")

    df_filtered = df_list_files[~df_list_files["folder_path"].apply(_has_skip)]
    print(f"=== After filter (folder_path segment startswith '00') ===")
    print(f"Total rows: {len(df_filtered)}")
    print(f"Rows with file_path: {df_filtered['file_path'].notna().sum()}\n")

    thi_after = df_filtered[df_filtered["file_path"].fillna("").str.contains("THI", case=False)]
    print(f"=== THI files surviving the filter ===")
    print(thi_after[["folder_name", "folder_path", "file_name"]].to_string())


if __name__ == "__main__":
    asyncio.run(main())
