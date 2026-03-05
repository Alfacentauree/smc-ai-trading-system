import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import os
import joblib

class MacroEngine:
    def __init__(self, model_dir="smc_ai_trading_system/models"):
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.h1_model = None
        self.m15_model = None
        self.h1_bias_cache = {} # {datetime: probability}
        self.m15_bias_cache = {} # {datetime: probability}
        self.load_models()

    def load_models(self):
        """Loads pre-trained models from disk if available."""
        h1_path = os.path.join(self.model_dir, "h1_lightgbm.pkl")
        m15_path = os.path.join(self.model_dir, "m15_lightgbm.pkl")
        
        if os.path.exists(h1_path):
            self.h1_model = joblib.load(h1_path)
            print(f"[MACRO] Loaded H1 Model from {h1_path}")
        
        if os.path.exists(m15_path):
            self.m15_model = joblib.load(m15_path)
            print(f"[MACRO] Loaded M15 Model from {m15_path}")

    def prepare_features(self, df, include_target=True):
        """Standard SMC-focused features for ML models."""
        df = df.copy()
        # Returns and Momentum
        df['returns'] = df['close'].pct_change()
        df['range'] = (df['high'] - df['low']) / df['close']
        df['volatility'] = df['returns'].rolling(10).std()
        
        # Relative Price Position
        df['sma_20'] = df['close'].rolling(20).mean()
        df['dist_sma'] = (df['close'] - df['sma_20']) / df['sma_20']
        
        # RSI (Trend strength)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Volume features
        if 'volume' in df.columns:
            df['rel_volume'] = df['volume'] / df['volume'].rolling(20).mean()
        else:
            df['rel_volume'] = 1.0 # Fallback
        
        if include_target:
            # Targets: Next candle direction
            df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        return df.dropna()

    def update_bias_cache(self, h1_csv, m15_csv, force_retrain=False):
        """
        Updates the bias caches by either predicting with existing models 
        or training new ones.
        """
        if self.h1_model is None or force_retrain:
            self.train_h1_model(h1_csv)
        else:
            print(f"[MACRO] Updating H1 Cache using existing model...")
            df = pd.read_csv(h1_csv, sep='	')
            mapping = {'<DATE>': 'date', '<TIME>': 'time', '<CLOSE>': 'close', '<HIGH>': 'high', '<LOW>': 'low', '<TICKVOL>': 'volume'}
            df.rename(columns=mapping, inplace=True)
            df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            features_df = self.prepare_features(df, include_target=False)
            X = features_df[['returns', 'range', 'volatility', 'dist_sma', 'rsi', 'rel_volume']]
            probs = self.h1_model.predict_proba(X)[:, 1]
            self.h1_bias_cache = dict(zip(features_df['datetime'], probs))

        if self.m15_model is None or force_retrain:
            self.train_m15_model(m15_csv)
        else:
            print(f"[MACRO] Updating M15 Cache using existing model...")
            df = pd.read_csv(m15_csv, sep='	')
            mapping = {'<DATE>': 'date', '<TIME>': 'time', '<CLOSE>': 'close', '<HIGH>': 'high', '<LOW>': 'low', '<TICKVOL>': 'volume'}
            df.rename(columns=mapping, inplace=True)
            df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            features_df = self.prepare_features(df, include_target=False)
            X = features_df[['returns', 'range', 'volatility', 'dist_sma', 'rsi', 'rel_volume']]
            probs = self.m15_model.predict_proba(X)[:, 1]
            self.m15_bias_cache = dict(zip(features_df['datetime'], probs))

    def train_h1_model(self, h1_csv_path):
        """Train LightGBM on 1H data for HTF Bias."""
        print(f"Training 1H LightGBM Model on {h1_csv_path}...")
        df = pd.read_csv(h1_csv_path, sep='	')
        mapping = {'<DATE>': 'date', '<TIME>': 'time', '<CLOSE>': 'close', '<HIGH>': 'high', '<LOW>': 'low', '<TICKVOL>': 'volume'}
        df.rename(columns=mapping, inplace=True)
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        
        train_df = self.prepare_features(df, include_target=True)
        X = train_df[['returns', 'range', 'volatility', 'dist_sma', 'rsi', 'rel_volume']]
        y = train_df['target']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        self.h1_model = lgb.LGBMClassifier(n_estimators=100, learning_rate=0.05, num_leaves=31, verbose=-1, n_jobs=1)
        self.h1_model.fit(X_train, y_train)
        
        preds = self.h1_model.predict(X_test)
        print(f"1H Model Accuracy: {accuracy_score(y_test, preds):.4f}")
        joblib.dump(self.h1_model, os.path.join(self.model_dir, "h1_lightgbm.pkl"))
        
        cache_df = self.prepare_features(df, include_target=False)
        X_cache = cache_df[['returns', 'range', 'volatility', 'dist_sma', 'rsi', 'rel_volume']]
        probs = self.h1_model.predict_proba(X_cache)[:, 1]
        self.h1_bias_cache = dict(zip(cache_df['datetime'], probs))

    def train_m15_model(self, m15_csv_path):
        """Train LightGBM on 15M data for LTF Bias."""
        print(f"Training 15M Model on {m15_csv_path}...")
        df = pd.read_csv(m15_csv_path, sep='	')
        mapping = {'<DATE>': 'date', '<TIME>': 'time', '<CLOSE>': 'close', '<HIGH>': 'high', '<LOW>': 'low', '<TICKVOL>': 'volume'}
        df.rename(columns=mapping, inplace=True)
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        
        train_df = self.prepare_features(df, include_target=True)
        X = train_df[['returns', 'range', 'volatility', 'dist_sma', 'rsi', 'rel_volume']]
        y = train_df['target']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        self.m15_model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=64, verbose=-1, n_jobs=1)
        self.m15_model.fit(X_train, y_train)
        
        preds = self.m15_model.predict(X_test)
        print(f"15M Model Accuracy: {accuracy_score(y_test, preds):.4f}")
        joblib.dump(self.m15_model, os.path.join(self.model_dir, "m15_lightgbm.pkl"))
        
        cache_df = self.prepare_features(df, include_target=False)
        X_cache = cache_df[['returns', 'range', 'volatility', 'dist_sma', 'rsi', 'rel_volume']]
        probs = self.m15_model.predict_proba(X_cache)[:, 1]
        self.m15_bias_cache = dict(zip(cache_df['datetime'], probs))

    def get_bias(self, timestamp):
        """
        Queries the pre-computed bias for a specific 1m candle timestamp.
        """
        # H1 Bias Alignment (Match by the nearest preceding hour)
        h1_key = timestamp.replace(minute=0, second=0)
        h1_prob = self.h1_bias_cache.get(h1_key, 0.5)
        
        # M15 Bias Alignment (Match by the nearest preceding 15m block)
        m15_minute = (timestamp.minute // 15) * 15
        m15_key = timestamp.replace(minute=m15_minute, second=0)
        m15_prob = self.m15_bias_cache.get(m15_key, 0.5)
        
        return h1_prob, m15_prob

if __name__ == "__main__":
    # This is a demonstration. In a real scenario, you'd provide 1D and 1H files.
    # For now, we simulate the structure.
    print("Macro Engine Initialized.")
