# app.py
# Battlefield 6 practical STK / TTK Monte Carlo calculator
# FINAL single-file Streamlit app rebuilt from the working Monte Carlo engine.
#
# Fixed model:
# - Pre-1.3.3.0 automatic-primary weapon data (37 weapons)
# - Selectable vertical recoil control for all weapons: 0%, 50%, 70%, or 80%
# - Monte Carlo trials: exactly 262,144 per weapon and selected distance
# - Practical STK includes every missed round fired before the kill
# - If the unconditional hit probability of a shot index falls to 20% or less,
#   the next shot is delayed until 0.2 s after the previous shot
# - No external JSON/CSV files are required
#
# Run:
#   pip install streamlit numpy pandas
#   streamlit run app.py

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

try:
    import streamlit as st
except ImportError:  # allows command-line self-test without Streamlit installed
    st = None


# ============================================================
# Fixed model settings
# ============================================================

BUILD_ID = "BF6-MC-262144-VERTICAL-CONTROL-FINAL-R5"
MODEL_VERSION = "pre-1.3.3.0"
TRIALS_PER_WEAPON = 262_144
VERTICAL_RECOIL_CONTROL_OPTIONS = (0, 50, 70, 80)
DEFAULT_VERTICAL_RECOIL_CONTROL_PERCENT = 0
BASE_RANDOM_SEED = 20_260_702
MAX_SHOTS = 240
TARGET_HEALTH = 100.0
HEAD_MULTIPLIER = 1.34
AIM_POINT_Y_M = 1.315
LOW_ACCURACY_THRESHOLD = 0.20
LOW_ACCURACY_INTERVAL_S = 0.20
SIMULATION_FRAME_S = 1.0 / 60.0
DAMAGE_EPSILON = 1e-6


# ============================================================
# Embedded weapon data — 37 weapons, no external files
# ============================================================

