import asyncio
import concurrent.futures
import io
import os
import re
from pathlib import Path

import msal
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from gex_msgraph import GraphClient, _core as _gex_core

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Auth patch ───────────────────────────────────────────────────────────────
# Azure AD tenant requires client_secret on every token request.
# gex_msgraph uses PublicClientApplication (no secret), which works while a
# cached token exists (e.g. in a running Jupyter kernel) but fails on a fresh
# process. Swap in ConfidentialClientApplication so the secret is sent.


class _ConfidentialTokenProvider:
    _SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(self, client_id, client_secret, tenant_id, username, password):
        self._username = username
        self._password = password
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority,
        )

    def get_token(self) -> str:
        accounts = self._app.get_accounts(username=self._username)
        if accounts:
            result = self._app.acquire_token_silent(self._SCOPES, account=accounts[0])
            if result and "access_token" in result:
                return str(result["access_token"])
        result = self._app.acquire_token_by_username_password(
            username=self._username,
            password=self._password,
            scopes=self._SCOPES,
        )
        if "access_token" in result:
            return str(result["access_token"])
        err = result.get("error_description") or result.get("error") or "Unknown error"
        raise RuntimeError(f"Token acquisition failed: {err}")


_gex_core._TokenProvider = _ConfidentialTokenProvider

# ─────────────────────────────────────────────────────────────────────────────


