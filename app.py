# app.py
# Battlefield 6 practical STK / TTK Monte Carlo calculator
# FINAL single-file Streamlit app rebuilt from the working Monte Carlo engine.
#
# Fixed model:
# - Pre-1.3.3.0 automatic-primary weapon/recoil/spread data (37 weapons)
# - Selectable armor: 0, 1, or 2 plates (40 HP each)
# - Armor damage curve uses +10 m extended drop-off ranges
# - Update 1.3.3.0 automatic-weapon body/chest damage vs armor: 0.84x
# - Separate recoil controls: vertical 0/50/70/80%, horizontal 0/20/30%
# - Search and select only the weapons to calculate; autocomplete shows weapon names only
# - Monte Carlo trials: exactly 262,144 per selected weapon and selected distance
# - Practical STK includes every missed round fired before the kill
# - Each Monte Carlo engagement tracks its own consecutive-miss streak
# - After 4 consecutive misses, that engagement waits until 0.2 s after the
#   previous shot before firing again; any hit resets the miss streak
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

BUILD_ID = "BF6-MC-262144-SEPARATE-VH-CONTROL-R9"
MODEL_VERSION = "pre-1.3.3 weapon/recoil/spread + 1.3.3 armor"
TRIALS_PER_WEAPON = 262_144
VERTICAL_RECOIL_CONTROL_OPTIONS = (0, 50, 70, 80)
HORIZONTAL_RECOIL_CONTROL_OPTIONS = (0, 20, 30)
DEFAULT_VERTICAL_RECOIL_CONTROL_PERCENT = 0
DEFAULT_HORIZONTAL_RECOIL_CONTROL_PERCENT = 0
BASE_RANDOM_SEED = 20_260_702
MAX_SHOTS = 240
TARGET_HEALTH = 100.0
HEAD_MULTIPLIER = 1.34
ARMOR_PLATE_OPTIONS = (0, 1, 2)
ARMOR_HP_PER_PLATE = 40.0
ARMOR_DAMAGE_RANGE_EXTENSION_M = 10.0
AUTOMATIC_BODY_DAMAGE_VS_ARMOR_MULTIPLIER = 0.84
AIM_POINT_Y_M = 1.315
CONSECUTIVE_MISSES_BEFORE_PAUSE = 4
MISS_STREAK_PAUSE_INTERVAL_S = 0.20
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


def armor_curve_distance(distance_m: float) -> float:
    """
    REDSEC armor extends every damage drop-off threshold by 10 m.
    Looking up the ordinary curve at max(distance - 10, 0) is equivalent.
    """
    return max(0.0, float(distance_m) - ARMOR_DAMAGE_RANGE_EXTENSION_M)


def automatic_body_damage_vs_armor(
    profile: list[dict[str, Any]],
    distance_m: float,
) -> float:
    shifted_base = damage_at_distance(profile, armor_curve_distance(distance_m))
    return _ceil_damage(
        shifted_base * AUTOMATIC_BODY_DAMAGE_VS_ARMOR_MULTIPLIER
    )


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


def recover_spread_array(
    spread_deg: np.ndarray,
    minimum_deg: float,
    maximum_deg: float,
    duration_s: float,
    coefficient: float,
    exponent: float,
    offset: float,
) -> np.ndarray:
    """Vectorized spread recovery for trials with the same time interval."""
    if duration_s <= 0 or spread_deg.size == 0:
        return spread_deg

    output = spread_deg.astype(np.float32, copy=True)
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(SIMULATION_FRAME_S, duration_s - elapsed)
        elapsed += step
        excess = np.maximum(output - np.float32(minimum_deg), 0.0)
        output -= np.float32(step) * (
            np.float32(coefficient) * excess**np.float32(exponent)
            + np.float32(offset)
        )
        np.clip(output, minimum_deg, maximum_deg, out=output)
    return output