WEAPON_DATA: list[dict[str, Any]] = [{'id': 'm433', 'class': 'Assault', 'weapon': 'M433', 'rpm': 830.769, 'velocity_mps': 670.0, 'mag_size': 30, 'reload_s': 2.384, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.78, 'recoil_mean_direction_deg': -22.0, 'recoil_direction_variation_per_side_deg': 50.9, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'b36a4', 'class': 'Assault', 'weapon': 'B36A4', 'rpm': 719.999, 'velocity_mps': 780.0, 'mag_size': 30, 'reload_s': 2.384, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.7, 'recoil_mean_direction_deg': -15.0, 'recoil_direction_variation_per_side_deg': 37.4, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'sor556mk2', 'class': 'Assault', 'weapon': 'SOR-556 MK2', 'rpm': 568.421, 'velocity_mps': 800.0, 'mag_size': 30, 'reload_s': 2.384, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.62, 'recoil_mean_direction_deg': -9.0, 'recoil_direction_variation_per_side_deg': 17.3, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'ak4d', 'class': 'Assault', 'weapon': 'AK4D', 'rpm': 514.285, 'velocity_mps': 720.0, 'mag_size': 20, 'reload_s': 2.467, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 20.0}], 'recoil_amount_deg': 0.85, 'recoil_mean_direction_deg': -18.0, 'recoil_direction_variation_per_side_deg': 25.4, 'recoil_decay_factor': 104.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.459, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.392, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'tr7', 'class': 'Assault', 'weapon': 'TR-7', 'rpm': 719.999, 'velocity_mps': 648.0, 'mag_size': 20, 'reload_s': 2.4, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 20.0}], 'recoil_amount_deg': 1.16, 'recoil_mean_direction_deg': 20.0, 'recoil_direction_variation_per_side_deg': 47.1, 'recoil_decay_factor': 104.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.459, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.392, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'kord6p67', 'class': 'Assault', 'weapon': 'KORD 6P67', 'rpm': 899.999, 'velocity_mps': 760.0, 'mag_size': 30, 'reload_s': 2.45, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.55, 'recoil_mean_direction_deg': 18.0, 'recoil_direction_variation_per_side_deg': 35.3, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'nvo228e', 'class': 'Assault', 'weapon': 'NVO-228E', 'rpm': 654.545, 'velocity_mps': 671.0, 'mag_size': 30, 'reload_s': 2.5, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 27.25}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 21.4}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.75, 'recoil_mean_direction_deg': -12.0, 'recoil_direction_variation_per_side_deg': 36.8, 'recoil_decay_factor': 76.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.24, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.307, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'l85a3', 'class': 'Assault', 'weapon': 'L85A3', 'rpm': 635.294, 'velocity_mps': 814.0, 'mag_size': 30, 'reload_s': 2.767, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.67, 'recoil_mean_direction_deg': 12.0, 'recoil_direction_variation_per_side_deg': 29.4, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'vcr2', 'class': 'Assault', 'weapon': 'VCR-2', 'rpm': 899.999, 'velocity_mps': 704.0, 'mag_size': 30, 'reload_s': 2.434, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.81, 'recoil_mean_direction_deg': 18.0, 'recoil_direction_variation_per_side_deg': 64.9, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm16a4', 'class': 'Assault', 'weapon': 'M16A4', 'rpm': 771.0, 'velocity_mps': 720.0, 'mag_size': 30, 'reload_s': 2.2, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.71, 'recoil_mean_direction_deg': -21.0, 'recoil_direction_variation_per_side_deg': 46.4, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 7.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm4a1', 'class': 'Carbine', 'weapon': 'M4A1', 'rpm': 899.999, 'velocity_mps': 630.0, 'mag_size': 30, 'reload_s': 2.2, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.86, 'recoil_mean_direction_deg': -18.0, 'recoil_direction_variation_per_side_deg': 37.9, 'recoil_decay_factor': 57.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.045, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.228, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm277', 'class': 'Carbine', 'weapon': 'M277', 'rpm': 719.999, 'velocity_mps': 624.0, 'mag_size': 20, 'reload_s': 2.384, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 20.0}], 'recoil_amount_deg': 0.96, 'recoil_mean_direction_deg': -22.0, 'recoil_direction_variation_per_side_deg': 39.4, 'recoil_decay_factor': 76.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.24, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.307, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'ak205', 'class': 'Carbine', 'weapon': 'AK-205', 'rpm': 719.999, 'velocity_mps': 737.0, 'mag_size': 30, 'reload_s': 2.484, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 17.83333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 15.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.51, 'recoil_mean_direction_deg': 6.0, 'recoil_direction_variation_per_side_deg': 7.8, 'recoil_decay_factor': 48.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 0.905, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.179, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm417a2', 'class': 'Carbine', 'weapon': 'M417 A2', 'rpm': 654.545, 'velocity_mps': 600.0, 'mag_size': 20, 'reload_s': 2.467, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 27.25}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 21.4}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.95, 'recoil_mean_direction_deg': -16.0, 'recoil_direction_variation_per_side_deg': 19.8, 'recoil_decay_factor': 76.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.24, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.307, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'grtbc', 'class': 'Carbine', 'weapon': 'GRT-BC', 'rpm': 830.769, 'velocity_mps': 599.0, 'mag_size': 30, 'reload_s': 2.5, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.82, 'recoil_mean_direction_deg': 16.0, 'recoil_direction_variation_per_side_deg': 31.2, 'recoil_decay_factor': 57.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.045, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.228, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'qbz192', 'class': 'Carbine', 'weapon': 'QBZ-192', 'rpm': 771.428, 'velocity_mps': 644.0, 'mag_size': 30, 'reload_s': 2.567, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.78, 'recoil_mean_direction_deg': -10.0, 'recoil_direction_variation_per_side_deg': 23.5, 'recoil_decay_factor': 57.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.045, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.228, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'sg553r', 'class': 'Carbine', 'weapon': 'SG 553R', 'rpm': 719.999, 'velocity_mps': 519.0, 'mag_size': 30, 'reload_s': 2.5, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.82, 'recoil_mean_direction_deg': -20.0, 'recoil_direction_variation_per_side_deg': 43.3, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'sor300sc', 'class': 'Carbine', 'weapon': 'SOR-300SC', 'rpm': 599.999, 'velocity_mps': 563.0, 'mag_size': 30, 'reload_s': 2.25, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.76, 'recoil_mean_direction_deg': -12.0, 'recoil_direction_variation_per_side_deg': 19.2, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'sgx', 'class': 'SMG', 'weapon': 'SGX', 'rpm': 830.769, 'velocity_mps': 402.0, 'mag_size': 30, 'reload_s': 2.517, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.6, 'recoil_mean_direction_deg': -18.0, 'recoil_direction_variation_per_side_deg': 39.8, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'pw5a3', 'class': 'SMG', 'weapon': 'PW5A3', 'rpm': 771.428, 'velocity_mps': 432.0, 'mag_size': 30, 'reload_s': 2.517, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.57, 'recoil_mean_direction_deg': -10.0, 'recoil_direction_variation_per_side_deg': 33.2, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'pw7a2', 'class': 'SMG', 'weapon': 'PW7A2', 'rpm': 947.368, 'velocity_mps': 600.0, 'mag_size': 30, 'reload_s': 2.184, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 16.66666667}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 16.66666667}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 14.28571429}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.52, 'recoil_mean_direction_deg': -10.0, 'recoil_direction_variation_per_side_deg': 33.3, 'recoil_decay_factor': 46.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 0.919, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.166, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'umg40', 'class': 'SMG', 'weapon': 'UMG-40', 'rpm': 635.294, 'velocity_mps': 488.0, 'mag_size': 30, 'reload_s': 2.517, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.61, 'recoil_mean_direction_deg': -16.0, 'recoil_direction_variation_per_side_deg': 17.4, 'recoil_decay_factor': 57.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.045, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.228, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'usg90', 'class': 'SMG', 'weapon': 'USG-90', 'rpm': 899.999, 'velocity_mps': 570.0, 'mag_size': 50, 'reload_s': 3.0, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 17.83333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 15.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.56, 'recoil_mean_direction_deg': 10.0, 'recoil_direction_variation_per_side_deg': 42.8, 'recoil_decay_factor': 48.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 0.905, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.179, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'kv9', 'class': 'SMG', 'weapon': 'KV9', 'rpm': 1079.999, 'velocity_mps': 348.0, 'mag_size': 17, 'reload_s': 2.384, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.54, 'recoil_mean_direction_deg': 22.0, 'recoil_direction_variation_per_side_deg': 57.6, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'scw10', 'class': 'SMG', 'weapon': 'SCW-10', 'rpm': 799.999, 'velocity_mps': 428.0, 'mag_size': 15, 'reload_s': 2.6, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.75, 'recoil_mean_direction_deg': -18.0, 'recoil_direction_variation_per_side_deg': 35.0, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'sl9', 'class': 'SMG', 'weapon': 'SL9', 'rpm': 674.999, 'velocity_mps': 510.0, 'mag_size': 30, 'reload_s': 2.65, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.53, 'recoil_mean_direction_deg': 0.0, 'recoil_direction_variation_per_side_deg': 16.2, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'cz3a1', 'class': 'SMG', 'weapon': 'CZ3A1', 'rpm': 981.818, 'velocity_mps': 360.0, 'mag_size': 30, 'reload_s': 2.217, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429}, {'min_range': 75.0, 'max_range': None, 'damage': 12.5}], 'recoil_amount_deg': 0.7, 'recoil_mean_direction_deg': -15.0, 'recoil_direction_variation_per_side_deg': 59.1, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 6.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'l110', 'class': 'LMG', 'weapon': 'L110', 'rpm': 719.999, 'velocity_mps': 780.0, 'mag_size': 100, 'reload_s': 6.5, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.56, 'recoil_mean_direction_deg': 0.0, 'recoil_direction_variation_per_side_deg': 39.4, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'drsiar', 'class': 'LMG', 'weapon': 'DRS-IAR', 'rpm': 771.428, 'velocity_mps': 720.0, 'mag_size': 30, 'reload_s': 2.467, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.7, 'recoil_mean_direction_deg': -14.0, 'recoil_direction_variation_per_side_deg': 35.2, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 9.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm60', 'class': 'LMG', 'weapon': 'M/60', 'rpm': 514.285, 'velocity_mps': 720.0, 'mag_size': 100, 'reload_s': 7.35, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 20.0}], 'recoil_amount_deg': 0.73, 'recoil_mean_direction_deg': 0.0, 'recoil_direction_variation_per_side_deg': 38.8, 'recoil_decay_factor': 104.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.459, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.392, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'rpkm', 'class': 'LMG', 'weapon': 'RPKM', 'rpm': 553.846, 'velocity_mps': 670.0, 'mag_size': 40, 'reload_s': 2.8, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 27.25}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 21.4}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.66, 'recoil_mean_direction_deg': 5.0, 'recoil_direction_variation_per_side_deg': 22.7, 'recoil_decay_factor': 76.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.24, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 9.0, 'spread_increase_per_shot_deg': 0.307, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm123k', 'class': 'LMG', 'weapon': 'M123K', 'rpm': 830.769, 'velocity_mps': 670.0, 'mag_size': 100, 'reload_s': 6.65, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.61, 'recoil_mean_direction_deg': -10.0, 'recoil_direction_variation_per_side_deg': 55.9, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm250', 'class': 'LMG', 'weapon': 'M250', 'rpm': 674.999, 'velocity_mps': 760.0, 'mag_size': 50, 'reload_s': 5.75, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 25.0}], 'recoil_amount_deg': 0.73, 'recoil_mean_direction_deg': -14.0, 'recoil_direction_variation_per_side_deg': 39.7, 'recoil_decay_factor': 76.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.24, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.307, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'kts100mk8', 'class': 'LMG', 'weapon': 'KTS100 MK8', 'rpm': 514.285, 'velocity_mps': 840.0, 'mag_size': 60, 'reload_s': 3.25, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0}, {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}], 'recoil_amount_deg': 0.52, 'recoil_mean_direction_deg': 8.0, 'recoil_direction_variation_per_side_deg': 10.9, 'recoil_decay_factor': 72.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.2, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 9.0, 'spread_increase_per_shot_deg': 0.27, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm240l', 'class': 'LMG', 'weapon': 'M240L', 'rpm': 599.999, 'velocity_mps': 630.0, 'mag_size': 50, 'reload_s': 4.25, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 20.0}], 'recoil_amount_deg': 0.81, 'recoil_mean_direction_deg': 5.0, 'recoil_direction_variation_per_side_deg': 41.8, 'recoil_decay_factor': 104.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.459, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.392, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'm121a2', 'class': 'LMG', 'weapon': 'M121 A2', 'rpm': 654.545, 'velocity_mps': 600.0, 'mag_size': 50, 'reload_s': 6.267, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0}, {'min_range': 75.0, 'max_range': None, 'damage': 20.0}], 'recoil_amount_deg': 0.8, 'recoil_mean_direction_deg': -7.0, 'recoil_direction_variation_per_side_deg': 39.5, 'recoil_decay_factor': 104.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.459, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.392, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}, {'id': 'rpk74m', 'class': 'LMG', 'weapon': 'RPK-74M', 'rpm': 685.0, 'velocity_mps': 840.0, 'mag_size': 45, 'reload_s': 2.784, 'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0}, {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0}, {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667}, {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667}, {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}], 'recoil_amount_deg': 0.48, 'recoil_mean_direction_deg': 6.0, 'recoil_direction_variation_per_side_deg': 18.9, 'recoil_decay_factor': 55.0, 'recoil_decay_exponent': 1.0, 'recoil_decay_time_exponent': 1.023, 'recoil_decay_offset': 0.06, 'ads_stand_min_deg': 0.05, 'ads_stand_max_deg': 11.0, 'spread_increase_per_shot_deg': 0.21, 'spread_first_shot_multiplier': 1.0, 'spread_firing_decrease_coefficient': 1.22, 'spread_firing_decrease_exponent': 2.5, 'spread_firing_decrease_offset': 1.84, 'spread_not_firing_decrease_coefficient': 0.0, 'spread_not_firing_decrease_exponent': 0.25, 'spread_not_firing_decrease_offset': 7.2, 'spread_radial_distribution_exponent': 0.67, 'source_model_version': 'pre-1.3.3.0'}]
WEAPON_BY_ID = {weapon["id"]: weapon for weapon in WEAPON_DATA}


# ============================================================
# Lightweight cache decorator for self-test environments
# ============================================================

def _cache_data(**kwargs: Any) -> Callable:
    if st is None:
        return lambda function: function
    return st.cache_data(**kwargs)


# ============================================================
# Target geometry
# ============================================================

@dataclass(frozen=True)
class TargetGeometry:
    aim_y_m: float = AIM_POINT_Y_M
    head_half_width_m: float = 0.09
    head_half_height_m: float = 0.115
    head_center_y_m: float = 1.635


TARGET = TargetGeometry()


def _capsule_mask(
    x: np.ndarray,
    y: np.ndarray,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    radius: float,
) -> np.ndarray:
    abx = bx - ax
    aby = by - ay
    denominator = max(abx * abx + aby * aby, 1e-12)
    t = ((x - ax) * abx + (y - ay) * aby) / denominator
    t = np.clip(t, 0.0, 1.0)
    nearest_x = ax + t * abx
    nearest_y = ay + t * aby
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius**2


def classify_target(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (any_hit, head_hit) for the fixed front-facing standing target."""
    head = (
        (x / TARGET.head_half_width_m) ** 2
        + ((y - TARGET.head_center_y_m) / TARGET.head_half_height_m) ** 2
        <= 1.0
    )

    neck = (np.abs(x) <= 0.07) & (y >= 1.48) & (y < 1.52)
    chest = (np.abs(x) <= 0.20) & (y >= 1.15) & (y < 1.48)
    abdomen_pelvis = (np.abs(x) <= 0.18) & (y >= 0.86) & (y < 1.15)

    upper_arms = (
        _capsule_mask(x, y, -0.20, 1.42, -0.28, 1.24, 0.050)
        | _capsule_mask(x, y, 0.20, 1.42, 0.28, 1.24, 0.050)
    )
    forearms_hands = (
        _capsule_mask(x, y, -0.28, 1.24, -0.07, 1.29, 0.045)
        | _capsule_mask(x, y, 0.28, 1.24, 0.07, 1.29, 0.045)
    )
    legs_feet = (
        _capsule_mask(x, y, -0.095, 0.86, -0.095, 0.09, 0.075)
        | _capsule_mask(x, y, 0.095, 0.86, 0.095, 0.09, 0.075)
        | _capsule_mask(x, y, -0.095, 0.09, -0.13, 0.025, 0.070)
        | _capsule_mask(x, y, 0.095, 0.09, 0.13, 0.025, 0.070)
    )

    body = neck | chest | abdomen_pelvis | upper_arms | forearms_hands | legs_feet
    return head | body, head


# ============================================================
# Damage model
# ============================================================

def _ceil_damage(value: float, decimals: int = 3) -> float:
    factor = 10**decimals
    return math.ceil(float(value) * factor - 1e-12) / factor


def damage_at_distance(profile: list[dict[str, Any]], distance_m: float) -> float:
    distance = max(float(distance_m), 0.0)
    for row in profile:
        lower = float(row["min_range"])
        upper = row["max_range"]
        if lower <= distance and (upper is None or distance < float(upper)):
            return _ceil_damage(float(row["damage"]))
    return _ceil_damage(float(profile[-1]["damage"]))


# ============================================================
# Recoil and spread recovery
# ============================================================

def _recoil_affine_coefficients(
    factor: float,
    exponent: float,
    time_exponent: float,
    duration_s: float,
    offset: float,
) -> tuple[float, float] | None:
    """
    For exponent == 1, collapse the 60 Hz recurrence into:
        magnitude_new = max(0, A * magnitude_old - B)
    """
    if abs(exponent - 1.0) > 1e-12:
        return None

    a_total = 1.0
    b_total = 0.0
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(SIMULATION_FRAME_S, duration_s - elapsed)
        elapsed += step
        coefficient = factor * step * (elapsed**time_exponent)
        a_total = (1.0 - coefficient) * a_total
        b_total = (1.0 - coefficient) * b_total + coefficient * offset
    return a_total, b_total


def recover_recoil_axis(
    values: np.ndarray,
    factor: float,
    exponent: float,
    time_exponent: float,
    duration_s: float,
    offset: float,
) -> np.ndarray:
    if duration_s <= 0:
        return values

    affine = _recoil_affine_coefficients(
        factor=factor,
        exponent=exponent,
        time_exponent=time_exponent,
        duration_s=duration_s,
        offset=offset,
    )
    if affine is not None:
        a_total, b_total = affine
        return np.sign(values) * np.maximum(0.0, a_total * np.abs(values) - b_total)

    output = values
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(SIMULATION_FRAME_S, duration_s - elapsed)
        elapsed += step
        decay = (
            (np.abs(output) ** exponent + offset)
            * factor
            * step
            * (elapsed**time_exponent)
        )
        output = np.sign(output) * np.maximum(0.0, np.abs(output) - decay)
    return output


def recover_spread(
    spread_deg: float,
    minimum_deg: float,
    maximum_deg: float,
    duration_s: float,
    coefficient: float,
    exponent: float,
    offset: float,
) -> float:
    output = float(spread_deg)
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(SIMULATION_FRAME_S, duration_s - elapsed)
        elapsed += step
        excess = max(output - minimum_deg, 0.0)
        output -= step * (coefficient * excess**exponent + offset)
        output = min(maximum_deg, max(minimum_deg, output))
    return output


# ============================================================
# Monte Carlo engine
# ============================================================

def _seed_for_condition(distance_m: int) -> int:
    # Same random stream for every weapon at a distance: common random numbers
    # reduce comparison noise between weapons.
    return BASE_RANDOM_SEED + int(distance_m) * 10_007


@_cache_data(show_spinner=False, max_entries=512)
def simulate_weapon(
    weapon_id: str,
    distance_m: int,
    trials: int = TRIALS_PER_WEAPON,
    vertical_recoil_control_percent: int = DEFAULT_VERTICAL_RECOIL_CONTROL_PERCENT,
) -> dict[str, Any]:
    weapon = WEAPON_BY_ID[weapon_id]
    trials = int(trials)
    if trials <= 0:
        raise ValueError("trials must be positive")

    vertical_recoil_control_percent = int(vertical_recoil_control_percent)
    if vertical_recoil_control_percent not in VERTICAL_RECOIL_CONTROL_OPTIONS:
        raise ValueError(
            "vertical_recoil_control_percent must be one of "
            f"{VERTICAL_RECOIL_CONTROL_OPTIONS}"
        )
    vertical_recoil_remaining = np.float32(
        1.0 - vertical_recoil_control_percent / 100.0
    )

    rng = np.random.default_rng(_seed_for_condition(distance_m))

    health = np.full(trials, TARGET_HEALTH, dtype=np.float32)
    alive = np.ones(trials, dtype=bool)
    recoil_x = np.zeros(trials, dtype=np.float32)
    recoil_y = np.zeros(trials, dtype=np.float32)

    kill_shot = np.zeros(trials, dtype=np.int16)
    kill_time_s = np.full(trials, np.nan, dtype=np.float32)
    hits_before_kill = np.zeros(trials, dtype=np.int16)

    rpm = float(weapon["rpm"])
    normal_interval_s = 60.0 / rpm
    magazine_size = max(int(weapon["mag_size"]), 1)
    reload_s = float(weapon["reload_s"])
    rounds_since_reload = 0
    time_s = 0.0

    spread_min = float(weapon["ads_stand_min_deg"])
    spread_max = float(weapon["ads_stand_max_deg"])
    spread_deg = spread_min

    recoil_amount = np.float32(weapon["recoil_amount_deg"])
    recoil_mean = np.float32(weapon["recoil_mean_direction_deg"])
    recoil_variation = float(weapon["recoil_direction_variation_per_side_deg"])
    body_damage = np.float32(damage_at_distance(weapon["damage_profile"], distance_m))
    head_damage = np.float32(_ceil_damage(float(body_damage) * HEAD_MULTIPLIER))

    low_accuracy_shot_count = 0
    first_low_accuracy_shot: int | None = None
    shot_hit_rates: list[float] = []

    for shot_number in range(1, MAX_SHOTS + 1):
        # 1) Spread around the current recoil-displaced aim direction.
        radial_random = rng.random(trials, dtype=np.float32)
        azimuth = rng.random(trials, dtype=np.float32) * np.float32(2.0 * math.pi)
        radial_exponent = np.float32(weapon["spread_radial_distribution_exponent"])
        radius_deg = np.float32(spread_deg) * radial_random**radial_exponent

        bullet_angle_x_deg = recoil_x + radius_deg * np.cos(azimuth)
        bullet_angle_y_deg = recoil_y + radius_deg * np.sin(azimuth)

        impact_x_m = np.float32(distance_m) * np.tan(np.deg2rad(bullet_angle_x_deg))
        impact_y_m = np.float32(AIM_POINT_Y_M) + np.float32(distance_m) * np.tan(
            np.deg2rad(bullet_angle_y_deg)
        )

        hit, head = classify_target(impact_x_m, impact_y_m)
        shot_hit_rate = float(hit.mean())
        shot_hit_rates.append(shot_hit_rate)

        # 2) Apply damage only to engagements that are still alive.
        active_hit = alive & hit
        hits_before_kill += active_hit.astype(np.int16)
        damage = np.where(head, head_damage, body_damage)
        health -= damage * active_hit

        newly_killed = alive & (health <= DAMAGE_EPSILON)
        kill_shot[newly_killed] = shot_number
        kill_time_s[newly_killed] = time_s
        alive[newly_killed] = False

        # No following-shot state is needed once every trial is dead.
        if not np.any(alive):
            break

        # 3) This shot's recoil affects the next shot.
        # Sym direction variation is used exactly as mean ± per-side variation.
        recoil_direction_deg = recoil_mean + rng.uniform(
            -recoil_variation,
            recoil_variation,
            size=trials,
        ).astype(np.float32)
        direction_rad = np.deg2rad(recoil_direction_deg)
        # Player control affects only the vertical component of each new kick.
        # Horizontal recoil is deliberately left unchanged. For example, 70%
        # control leaves 30% of the sampled vertical kick in the weapon state.
        recoil_x += -recoil_amount * np.sin(direction_rad)
        recoil_y += (
            recoil_amount * np.cos(direction_rad) * vertical_recoil_remaining
        )

        # 4) Increase spread after firing.
        spread_increment = float(weapon["spread_increase_per_shot_deg"])
        if shot_number == 1:
            spread_increment *= float(weapon["spread_first_shot_multiplier"])
        spread_deg = min(spread_max, spread_deg + spread_increment)

        # 5) Decide the interval before the next shot.
        rounds_since_reload += 1
        low_accuracy = shot_hit_rate <= LOW_ACCURACY_THRESHOLD
        if low_accuracy:
            low_accuracy_shot_count += 1
            if first_low_accuracy_shot is None:
                first_low_accuracy_shot = shot_number

        if rounds_since_reload >= magazine_size:
            interval_s = reload_s
            rounds_since_reload = 0
            recoil_x.fill(0.0)
            recoil_y.fill(0.0)
            spread_deg = spread_min
        else:
            interval_s = (
                max(normal_interval_s, LOW_ACCURACY_INTERVAL_S)
                if low_accuracy
                else normal_interval_s
            )

            recoil_x = recover_recoil_axis(
                recoil_x,
                factor=float(weapon["recoil_decay_factor"]),
                exponent=float(weapon["recoil_decay_exponent"]),
                time_exponent=float(weapon["recoil_decay_time_exponent"]),
                duration_s=interval_s,
                offset=float(weapon["recoil_decay_offset"]),
            )
            recoil_y = recover_recoil_axis(
                recoil_y,
                factor=float(weapon["recoil_decay_factor"]),
                exponent=float(weapon["recoil_decay_exponent"]),
                time_exponent=float(weapon["recoil_decay_time_exponent"]),
                duration_s=interval_s,
                offset=float(weapon["recoil_decay_offset"]),
            )

            # The normal shot interval uses firing recovery. Any extra part of the
            # 0.2 s pause uses not-firing recovery.
            firing_recovery_s = min(normal_interval_s, interval_s)
            spread_deg = recover_spread(
                spread_deg,
                minimum_deg=spread_min,
                maximum_deg=spread_max,
                duration_s=firing_recovery_s,
                coefficient=float(weapon["spread_firing_decrease_coefficient"]),
                exponent=float(weapon["spread_firing_decrease_exponent"]),
                offset=float(weapon["spread_firing_decrease_offset"]),
            )

            non_firing_recovery_s = max(0.0, interval_s - firing_recovery_s)
            if non_firing_recovery_s > 0:
                spread_deg = recover_spread(
                    spread_deg,
                    minimum_deg=spread_min,
                    maximum_deg=spread_max,
                    duration_s=non_firing_recovery_s,
                    coefficient=float(weapon["spread_not_firing_decrease_coefficient"]),
                    exponent=float(weapon["spread_not_firing_decrease_exponent"]),
                    offset=float(weapon["spread_not_firing_decrease_offset"]),
                )

        time_s += interval_s

    killed = kill_shot > 0
    killed_count = int(killed.sum())
    kill_probability = killed_count / trials

    if killed_count == 0:
        return {
            "class": weapon["class"],
            "weapon": weapon["weapon"],
            "rpm": rpm,
            "distance_m": int(distance_m),
            "trials": trials,
            "vertical_recoil_control_percent": vertical_recoil_control_percent,
            "practical_stk_mean": math.nan,
            "practical_stk_median": math.nan,
            "practical_stk_p80": math.nan,
            "ttk_mean_s": math.nan,
            "ttk_median_s": math.nan,
            "ttk_p80_s": math.nan,
            "accuracy": math.nan,
            "kill_probability": 0.0,
            "first_low_accuracy_shot": first_low_accuracy_shot,
            "low_accuracy_shot_count": low_accuracy_shot_count,
        }

    successful_shots = kill_shot[killed].astype(np.float64)
    successful_times = kill_time_s[killed].astype(np.float64)
    total_fired = float(successful_shots.sum())
    total_hits = float(hits_before_kill[killed].sum())

    return {
        "class": weapon["class"],
        "weapon": weapon["weapon"],
        "rpm": rpm,
        "distance_m": int(distance_m),
        "trials": trials,
        "vertical_recoil_control_percent": vertical_recoil_control_percent,
        "practical_stk_mean": float(successful_shots.mean()),
        "practical_stk_median": float(np.median(successful_shots)),
        "practical_stk_p80": float(np.quantile(successful_shots, 0.80)),
        "ttk_mean_s": float(successful_times.mean()),
        "ttk_median_s": float(np.median(successful_times)),
        "ttk_p80_s": float(np.quantile(successful_times, 0.80)),
        "accuracy": total_hits / total_fired if total_fired else math.nan,
        "kill_probability": kill_probability,
        "first_low_accuracy_shot": first_low_accuracy_shot,
        "low_accuracy_shot_count": low_accuracy_shot_count,
    }


@_cache_data(show_spinner=False, max_entries=64)
def simulate_all_weapons(
    distance_m: int,
    trials: int = TRIALS_PER_WEAPON,
    vertical_recoil_control_percent: int = DEFAULT_VERTICAL_RECOIL_CONTROL_PERCENT,
) -> pd.DataFrame:
    rows = [
        simulate_weapon(
            weapon["id"],
            int(distance_m),
            int(trials),
            int(vertical_recoil_control_percent),
        )
        for weapon in WEAPON_DATA
    ]
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(
        ["ttk_mean_s", "practical_stk_mean", "weapon"],
        ascending=[True, True, True],
        na_position="last",
    ).reset_index(drop=True)
    frame.insert(0, "rank", np.arange(1, len(frame) + 1))
    return frame


# ============================================================
# Streamlit UI
# ============================================================

def _format_results(results: pd.DataFrame) -> pd.DataFrame:
    output = results.copy()
    output["practical_stk_mean"] = output["practical_stk_mean"].round(3)
    output["practical_stk_median"] = output["practical_stk_median"].round(0).astype("Int64")
    output["practical_stk_p80"] = output["practical_stk_p80"].round(0).astype("Int64")
    output["ttk_mean_s"] = output["ttk_mean_s"].round(4)
    output["ttk_median_s"] = output["ttk_median_s"].round(4)
    output["ttk_p80_s"] = output["ttk_p80_s"].round(4)
    output["accuracy"] = (output["accuracy"] * 100.0).round(2)
    output["kill_probability"] = (output["kill_probability"] * 100.0).round(3)

    return output.rename(
        columns={
            "rank": "순위",
            "class": "종류",
            "weapon": "총기",
            "rpm": "RPM",
            "vertical_recoil_control_percent": "수직 반동 제어 (%)",
            "practical_stk_mean": "실전 STK 평균",
            "practical_stk_median": "실전 STK 중앙값",
            "practical_stk_p80": "실전 STK P80",
            "ttk_mean_s": "TTK 평균 (초)",
            "ttk_median_s": "TTK 중앙값 (초)",
            "ttk_p80_s": "TTK P80 (초)",
            "accuracy": "명중률 (%)",
            "kill_probability": "처치 성공률 (%)",
            "first_low_accuracy_shot": "첫 20% 이하 발차",
            "low_accuracy_shot_count": "20% 이하 발차 수",
            "trials": "시행 횟수",
        }
    )


def render_app() -> None:
    if st is None:
        raise RuntimeError("Streamlit is not installed")

    st.set_page_config(page_title="BF6 Practical STK / TTK", layout="wide")
    st.title("Battlefield 6 실전 STK / TTK")
    st.caption(
        f"BUILD {BUILD_ID} · {MODEL_VERSION} · 총기당 {TRIALS_PER_WEAPON:,}회 고정"
    )

    control_col, distance_col = st.columns([1.0, 2.0])
    with control_col:
        vertical_recoil_control_percent = st.radio(
            "수직 반동 제어",
            options=list(VERTICAL_RECOIL_CONTROL_OPTIONS),
            index=0,
            horizontal=True,
            format_func=lambda value: f"{value}%",
            help=(
                "각 발의 수직 반동 성분만 선택한 비율만큼 상쇄합니다. "
                "수평 반동과 스프레드는 바뀌지 않습니다."
            ),
        )
    with distance_col:
        distance_m = st.slider(
            "거리 (m)", min_value=1, max_value=150, value=30, step=1
        )

    st.info(
        "실전 STK는 빗나간 탄까지 포함해 처치까지 실제 발사한 총탄 수입니다. "
        "선택한 수직 반동 제어율은 모든 총기에 동일하게 적용되며 수평 반동에는 적용되지 않습니다. "
        "한 발차의 고정 코호트 명중률이 20% 이하가 되면 다음 발은 직전 발사 0.2초 후에 나갑니다. "
        "같은 거리·같은 제어율에서 끝난 총기는 캐시에서 즉시 불러옵니다. "
        "다른 제어율을 처음 선택하면 해당 조건을 새로 계산합니다."
    )

    calculate = st.button(
        f"37종 전체 × {TRIALS_PER_WEAPON:,}회 계산 · 수직 제어 {vertical_recoil_control_percent}%",
        type="primary",
        use_container_width=True,
    )

    request_key = (
        f"distance-{int(distance_m)}-vertical-control-"
        f"{int(vertical_recoil_control_percent)}"
    )
    if calculate:
        st.session_state["bf6_requested_key"] = request_key

    if st.session_state.get("bf6_requested_key") != request_key:
        st.warning("거리를 정한 뒤 계산 버튼을 누르세요.")
        return

    progress = st.progress(0.0, text="계산 준비 중…")
    status = st.empty()
    rows: list[dict[str, Any]] = []
    for index, weapon in enumerate(WEAPON_DATA, start=1):
        status.write(
            f"{index}/{len(WEAPON_DATA)} — {weapon['class']} | {weapon['weapon']} "
            f"({TRIALS_PER_WEAPON:,}회)"
        )
        rows.append(
            simulate_weapon(
                weapon_id=weapon["id"],
                distance_m=int(distance_m),
                trials=TRIALS_PER_WEAPON,
                vertical_recoil_control_percent=int(
                    vertical_recoil_control_percent
                ),
            )
        )
        progress.progress(
            index / len(WEAPON_DATA),
            text=f"{index}/{len(WEAPON_DATA)} 완료",
        )

    progress.empty()
    status.empty()
    results = pd.DataFrame(rows).sort_values(
        ["ttk_mean_s", "practical_stk_mean", "weapon"],
        ascending=[True, True, True],
        na_position="last",
    ).reset_index(drop=True)
    results.insert(0, "rank", np.arange(1, len(results) + 1))

    view = _format_results(results)
    columns = [
        "순위",
        "종류",
        "총기",
        "RPM",
        "수직 반동 제어 (%)",
        "실전 STK 평균",
        "실전 STK 중앙값",
        "실전 STK P80",
        "TTK 평균 (초)",
        "TTK 중앙값 (초)",
        "TTK P80 (초)",
        "명중률 (%)",
        "처치 성공률 (%)",
        "첫 20% 이하 발차",
        "시행 횟수",
    ]

    st.subheader(f"{int(distance_m)}m — 자동화기 37종")
    st.dataframe(view[columns], use_container_width=True, hide_index=True)

    csv_bytes = view[columns].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "현재 결과 CSV 다운로드",
        data=csv_bytes,
        file_name=(
            f"bf6_mc_{int(distance_m)}m_vcontrol-"
            f"{int(vertical_recoil_control_percent)}pct_"
            f"{TRIALS_PER_WEAPON}.csv"
        ),
        mime="text/csv",
    )

    with st.expander("계산 정의"):
        st.write(
            {
                "시행 횟수": f"총기마다 정확히 {TRIALS_PER_WEAPON:,}회",
                "수직 반동 제어": f"{vertical_recoil_control_percent}%",
                "제어 적용 방식": (
                    "매 발 새로 발생한 수직 반동 성분에만 적용; "
                    "수평 반동·스프레드는 미변경"
                ),
                "조준점": f"가슴 중앙 y={AIM_POINT_Y_M}m",
                "반동 방향": "평균 방향 ± Sym per-side variation",
                "실전 STK": "빗나간 탄을 포함한 처치 발차",
                "TTK": "첫 발 0초부터 치명탄 발사 시점까지; 재장전·0.2초 휴식 포함",
                "명중률": "성공한 교전에서 처치까지 명중탄 / 발사탄",
                "20% 규칙": "해당 발차 명중률 ≤20%이면 다음 발까지 총 간격 0.2초",
                "탄속/비행시간": "TTK에 미포함",
                "데미지 모델": MODEL_VERSION,
            }
        )


def self_test() -> None:
    # Small smoke tests only; the app itself always uses 262,144 trials.
    results = [
        simulate_weapon(
            "m433",
            distance_m=20,
            trials=2_048,
            vertical_recoil_control_percent=control,
        )
        for control in VERTICAL_RECOIL_CONTROL_OPTIONS
    ]
    result = results[0]
    required = {
        "practical_stk_mean",
        "ttk_mean_s",
        "accuracy",
        "kill_probability",
    }
    missing = required - set(result)
    if missing:
        raise RuntimeError(f"self-test missing keys: {sorted(missing)}")
    if not (0.0 <= float(result["kill_probability"]) <= 1.0):
        raise RuntimeError("invalid kill probability")
    for control, control_result in zip(VERTICAL_RECOIL_CONTROL_OPTIONS, results):
        if int(control_result["vertical_recoil_control_percent"]) != control:
            raise RuntimeError("vertical recoil control was not preserved")
        if not (0.0 <= float(control_result["kill_probability"]) <= 1.0):
            raise RuntimeError("invalid kill probability")
    print("SELF-TEST OK")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    elif st is None:
        print("Streamlit is not installed. Run: pip install streamlit numpy pandas")
    else:
        render_app()
