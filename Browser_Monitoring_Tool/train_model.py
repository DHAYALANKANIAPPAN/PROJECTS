import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os


VECT_FILE = "vectorizer.pkl"
MODEL_FILE = "category_model.pkl"
DATA_FILE = "training_data.csv"


if not os.path.exists(DATA_FILE):
    print(f"[ERROR] Training data file '{DATA_FILE}' not found!")
    exit(1)

# Load training data
df = pd.read_csv(DATA_FILE)
if df.empty or not all(col in df.columns for col in ['url','title','category']):
    print("[ERROR] CSV must have 'url', 'title', 'category' columns and not be empty!")
    exit(1)

# Combine url + title for training
texts = (df['title'].fillna('') + ' ' + df['url'].fillna('')).tolist()
labels = df['category'].tolist()

# Split for validation
X_train, X_test, y_train, y_test = train_test_split(texts, labels, test_size=0.2, random_state=42)

# Vectorize
vectorizer = TfidfVectorizer(ngram_range=(1,2))
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# Train model
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train_vec, y_train)

# Save model
joblib.dump(vectorizer, VECT_FILE)
joblib.dump(clf, MODEL_FILE)

print("[ML] Training completed.")
print(f"[ML] Vectorizer saved as '{VECT_FILE}'")
print(f"[ML] Classifier saved as '{MODEL_FILE}'")

# Evaluate
y_pred = clf.predict(X_test_vec)
print("\n[ML] Test Set Performance:")
print(classification_report(y_test, y_pred))