def update_consecutive_miss_streaks(
    streaks: np.ndarray,
    active: np.ndarray,
    hits: np.ndarray,
) -> np.ndarray:
    """
    Update each engagement independently. A hit resets its streak; a miss adds one.
    Returns the active engagements that have just reached the pause threshold.
    """
    active_hits = active & hits
    active_misses = active & ~hits
    streaks[active_hits] = 0
    streaks[active_misses] += 1
    return active & (streaks >= CONSECUTIVE_MISSES_BEFORE_PAUSE)


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
    horizontal_recoil_control_percent: int = DEFAULT_HORIZONTAL_RECOIL_CONTROL_PERCENT,
    armor_plates: int = 0,
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

    horizontal_recoil_control_percent = int(horizontal_recoil_control_percent)
    if horizontal_recoil_control_percent not in HORIZONTAL_RECOIL_CONTROL_OPTIONS:
        raise ValueError(
            "horizontal_recoil_control_percent must be one of "
            f"{HORIZONTAL_RECOIL_CONTROL_OPTIONS}"
        )
    horizontal_recoil_remaining = np.float32(
        1.0 - horizontal_recoil_control_percent / 100.0
    )

    armor_plates = int(armor_plates)
    if armor_plates not in ARMOR_PLATE_OPTIONS:
        raise ValueError(f"armor_plates must be one of {ARMOR_PLATE_OPTIONS}")
    initial_armor_hp = np.float32(armor_plates * ARMOR_HP_PER_PLATE)

    rng = np.random.default_rng(_seed_for_condition(distance_m))

    health = np.full(trials, TARGET_HEALTH, dtype=np.float32)
    armor_hp = np.full(trials, initial_armor_hp, dtype=np.float32)
    alive = np.ones(trials, dtype=bool)
    recoil_x = np.zeros(trials, dtype=np.float32)
    recoil_y = np.zeros(trials, dtype=np.float32)
    time_s = np.zeros(trials, dtype=np.float32)

    kill_shot = np.zeros(trials, dtype=np.int16)
    kill_time_s = np.full(trials, np.nan, dtype=np.float32)
    hits_before_kill = np.zeros(trials, dtype=np.int16)
    consecutive_misses = np.zeros(trials, dtype=np.uint8)
    pause_count = np.zeros(trials, dtype=np.uint16)

    rpm = float(weapon["rpm"])
    normal_interval_s = 60.0 / rpm
    pause_interval_s = max(normal_interval_s, MISS_STREAK_PAUSE_INTERVAL_S)
    magazine_size = max(int(weapon["mag_size"]), 1)
    reload_s = float(weapon["reload_s"])
    rounds_since_reload = 0

    spread_min = float(weapon["ads_stand_min_deg"])
    spread_max = float(weapon["ads_stand_max_deg"])
    spread_deg = np.full(trials, spread_min, dtype=np.float32)

    recoil_amount = np.float32(weapon["recoil_amount_deg"])
    recoil_mean = np.float32(weapon["recoil_mean_direction_deg"])
    recoil_variation = float(weapon["recoil_direction_variation_per_side_deg"])
    # Soldier-health damage uses the selected physical distance.
    health_body_damage = np.float32(
        damage_at_distance(weapon["damage_profile"], distance_m)
    )
    health_head_damage = np.float32(
        _ceil_damage(float(health_body_damage) * HEAD_MULTIPLIER)
    )

    # While any plate HP remains, the armor curve has its drop-off thresholds
    # extended by 10 m. Automatic-weapon body/chest hits then receive the
    # Update 1.3.3.0 0.84x damage-vs-armor multiplier. Head hits retain the
    # model's head multiplier but still use the armor-shifted range curve.
    armor_base_damage = np.float32(
        damage_at_distance(
            weapon["damage_profile"],
            armor_curve_distance(distance_m),
        )
    )
    armor_body_damage = np.float32(
        _ceil_damage(
            float(armor_base_damage)
            * AUTOMATIC_BODY_DAMAGE_VS_ARMOR_MULTIPLIER
        )
    )
    armor_head_damage = np.float32(
        _ceil_damage(float(armor_base_damage) * HEAD_MULTIPLIER)
    )

    for shot_number in range(1, MAX_SHOTS + 1):
        alive_before_shot = alive.copy()

        # 1) Spread around each engagement's current recoil-displaced aim.
        radial_random = rng.random(trials, dtype=np.float32)
        azimuth = rng.random(trials, dtype=np.float32) * np.float32(2.0 * math.pi)
        radial_exponent = np.float32(weapon["spread_radial_distribution_exponent"])
        radius_deg = spread_deg * radial_random**radial_exponent

        bullet_angle_x_deg = recoil_x + radius_deg * np.cos(azimuth)
        bullet_angle_y_deg = recoil_y + radius_deg * np.sin(azimuth)

        impact_x_m = np.float32(distance_m) * np.tan(np.deg2rad(bullet_angle_x_deg))
        impact_y_m = np.float32(AIM_POINT_Y_M) + np.float32(distance_m) * np.tan(
            np.deg2rad(bullet_angle_y_deg)
        )

        hit, head = classify_target(impact_x_m, impact_y_m)

        # 2) Update each engagement's own consecutive-miss state.
        pause_trigger = update_consecutive_miss_streaks(
            consecutive_misses,
            alive_before_shot,
            hit,
        )

        # 3) Apply damage only to engagements that were alive for this shot.
        # Armor is global extra HP: every hit removes plate HP first, and any
        # excess from that same bullet carries into soldier health.
        active_hit = alive_before_shot & hit
        hits_before_kill += active_hit.astype(np.int16)

        armor_active_hit = active_hit & (armor_hp > DAMAGE_EPSILON)
        health_only_hit = active_hit & ~armor_active_hit

        armor_damage = np.where(head, armor_head_damage, armor_body_damage).astype(
            np.float32, copy=False
        )
        health_damage = np.where(
            head, health_head_damage, health_body_damage
        ).astype(np.float32, copy=False)

        if np.any(armor_active_hit):
            armor_before = armor_hp[armor_active_hit].copy()
            incoming = armor_damage[armor_active_hit]
            absorbed = np.minimum(armor_before, incoming)
            overflow = np.maximum(incoming - armor_before, 0.0)
            armor_hp[armor_active_hit] = armor_before - absorbed
            health[armor_active_hit] -= overflow

        if np.any(health_only_hit):
            health[health_only_hit] -= health_damage[health_only_hit]

        newly_killed = alive_before_shot & (health <= DAMAGE_EPSILON)
        kill_shot[newly_killed] = shot_number
        kill_time_s[newly_killed] = time_s[newly_killed]
        alive[newly_killed] = False

        if not np.any(alive):
            break

        # A kill does not schedule a later pause.
        pause_trigger &= alive

        # 4) This shot's recoil affects only surviving engagements' next shot.
        recoil_direction_deg = recoil_mean + rng.uniform(
            -recoil_variation,
            recoil_variation,
            size=trials,
        ).astype(np.float32)
        direction_rad = np.deg2rad(recoil_direction_deg)
        recoil_x[alive] += (
            -recoil_amount
            * np.sin(direction_rad[alive])
            * horizontal_recoil_remaining
        )
        recoil_y[alive] += (
            recoil_amount
            * np.cos(direction_rad[alive])
            * vertical_recoil_remaining
        )

        # 5) Increase spread after firing for surviving engagements.
        spread_increment = float(weapon["spread_increase_per_shot_deg"])
        if shot_number == 1:
            spread_increment *= float(weapon["spread_first_shot_multiplier"])
        spread_deg[alive] = np.minimum(
            np.float32(spread_max),
            spread_deg[alive] + np.float32(spread_increment),
        )

        # 6) Magazine reload supersedes the short miss-streak pause.
        rounds_since_reload += 1
        if rounds_since_reload >= magazine_size:
            time_s[alive] += np.float32(reload_s)
            rounds_since_reload = 0
            recoil_x[alive] = 0.0
            recoil_y[alive] = 0.0
            spread_deg[alive] = np.float32(spread_min)
            consecutive_misses[alive] = 0
            continue

        normal_mask = alive & ~pause_trigger
        pause_mask = alive & pause_trigger

        # The four-miss event causes one actual 0.2 s interval, then the streak resets.
        pause_count[pause_mask] += 1
        consecutive_misses[pause_mask] = 0

        # 7) Recoil recovery. Each group has its own interval.
        if np.any(normal_mask):
            recoil_x[normal_mask] = recover_recoil_axis(
                recoil_x[normal_mask],
                factor=float(weapon["recoil_decay_factor"]),
                exponent=float(weapon["recoil_decay_exponent"]),
                time_exponent=float(weapon["recoil_decay_time_exponent"]),
                duration_s=normal_interval_s,
                offset=float(weapon["recoil_decay_offset"]),
            )
            recoil_y[normal_mask] = recover_recoil_axis(
                recoil_y[normal_mask],
                factor=float(weapon["recoil_decay_factor"]),
                exponent=float(weapon["recoil_decay_exponent"]),
                time_exponent=float(weapon["recoil_decay_time_exponent"]),
                duration_s=normal_interval_s,
                offset=float(weapon["recoil_decay_offset"]),
            )

        if np.any(pause_mask):
            recoil_x[pause_mask] = recover_recoil_axis(
                recoil_x[pause_mask],
                factor=float(weapon["recoil_decay_factor"]),
                exponent=float(weapon["recoil_decay_exponent"]),
                time_exponent=float(weapon["recoil_decay_time_exponent"]),
                duration_s=pause_interval_s,
                offset=float(weapon["recoil_decay_offset"]),
            )
            recoil_y[pause_mask] = recover_recoil_axis(
                recoil_y[pause_mask],
                factor=float(weapon["recoil_decay_factor"]),
                exponent=float(weapon["recoil_decay_exponent"]),
                time_exponent=float(weapon["recoil_decay_time_exponent"]),
                duration_s=pause_interval_s,
                offset=float(weapon["recoil_decay_offset"]),
            )

        # 8) Spread recovery: normal shot interval is firing recovery;
        #    only the extra part of the 0.2 s pause is non-firing recovery.
        if np.any(normal_mask):
            spread_deg[normal_mask] = recover_spread_array(
                spread_deg[normal_mask],
                minimum_deg=spread_min,
                maximum_deg=spread_max,
                duration_s=normal_interval_s,
                coefficient=float(weapon["spread_firing_decrease_coefficient"]),
                exponent=float(weapon["spread_firing_decrease_exponent"]),
                offset=float(weapon["spread_firing_decrease_offset"]),
            )

        if np.any(pause_mask):
            firing_recovery_s = min(normal_interval_s, pause_interval_s)
            spread_deg[pause_mask] = recover_spread_array(
                spread_deg[pause_mask],
                minimum_deg=spread_min,
                maximum_deg=spread_max,
                duration_s=firing_recovery_s,
                coefficient=float(weapon["spread_firing_decrease_coefficient"]),
                exponent=float(weapon["spread_firing_decrease_exponent"]),
                offset=float(weapon["spread_firing_decrease_offset"]),
            )
            non_firing_recovery_s = max(0.0, pause_interval_s - firing_recovery_s)
            if non_firing_recovery_s > 0:
                spread_deg[pause_mask] = recover_spread_array(
                    spread_deg[pause_mask],
                    minimum_deg=spread_min,
                    maximum_deg=spread_max,
                    duration_s=non_firing_recovery_s,
                    coefficient=float(weapon["spread_not_firing_decrease_coefficient"]),
                    exponent=float(weapon["spread_not_firing_decrease_exponent"]),
                    offset=float(weapon["spread_not_firing_decrease_offset"]),
                )

        time_s[normal_mask] += np.float32(normal_interval_s)
        time_s[pause_mask] += np.float32(pause_interval_s)

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
            "horizontal_recoil_control_percent": horizontal_recoil_control_percent,
            "armor_plates": armor_plates,
            "initial_armor_hp": float(initial_armor_hp),
            "health_body_damage": float(health_body_damage),
            "armor_body_damage": float(armor_body_damage),
            "armor_curve_distance_m": float(armor_curve_distance(distance_m)),
            "practical_stk_mean": math.nan,
            "practical_stk_median": math.nan,
            "practical_stk_p80": math.nan,
            "ttk_mean_s": math.nan,
            "ttk_median_s": math.nan,
            "ttk_p80_s": math.nan,
            "accuracy": math.nan,
            "kill_probability": 0.0,
            "pause_count_mean": math.nan,
            "pause_count_median": math.nan,
        }

    successful_shots = kill_shot[killed].astype(np.float64)
    successful_times = kill_time_s[killed].astype(np.float64)
    successful_pauses = pause_count[killed].astype(np.float64)
    total_fired = float(successful_shots.sum())
    total_hits = float(hits_before_kill[killed].sum())

    return {
        "class": weapon["class"],
        "weapon": weapon["weapon"],
        "rpm": rpm,
        "distance_m": int(distance_m),
        "trials": trials,
        "vertical_recoil_control_percent": vertical_recoil_control_percent,
        "horizontal_recoil_control_percent": horizontal_recoil_control_percent,
        "armor_plates": armor_plates,
        "initial_armor_hp": float(initial_armor_hp),
        "health_body_damage": float(health_body_damage),
        "armor_body_damage": float(armor_body_damage),
        "armor_curve_distance_m": float(armor_curve_distance(distance_m)),
        "practical_stk_mean": float(successful_shots.mean()),
        "practical_stk_median": float(np.median(successful_shots)),
        "practical_stk_p80": float(np.quantile(successful_shots, 0.80)),
        "ttk_mean_s": float(successful_times.mean()),
        "ttk_median_s": float(np.median(successful_times)),
        "ttk_p80_s": float(np.quantile(successful_times, 0.80)),
        "accuracy": total_hits / total_fired if total_fired else math.nan,
        "kill_probability": kill_probability,
        "pause_count_mean": float(successful_pauses.mean()),
        "pause_count_median": float(np.median(successful_pauses)),
    }


