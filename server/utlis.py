import numpy as np


def calculate_fft(eeg_data):
    """
    Calculate FFT of EEG data and return frequency bins and magnitudes.
    """
    if len(eeg_data) == 0:
        return [], []
    n = len(eeg_data)
    eeg_array = np.array(eeg_data)
    fft_result = np.fft.rfft(eeg_array)
    magnitudes = np.abs(fft_result).tolist()
    freq_bins = np.fft.rfftfreq(n, d=1/256).tolist()  # assuming 256 Hz sampling rate
    return freq_bins, magnitudes

def calculate_band_powers(freq_bins, magnitudes):
    """
    Calculate power in standard EEG bands (delta, theta, alpha, beta, gamma).
    Returns a dict with band names and their power.
    """
    bands = {
        "delta": (0.5, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta": (13, 30),
        "gamma": (30, 45),
    }
    band_powers = {}
    for band, (low, high) in bands.items():
        power = 0.0
        for f, mag in zip(freq_bins, magnitudes):
            if low <= f < high:
                power += mag**2
        band_powers[band] = power
    return band_powers