def _run_async(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exe:
        return exe.submit(asyncio.run, coro).result()


_SHEETS = [
    ("Report",       "A:M", "_report"),
    ("Key drivers",  "A:J", "_kd"),
    ("Ratio_commit", "A:J", "_rc"),
    ("ADL input",    "A:I", "_adl"),
]


async def _fetch_all():
    root_dir = os.environ.get("ROOT_DIR")
    if not root_dir:
        raise RuntimeError(
            "ROOT_DIR is not set. Add it to .env (local) or Streamlit secrets (deploy)."
        )

    client = GraphClient("das_u1")

    items = await client.list_files(root_dir)
    xlsx_files = await client.walk(root_dir, pattern="*.xls*")

    df_folders = pd.DataFrame(items)[["name", "path"]].rename(
        columns={"name": "folder_name", "path": "folder_path"}
    )
    df_xlsx = pd.DataFrame(xlsx_files)[["name", "path", "modified"]].rename(
        columns={"name": "file_name", "path": "file_path", "modified": "file_modified"}
    )
    df_xlsx["folder_path"] = df_xlsx["file_path"].str.rsplit("/", n=1).str[0]
    df_list_files = df_folders.merge(df_xlsx, on="folder_path", how="left")

    paths = df_list_files[df_list_files["file_path"].notna()]["file_path"].tolist()

    async def _read_file(path: str) -> dict:
        """Download once, read all 4 sheets from the same buffer."""
        try:
            raw = await client.download(item_path=path)
            buf = io.BytesIO(raw)
            out = {}
            for sheet, usecols, key in _SHEETS:
                buf.seek(0)
                try:
                    df = pd.read_excel(
                        buf, sheet_name=sheet, usecols=usecols,
                        skiprows=1, engine="calamine",
                    )
                    df["_source"] = path
                    out[key] = df
                except Exception:
                    out[key] = None
            return out
        except Exception:
            return {key: None for _, _, key in _SHEETS}

    file_results = await asyncio.gather(*[_read_file(p) for p in paths])

    def _concat(key: str) -> pd.DataFrame:
        frames = [r[key] for r in file_results if r.get(key) is not None and not r[key].empty]
        return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()

    return (
        df_list_files, paths,
        _concat("_report"), _concat("_kd"), _concat("_rc"), _concat("_adl"),
    )


def _clean_report(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "Code": "code",
        "Phân cấp đơn vị": "phan_cap_don_vi",
        "Mã đơn vị": "ma_don_vi",
        "Tên đơn vị": "ten_don_vi",
        "Khoản mục": "khoan_muc",
        "Chỉ tiêu": "chi_tieu",
        "Năm": "nam",
        "Quý": "quy",
        "Số tiền tổng": "so_tien_tong",
        "Nguồn thông tin\n(Các ghi chú khác về dữ liệu, nguồn thông tin,...nếu cần để sau có thể follow up": "nguon_thong_tin",
        "Phân loại ổn định và không ổn định": "phan_loai_on_dinh_khong_on_dinh",
        "Phân loại Bên trong và bên ngoài": "phan_loai_ben_trong_ben_ngoai",
        "Đối tượng giao dịch kinh tế": "doi_tuong_giao_dich_kinh_te",
        "_source": "source",
    }
    df = df.rename(columns=mapping)
    df = df[[c for c in mapping.values() if c in df.columns]]
    df["so_tien_tong"] = pd.to_numeric(df["so_tien_tong"], errors="coerce")
    df["nam"] = pd.to_numeric(df["nam"], errors="coerce").astype("Int64")
    # quy can be numeric (1–4) or string with Q-prefix ("Q1"–"Q4")
    df["quy"] = (
        df["quy"].astype(str).str.strip().str.upper().str.replace("Q", "", regex=False)
    )
    df["quy"] = pd.to_numeric(df["quy"], errors="coerce").astype("Int64")
    return df


def _clean_key_drivers(df: pd.DataFrame) -> pd.DataFrame:
    col_a = "Phân loại Ổn định & Không ổn định"
    col_b = "Phân loại ổn định và không ổn định"
    if col_a in df.columns and col_b in df.columns:
        df[col_a] = df[col_a].combine_first(df[col_b])
        df = df.drop(columns=[col_b])

    mapping = {
        "Group": "group",
        "Code": "code",
        "Phân cấp đơn vị": "phan_cap_don_vi",
        "Mã đơn vị": "ma_don_vi",
        "Tên đơn vị": "ten_don_vi",
        "Chỉ tiêu": "chi_tieu",
        "Cấu phần value chain": "cau_phan_value_chain",
        "Key drivers": "key_drivers",
        "Phân loại Ổn định & Không ổn định": "phan_loai_on_dinh_khong_on_dinh",
        "Rationale ổn định or không ổn định": "rationale_on_dinh_khong_on_dinh",
        "Phân loại Bên trong và bên ngoài": "phan_loai_ben_trong_ben_ngoai",
        "_source": "source",
    }
    df = df.rename(columns=mapping)
    df = df[[c for c in mapping.values() if c in df.columns]]
    return df


def _clean_ratio_commit(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "Phân cấp đơn vị": "phan_cap_don_vi",
        "Mã đơn vị": "ma_don_vi",
        "Tên đơn vị": "ten_don_vi",
        "Chỉ tiêu cam kết": "chi_tieu_cam_ket",
        "Công thức": "cong_thuc",
        "Giá trị cam kết": "gia_tri_cam_ket",
        "Năm": "nam",
        "Quý": "quy",
        "Giá trị thực hiện": "gia_tri_thuc_hien",
        "Status (ok/ break)": "status",
        "_source": "source",
        "Nguồn số liệu": "nguon_so_lieu",
        "Định kỳ": "dinh_ky",
    }
    df = df.rename(columns=mapping)
    df = df[[c for c in mapping.values() if c in df.columns]]
    df["gia_tri_cam_ket"] = pd.to_numeric(df["gia_tri_cam_ket"], errors="coerce")
    df["gia_tri_thuc_hien"] = pd.to_numeric(df["gia_tri_thuc_hien"], errors="coerce")
    df["nam"] = pd.to_numeric(df["nam"], errors="coerce").astype("Int64")
    df["quy"] = (
        df["quy"].astype(str).str.strip().str.upper().str.replace("Q", "", regex=False)
    )
    df["quy"] = pd.to_numeric(df["quy"], errors="coerce").astype("Int64")
    return df


def _clean_adl(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "Phân cấp đơn vị": "phan_cap_don_vi",
        "Mã đơn vị": "ma_don_vi",
        "Tên đơn vị": "ten_don_vi",
        "Năm": "nam",
        "Giai đoạn ngành\n(Industry Lifecycle) ▼": "giai_doan_nganh",
        "Vị thế cạnh tranh\n(Competition) ▼": "vi_the_canh_tranh",
        "Mức độ\ntin cậy ▼": "muc_do_tin_cay",
        "Cơ sở đánh giá / Rationale\n(ngành, DN, market...)": "co_so_danh_gia",
        "Thị phần\nước tính (%)": "thi_phan_uoc_tinh",
        "_source": "source",
    }
    df = df.rename(columns=mapping)
    df = df[[c for c in mapping.values() if c in df.columns]]
    df["nam"] = pd.to_numeric(df["nam"], errors="coerce").astype("Int64")
    df["thi_phan_uoc_tinh"] = pd.to_numeric(df["thi_phan_uoc_tinh"], errors="coerce")
    return df


def _folder_group(folder_name: str) -> str:
    m = re.match(r"^(\d+)\.", str(folder_name))
    if not m:
        return "Unknown"
    return "GEE" if int(m.group(1)) <= 13 else "GEL"


def _status_from_source(paths: list[str], df: pd.DataFrame) -> dict[str, str]:
    """Map each file path to 'success' or 'missing_sheet' based on presence in df._source."""
    hits: set[str] = set()
    if not df.empty and "_source" in df.columns:
        hits = set(df["_source"].dropna())
    elif not df.empty and "source" in df.columns:
        hits = set(df["source"].dropna())
    return {p: ("success" if p in hits else "missing_sheet") for p in paths}


def _build_summary(df_list_files, paths, df_report_raw, df_kd_raw, df_rc_raw, df_adl_raw, df_report, df_key_drivers):
    df = df_list_files.copy()

    # Compute status columns from _source presence in raw DataFrames
    for col_name, raw_df in [
        ("report", df_report_raw),
        ("key_drivers", df_kd_raw),
        ("ratio_commit", df_rc_raw),
        ("adl_input", df_adl_raw),
    ]:
        stat_map = _status_from_source(paths, raw_df)
        df[f"{col_name}_status"] = df["file_path"].map(stat_map)

    # Group from folder number (heuristic: 01–13 = GEE, 14+ = GEL)
    df["group"] = df["folder_name"].apply(_folder_group)

    # Add ma_don_vi / ten_don_vi from df_report (one row per source file)
    if not df_report.empty and "source" in df_report.columns:
        unit_info = (
            df_report[["source", "ma_don_vi", "ten_don_vi"]]
            .drop_duplicates("source")
            .rename(columns={"source": "file_path"})
        )
        df = df.merge(unit_info, on="file_path", how="left")
    else:
        df["ma_don_vi"] = pd.NA
        df["ten_don_vi"] = pd.NA

    # Try to refine group from phan_cap_don_vi in df_report ("GEE" / "GEL" substring)
    if not df_report.empty and "phan_cap_don_vi" in df_report.columns:
        def _phan_cap_to_group(val):
            s = str(val).upper()
            if "GEE" in s:
                return "GEE"
            if "GEL" in s:
                return "GEL"
            return None

        pc_group = (
            df_report[["ma_don_vi", "phan_cap_don_vi"]]
            .dropna(subset=["ma_don_vi"])
            .drop_duplicates("ma_don_vi")
            .assign(g=lambda x: x["phan_cap_don_vi"].map(_phan_cap_to_group))
            .dropna(subset=["g"])
            .set_index("ma_don_vi")["g"]
            .to_dict()
        )
        if pc_group:
            df["group"] = df["ma_don_vi"].map(pc_group).fillna(df["group"])

    # Fallback: derive ma_don_vi from folder_name for units with no file
    def _folder_to_ma(folder_name):
        m = re.match(r"^\d+\.\s*(.+)", str(folder_name))
        return m.group(1).strip() if m else folder_name

    df["ma_don_vi"] = df["ma_don_vi"].fillna(df["folder_name"].apply(_folder_to_ma))
    df["ten_don_vi"] = df["ten_don_vi"].fillna(df["ma_don_vi"])

    return df


@st.cache_data(ttl=3600)
def load_data() -> dict:
    df_list_files, paths, df_report_raw, df_kd_raw, df_rc_raw, df_adl_raw = _run_async(
        _fetch_all()
    )

    df_report = _clean_report(df_report_raw)
    df_key_drivers = _clean_key_drivers(df_kd_raw)
    df_ratio_commit = _clean_ratio_commit(df_rc_raw)
    df_adl = _clean_adl(df_adl_raw)

    df_summary = _build_summary(
        df_list_files, paths,
        df_report_raw, df_kd_raw, df_rc_raw, df_adl_raw,
        df_report, df_key_drivers,
    )

    return {
        "report": df_report,
        "key_drivers": df_key_drivers,
        "ratio_commit": df_ratio_commit,
        "adl": df_adl,
        "summary": df_summary,
    }
