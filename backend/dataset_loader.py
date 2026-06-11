"""
dataset_loader.py
Load and manage AIS ship dataset for the Maritime Weather Intelligence Agent.
"""

import pandas as pd
import numpy as np
import os
from typing import Optional


REQUIRED_COLUMNS = ["mmsi", "vessel_name", "latitude", "longitude", "timestamp", "speed", "course", "status"]

class DatasetLoader:
    """Loads and manages AIS vessel data from CSV."""

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath
        self.df: Optional[pd.DataFrame] = None

    def load(self) -> pd.DataFrame:
        """Load the dataset from the configured file."""
        if not self.filepath:
            raise ValueError("No dataset file configured.")
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Dataset file not found: {self.filepath}")

        self.df = pd.read_csv(self.filepath)
        self.df = self._validate_and_clean(self.df)
        print(f"[DatasetLoader] Loaded {len(self.df)} ships from {self.filepath}")
        return self.df

    def _validate_and_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        # Ensure required columns exist
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = df.dropna(subset=["latitude", "longitude", "mmsi"])
        df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df["speed"]     = pd.to_numeric(df["speed"],     errors="coerce").fillna(0)
        df["course"]    = pd.to_numeric(df["course"],    errors="coerce").fillna(0)
        df = df.dropna(subset=["latitude", "longitude"])
        df = df[(df["latitude"].between(-90, 90)) & (df["longitude"].between(-180, 180))]

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        return df.reset_index(drop=True)

    def get_vessel_list(self) -> list:
        """Return list of (mmsi, vessel_name) tuples."""
        if self.df is None:
            self.load()
        return list(zip(self.df["mmsi"].astype(str), self.df["vessel_name"]))

    def get_vessel_by_mmsi(self, mmsi: str) -> Optional[dict]:
        """Return a single vessel record as dict."""
        if self.df is None:
            self.load()
        row = self.df[self.df["mmsi"].astype(str) == str(mmsi)]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def get_all_vessels(self) -> pd.DataFrame:
        if self.df is None:
            self.load()
        return self.df.copy()