@_cache_data(show_spinner=False, max_entries=64)
def simulate_all_weapons(
    distance_m: int,
    trials: int = TRIALS_PER_WEAPON,
    vertical_recoil_control_percent: int = DEFAULT_VERTICAL_RECOIL_CONTROL_PERCENT,
    horizontal_recoil_control_percent: int = DEFAULT_HORIZONTAL_RECOIL_CONTROL_PERCENT,
    armor_plates: int = 0,
) -> pd.DataFrame:
    rows = [
        simulate_weapon(
            weapon["id"],
            int(distance_m),
            int(trials),
            int(vertical_recoil_control_percent),
            int(horizontal_recoil_control_percent),
            int(armor_plates),
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
    output["pause_count_mean"] = output["pause_count_mean"].round(3)
    output["pause_count_median"] = output["pause_count_median"].round(0).astype("Int64")

    return output.rename(
        columns={
            "rank": "순위",
            "class": "종류",
            "weapon": "총기",
            "rpm": "RPM",
            "vertical_recoil_control_percent": "수직 반동 제어 (%)",
            "horizontal_recoil_control_percent": "수평 반동 제어 (%)",
            "armor_plates": "방탄판 (장)",
            "initial_armor_hp": "초기 방탄 HP",
            "health_body_damage": "일반 몸통 데미지",
            "armor_body_damage": "방탄 대상 몸통 데미지",
            "armor_curve_distance_m": "방탄 곡선 조회 거리 (m)",
            "practical_stk_mean": "실전 STK 평균",
            "practical_stk_median": "실전 STK 중앙값",
            "practical_stk_p80": "실전 STK P80",
            "ttk_mean_s": "TTK 평균 (초)",
            "ttk_median_s": "TTK 중앙값 (초)",
            "ttk_p80_s": "TTK P80 (초)",
            "accuracy": "명중률 (%)",
            "kill_probability": "처치 성공률 (%)",
            "pause_count_mean": "평균 4연속 미스 휴식 횟수",
            "pause_count_median": "중앙값 휴식 횟수",
            "trials": "시행 횟수",
        }
    )


CLASS_ROW_BACKGROUND = {
    # Muted, semi-transparent backgrounds: category is encoded by the row, not the text.
    "Assault": "rgba(132, 92, 92, 0.24)",
    "Carbine": "rgba(86, 118, 96, 0.24)",
    "SMG": "rgba(83, 102, 127, 0.24)",
    "LMG": "rgba(126, 116, 77, 0.24)",
}


def _style_results_by_class(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply a muted background to every cell in a row according to weapon class."""
    def style_row(row: pd.Series) -> list[str]:
        background = CLASS_ROW_BACKGROUND.get(str(row.get("종류", "")), "transparent")
        return [f"background-color: {background}"] * len(row)

    return frame.style.apply(style_row, axis=1)


def _class_color_legend_html() -> str:
    labels = []
    for class_name in ("Assault", "Carbine", "SMG", "LMG"):
        color = CLASS_ROW_BACKGROUND[class_name]
        labels.append(
            f'<span style="display:inline-block; padding:0.28rem 0.62rem; '
            f'margin:0 0.35rem 0.35rem 0; border-radius:0.35rem; '
            f'background:{color}; border:1px solid rgba(127,127,127,0.22);">'
            f'{class_name}</span>'
        )
    return "".join(labels)


def render_app() -> None:
    if st is None:
        raise RuntimeError("Streamlit is not installed")

    st.set_page_config(page_title="BF6 Practical STK / TTK", layout="wide")
    st.title("Battlefield 6 실전 STK / TTK")
    st.caption(
        f"BUILD {BUILD_ID} · {MODEL_VERSION} · 선택한 총기마다 {TRIALS_PER_WEAPON:,}회 고정"
    )

    weapon_names = sorted(weapon["weapon"] for weapon in WEAPON_DATA)
    weapon_by_name = {weapon["weapon"]: weapon for weapon in WEAPON_DATA}

    st.subheader("총기 검색")
    selected_weapon_names = st.multiselect(
        "계산할 총기",
        options=weapon_names,
        default=[],
        placeholder="총기 이름을 입력하세요 (예: M433)",
    )

    vertical_col, horizontal_col, armor_col, distance_col = st.columns([1.25, 1.15, 1.0, 2.0])
    with vertical_col:
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
    with horizontal_col:
        horizontal_recoil_control_percent = st.radio(
            "수평 반동 제어",
            options=list(HORIZONTAL_RECOIL_CONTROL_OPTIONS),
            index=0,
            horizontal=True,
            format_func=lambda value: f"{value}%",
            help=(
                "각 발의 좌우 반동 성분만 선택한 비율만큼 상쇄합니다. "
                "수직 반동과 스프레드는 바뀌지 않습니다."
            ),
        )
    with armor_col:
        armor_plates = st.radio(
            "방탄판",
            options=list(ARMOR_PLATE_OPTIONS),
            index=0,
            horizontal=True,
            format_func=lambda value: f"{value}장",
            help=(
                "1장당 40 HP입니다. 방탄이 남아 있는 동안 데미지 구간은 "
                "10m 연장되고 자동화기 몸통 데미지는 0.84배가 됩니다."
            ),
        )
    with distance_col:
        distance_m = st.slider(
            "거리 (m)", min_value=1, max_value=150, value=30, step=1
        )

    st.info(
        "선택한 총기만 각각 262,144회 계산합니다. 실전 STK는 빗나간 탄까지 포함해 "
        "처치까지 실제 발사한 총탄 수입니다. 각 몬테카를로 교전에서 4발 연속으로 "
        "빗나가면 다음 발은 직전 발사 0.2초 후에 나가며, 한 발이라도 명중하면 "
        "연속 미스 카운터가 초기화됩니다. 방탄판은 1장당 40 HP이고, 방탄이 남아 "
        "있는 동안 +10m 데미지 구간 연장과 자동화기 몸통 0.84배가 적용됩니다."
    )

    if not selected_weapon_names:
        st.warning("검색창에서 계산할 총기를 한 개 이상 선택하세요.")
        return

    selected_weapons = [weapon_by_name[name] for name in selected_weapon_names]
    selected_ids = tuple(sorted(weapon["id"] for weapon in selected_weapons))

    calculate = st.button(
        f"선택한 {len(selected_weapons)}종 × {TRIALS_PER_WEAPON:,}회 계산 · "
        f"수직 {vertical_recoil_control_percent}% · 수평 {horizontal_recoil_control_percent}% · "
        f"방탄판 {armor_plates}장",
        type="primary",
        use_container_width=True,
    )

    request_key = (
        selected_ids,
        int(distance_m),
        int(vertical_recoil_control_percent),
        int(horizontal_recoil_control_percent),
        int(armor_plates),
    )
    if calculate:
        st.session_state["bf6_requested_key_r9"] = request_key

    if st.session_state.get("bf6_requested_key_r9") != request_key:
        st.warning("총기와 조건을 정한 뒤 계산 버튼을 누르세요.")
        return

    progress = st.progress(0.0, text="계산 준비 중…")
    status = st.empty()
    rows: list[dict[str, Any]] = []
    total_selected = len(selected_weapons)

    for index, weapon in enumerate(selected_weapons, start=1):
        status.write(
            f"{index}/{total_selected} — {weapon['weapon']} "
            f"({weapon['class']}, {TRIALS_PER_WEAPON:,}회)"
        )
        rows.append(
            simulate_weapon(
                weapon_id=weapon["id"],
                distance_m=int(distance_m),
                trials=TRIALS_PER_WEAPON,
                vertical_recoil_control_percent=int(
                    vertical_recoil_control_percent
                ),
                horizontal_recoil_control_percent=int(
                    horizontal_recoil_control_percent
                ),
                armor_plates=int(armor_plates),
            )
        )
        progress.progress(
            index / total_selected,
            text=f"{index}/{total_selected} 완료",
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
        "수평 반동 제어 (%)",
        "방탄판 (장)",
        "초기 방탄 HP",
        "일반 몸통 데미지",
        "방탄 대상 몸통 데미지",
        "실전 STK 평균",
        "실전 STK 중앙값",
        "실전 STK P80",
        "TTK 평균 (초)",
        "TTK 중앙값 (초)",
        "TTK P80 (초)",
        "명중률 (%)",
        "처치 성공률 (%)",
        "평균 4연속 미스 휴식 횟수",
        "중앙값 휴식 횟수",
        "시행 횟수",
    ]

    st.subheader(
        f"{int(distance_m)}m · 방탄판 {int(armor_plates)}장 — 선택한 {len(selected_weapons)}종"
    )
    st.markdown(_class_color_legend_html(), unsafe_allow_html=True)

    table = view[columns].copy()
    styled_table = _style_results_by_class(table)
    st.dataframe(
        styled_table,
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = table.to_csv(index=False).encode("utf-8-sig")
    selected_slug = "-".join(weapon["id"] for weapon in selected_weapons)
    if len(selected_slug) > 80:
        selected_slug = f"{len(selected_weapons)}-weapons"
    st.download_button(
        "현재 결과 CSV 다운로드",
        data=csv_bytes,
        file_name=(
            f"bf6_mc_{selected_slug}_{int(distance_m)}m_vcontrol-"
            f"{int(vertical_recoil_control_percent)}pct_hcontrol-"
            f"{int(horizontal_recoil_control_percent)}pct_"
            f"armor-{int(armor_plates)}_"
            f"{TRIALS_PER_WEAPON}.csv"
        ),
        mime="text/csv",
    )

    with st.expander("계산 정의"):
        st.write(
            {
                "선택 총기": selected_weapon_names,
                "시행 횟수": f"선택한 총기마다 정확히 {TRIALS_PER_WEAPON:,}회",
                "수직 반동 제어": f"{vertical_recoil_control_percent}%",
                "수평 반동 제어": f"{horizontal_recoil_control_percent}%",
                "방탄판": f"{armor_plates}장 / {armor_plates * ARMOR_HP_PER_PLATE:.0f} HP",
                "방탄 데미지 구간": (
                    f"방탄이 남아 있는 동안 모든 구간 경계를 +{ARMOR_DAMAGE_RANGE_EXTENSION_M:.0f}m 연장; "
                    "계산상 실제 거리-10m의 일반 곡선 조회"
                ),
                "방탄 몸통 배율": f"자동화기 {AUTOMATIC_BODY_DAMAGE_VS_ARMOR_MULTIPLIER:.2f}x",
                "방탄 초과 피해": "남은 방탄 HP를 넘는 같은 탄환의 피해는 체력으로 이월",
                "제어 적용 방식": (
                    "매 발 새로 발생한 반동을 수직·수평 성분으로 분해해 각각의 "
                    "선택 비율만큼 상쇄; 스프레드는 미변경"
                ),
                "조준점": f"가슴 중앙 y={AIM_POINT_Y_M}m",
                "반동 방향": "평균 방향 ± Sym per-side variation",
                "실전 STK": "빗나간 탄을 포함한 처치 발차",
                "TTK": "첫 발 0초부터 치명탄 발사 시점까지; 재장전·4연속 미스 후 0.2초 휴식 포함",
                "명중률": "성공한 교전에서 처치까지 명중탄 / 발사탄",
                "4연속 미스 규칙": (
                    "각 교전에서 명중 시 카운터 0; 연속 4회 빗나가면 "
                    "다음 발까지 총 간격 0.2초 후 카운터 0"
                ),
                "표 색상": "Assault/Carbine/SMG/LMG별 저채도 반투명 행 배경",
                "탄속/비행시간": "TTK에 미포함",
                "데미지 모델": MODEL_VERSION,
            }
        )

def self_test() -> None:
    # Deterministic rule test: hit, miss, miss, miss, miss -> pause on final miss.
    streak = np.zeros(1, dtype=np.uint8)
    active = np.array([True])
    sequence = [True, False, False, False, False]
    triggers = []
    for event in sequence:
        trigger = update_consecutive_miss_streaks(
            streak,
            active,
            np.array([event]),
        )
        triggers.append(bool(trigger[0]))
        if trigger[0]:
            streak[0] = 0
    if triggers != [False, False, False, False, True]:
        raise RuntimeError(f"4-miss rule failed: {triggers}")

    # Small Monte Carlo smoke tests only; the app itself always uses 262,144 trials.
    results = [
        simulate_weapon(
            "m433",
            distance_m=20,
            trials=2_048,
            vertical_recoil_control_percent=vertical_control,
            horizontal_recoil_control_percent=horizontal_control,
            armor_plates=armor_plates,
        )
        for armor_plates in ARMOR_PLATE_OPTIONS
        for vertical_control in VERTICAL_RECOIL_CONTROL_OPTIONS
        for horizontal_control in HORIZONTAL_RECOIL_CONTROL_OPTIONS
    ]
    result = results[0]
    required = {
        "practical_stk_mean",
        "ttk_mean_s",
        "accuracy",
        "kill_probability",
        "pause_count_mean",
        "vertical_recoil_control_percent",
        "horizontal_recoil_control_percent",
    }
    missing = required - set(result)
    if missing:
        raise RuntimeError(f"self-test missing keys: {sorted(missing)}")
    if not (0.0 <= float(result["kill_probability"]) <= 1.0):
        raise RuntimeError("invalid kill probability")

    result_index = 0
    for armor_plates in ARMOR_PLATE_OPTIONS:
        for vertical_control in VERTICAL_RECOIL_CONTROL_OPTIONS:
            for horizontal_control in HORIZONTAL_RECOIL_CONTROL_OPTIONS:
                control_result = results[result_index]
                result_index += 1
                if int(control_result["vertical_recoil_control_percent"]) != vertical_control:
                    raise RuntimeError("vertical recoil control was not preserved")
                if int(control_result["horizontal_recoil_control_percent"]) != horizontal_control:
                    raise RuntimeError("horizontal recoil control was not preserved")
                if int(control_result["armor_plates"]) != armor_plates:
                    raise RuntimeError("armor plate count was not preserved")
                if not (0.0 <= float(control_result["kill_probability"]) <= 1.0):
                    raise RuntimeError("invalid kill probability")

    m433 = WEAPON_BY_ID["m433"]
    if damage_at_distance(m433["damage_profile"], 30) != 20.0:
        raise RuntimeError("ordinary distance damage test failed")
    if automatic_body_damage_vs_armor(m433["damage_profile"], 30) != 21.0:
        raise RuntimeError("armor +10m / 0.84x damage test failed")
    print("SELF-TEST OK")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    elif st is None:
        print("Streamlit is not installed. Run: pip install streamlit numpy pandas")
    else:
        render_app()
