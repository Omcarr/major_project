import os
import numpy as np
import pandas as pd
from scipy.signal import welch

bands = {
    'delta': (0.5, 4),
    'theta': (4, 8),
    'alpha': (8, 12),
    'beta': (12, 30),
}

def extract_features_from_signal(signal, fs=128):
    features = {
        'mean': np.mean(signal),
        'std': np.std(signal),
        'max': np.max(signal),
        'min': np.min(signal),
    }
    freqs, psd = welch(signal, fs=fs)
    total_power = np.sum(psd)
    for band, (low, high) in bands.items():
        band_power = np.sum(psd[(freqs >= low) & (freqs <= high)])
        features[f'bandpower_{band}'] = band_power / total_power if total_power > 0 else 0
    return features

def extract_patient_features(patient_dir):
    features = {}
    for file in os.listdir(patient_dir):
        if file.endswith('.txt'):
            channel = os.path.splitext(file)[0]
            signal = np.loadtxt(os.path.join(patient_dir, file))
            feats = extract_features_from_signal(signal)
            for k, v in feats.items():
                features[f'{channel}_{k}'] = v
    return features

# Set your base EEG folder
base_dir = 'EEG_data'  # <-- Replace with your actual path

data = []

for class_label, label_id in [('Healthy', 0), ('AD', 1)]:
    for eye_state in ['Eyes_open', 'Eyes_closed']:
        path = os.path.join(base_dir, class_label, eye_state)
        for patient_folder in os.listdir(path):
            patient_path = os.path.join(path, patient_folder)
            if os.path.isdir(patient_path):
                features = extract_patient_features(patient_path)
                features['label'] = label_id
                features['eye_state'] = eye_state
                features['patient_id'] = f'{class_label}_{eye_state}_{patient_folder}'
                data.append(features)

df = pd.DataFrame(data)
df.fillna(0, inplace=True)
df.to_csv('eeg_features_all_patients.csv', index=False)
print("Saved features to eeg_features_all_patients.csv")
