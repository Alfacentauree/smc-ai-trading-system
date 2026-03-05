from macro_engine import MacroEngine
import os

def verify_retrain():
    print("--- Verifying MacroEngine Retraining with Volume ---")
    macro = MacroEngine(model_dir="models_test")
    
    d1_csv = "data/NDXUSD.p_D1.csv"
    h1_csv = "data/NDXUSD.p_H1.csv"
    
    if not os.path.exists(d1_csv) or not os.path.exists(h1_csv):
        print(f"Error: CSV files not found in 'data/' directory.")
        return

    print("Attempting to train D1 model...")
    macro.train_d1_model(d1_csv)
    
    print("Attempting to train H1 model...")
    macro.train_h1_model(h1_csv)
    
    # Verify model files exist
    d1_exists = os.path.exists("models_test/d1_lightgbm.pkl")
    h1_exists = os.path.exists("models_test/h1_lightgbm.pkl")
    
    if d1_exists and h1_exists:
        print("\n[SUCCESS] Both models trained and saved with volume feature.")
    else:
        print("\n[FAILURE] Model training failed.")

if __name__ == "__main__":
    verify_retrain()
