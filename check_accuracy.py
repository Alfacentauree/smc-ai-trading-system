from macro_engine import MacroEngine
import os
import pandas as pd

def check_extended_accuracy():
    print("--- Detailed Accuracy Check (Extended Datasets) ---")
    macro = MacroEngine(model_dir="models_check")
    
    # Larger datasets for better stats
    h1_large = "data/NDXUSD.p_H1_202001100000_202602271800.csv"
    m15_standard = "data/NDXUSD.p_M15.csv"
    
    if os.path.exists(h1_large):
        print("\n[H1 Model] Testing on data from 2020 to 2026...")
        macro.train_h1_model(h1_large)
    else:
        print("\nH1 Large file not found. Using standard H1.")
        macro.train_h1_model("data/NDXUSD.p_H1.csv")

    if os.path.exists(m15_standard):
        print("\n[M15 Model] Testing on standard M15...")
        macro.train_m15_model(m15_standard)
    else:
        print("\nM15 standard file not found.")

if __name__ == "__main__":
    check_extended_accuracy()
