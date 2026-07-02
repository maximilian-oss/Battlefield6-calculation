# app.py
# Battlefield 6 practical STK / TTK Monte Carlo calculator
# Fixed model:
# - Pre-1.3.3.0 weapon data
# - Player recoil compensation 0%
# - 262,144 Monte Carlo engagements per weapon and selected condition
# - Practical STK includes missed rounds
# - If cohort hit rate for a shot is <= 20%, the interval before the next shot becomes 0.2 s
#
# Run:
#   pip install streamlit numpy pandas
#   streamlit run app.py

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st


# ============================================================
# Fixed model settings
# ============================================================

MONTE_CARLO_TRIALS = 262_144
RANDOM_SEED = 20_260_702
PLAYER_RECOIL_COMPENSATION = 0.0
HIT_RATE_REST_THRESHOLD = 0.20
REST_INTERVAL_S = 0.20
MAX_SHOTS = 240
TARGET_HEALTH = 100.0
HEAD_MULTIPLIER = 1.34
ARMOR_HP_PER_PLATE = 40.0
ARMOR_RANGE_PENALTY_M = 10.0
AIM_POINT_Y_M = 1.315
FRAME_DT = 1.0 / 60.0
DAMAGE_EPS = 1e-7
BUILD_ID = "BF6-MC262144-0PCT-R1"


# ============================================================
# Embedded weapon data — no external JSON/CSV required
# ============================================================

WEAPON_DATA = [{'id': 'm433',
  'class': 'Assault',
  'weapon': 'M433',
  'rpm': 830.769,
  'velocity_mps': 670.0,
  'mag_size': 30,
  'reload_s': 2.384,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.78,
  'recoil_mean_direction_deg': -22.0,
  'recoil_direction_variation_per_side_deg': 50.9,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'b36a4',
  'class': 'Assault',
  'weapon': 'B36A4',
  'rpm': 719.999,
  'velocity_mps': 780.0,
  'mag_size': 30,
  'reload_s': 2.384,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.7,
  'recoil_mean_direction_deg': -15.0,
  'recoil_direction_variation_per_side_deg': 37.4,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'sor556mk2',
  'class': 'Assault',
  'weapon': 'SOR-556 MK2',
  'rpm': 568.421,
  'velocity_mps': 800.0,
  'mag_size': 30,
  'reload_s': 2.384,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.62,
  'recoil_mean_direction_deg': -9.0,
  'recoil_direction_variation_per_side_deg': 17.3,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'ak4d',
  'class': 'Assault',
  'weapon': 'AK4D',
  'rpm': 514.285,
  'velocity_mps': 720.0,
  'mag_size': 20,
  'reload_s': 2.467,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 20.0}],
  'recoil_amount_deg': 0.85,
  'recoil_mean_direction_deg': -18.0,
  'recoil_direction_variation_per_side_deg': 25.4,
  'recoil_decay_factor': 104.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.459,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.392,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'tr7',
  'class': 'Assault',
  'weapon': 'TR-7',
  'rpm': 719.999,
  'velocity_mps': 648.0,
  'mag_size': 20,
  'reload_s': 2.4,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 20.0}],
  'recoil_amount_deg': 1.16,
  'recoil_mean_direction_deg': 20.0,
  'recoil_direction_variation_per_side_deg': 47.1,
  'recoil_decay_factor': 104.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.459,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.392,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'kord6p67',
  'class': 'Assault',
  'weapon': 'KORD 6P67',
  'rpm': 899.999,
  'velocity_mps': 760.0,
  'mag_size': 30,
  'reload_s': 2.45,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.55,
  'recoil_mean_direction_deg': 18.0,
  'recoil_direction_variation_per_side_deg': 35.3,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'nvo228e',
  'class': 'Assault',
  'weapon': 'NVO-228E',
  'rpm': 654.545,
  'velocity_mps': 671.0,
  'mag_size': 30,
  'reload_s': 2.5,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 27.25},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 21.4},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.75,
  'recoil_mean_direction_deg': -12.0,
  'recoil_direction_variation_per_side_deg': 36.8,
  'recoil_decay_factor': 76.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.24,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.307,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'l85a3',
  'class': 'Assault',
  'weapon': 'L85A3',
  'rpm': 635.294,
  'velocity_mps': 814.0,
  'mag_size': 30,
  'reload_s': 2.767,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.67,
  'recoil_mean_direction_deg': 12.0,
  'recoil_direction_variation_per_side_deg': 29.4,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'vcr2',
  'class': 'Assault',
  'weapon': 'VCR-2',
  'rpm': 899.999,
  'velocity_mps': 704.0,
  'mag_size': 30,
  'reload_s': 2.434,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.81,
  'recoil_mean_direction_deg': 18.0,
  'recoil_direction_variation_per_side_deg': 64.9,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm16a4',
  'class': 'Assault',
  'weapon': 'M16A4',
  'rpm': 771.0,
  'velocity_mps': 720.0,
  'mag_size': 30,
  'reload_s': 2.2,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.71,
  'recoil_mean_direction_deg': -21.0,
  'recoil_direction_variation_per_side_deg': 46.4,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 7.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm4a1',
  'class': 'Carbine',
  'weapon': 'M4A1',
  'rpm': 899.999,
  'velocity_mps': 630.0,
  'mag_size': 30,
  'reload_s': 2.2,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.86,
  'recoil_mean_direction_deg': -18.0,
  'recoil_direction_variation_per_side_deg': 37.9,
  'recoil_decay_factor': 57.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.045,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.228,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm277',
  'class': 'Carbine',
  'weapon': 'M277',
  'rpm': 719.999,
  'velocity_mps': 624.0,
  'mag_size': 20,
  'reload_s': 2.384,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 20.0}],
  'recoil_amount_deg': 0.96,
  'recoil_mean_direction_deg': -22.0,
  'recoil_direction_variation_per_side_deg': 39.4,
  'recoil_decay_factor': 76.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.24,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.307,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'ak205',
  'class': 'Carbine',
  'weapon': 'AK-205',
  'rpm': 719.999,
  'velocity_mps': 737.0,
  'mag_size': 30,
  'reload_s': 2.484,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 17.83333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 15.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.51,
  'recoil_mean_direction_deg': 6.0,
  'recoil_direction_variation_per_side_deg': 7.8,
  'recoil_decay_factor': 48.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 0.905,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.179,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm417a2',
  'class': 'Carbine',
  'weapon': 'M417 A2',
  'rpm': 654.545,
  'velocity_mps': 600.0,
  'mag_size': 20,
  'reload_s': 2.467,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 27.25},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 21.4},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.95,
  'recoil_mean_direction_deg': -16.0,
  'recoil_direction_variation_per_side_deg': 19.8,
  'recoil_decay_factor': 76.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.24,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.307,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'grtbc',
  'class': 'Carbine',
  'weapon': 'GRT-BC',
  'rpm': 830.769,
  'velocity_mps': 599.0,
  'mag_size': 30,
  'reload_s': 2.5,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.82,
  'recoil_mean_direction_deg': 16.0,
  'recoil_direction_variation_per_side_deg': 31.2,
  'recoil_decay_factor': 57.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.045,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.228,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'qbz192',
  'class': 'Carbine',
  'weapon': 'QBZ-192',
  'rpm': 771.428,
  'velocity_mps': 644.0,
  'mag_size': 30,
  'reload_s': 2.567,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.78,
  'recoil_mean_direction_deg': -10.0,
  'recoil_direction_variation_per_side_deg': 23.5,
  'recoil_decay_factor': 57.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.045,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.228,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'sg553r',
  'class': 'Carbine',
  'weapon': 'SG 553R',
  'rpm': 719.999,
  'velocity_mps': 519.0,
  'mag_size': 30,
  'reload_s': 2.5,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.82,
  'recoil_mean_direction_deg': -20.0,
  'recoil_direction_variation_per_side_deg': 43.3,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'sor300sc',
  'class': 'Carbine',
  'weapon': 'SOR-300SC',
  'rpm': 599.999,
  'velocity_mps': 563.0,
  'mag_size': 30,
  'reload_s': 2.25,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.76,
  'recoil_mean_direction_deg': -12.0,
  'recoil_direction_variation_per_side_deg': 19.2,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'sgx',
  'class': 'SMG',
  'weapon': 'SGX',
  'rpm': 830.769,
  'velocity_mps': 402.0,
  'mag_size': 30,
  'reload_s': 2.517,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.6,
  'recoil_mean_direction_deg': -18.0,
  'recoil_direction_variation_per_side_deg': 39.8,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'pw5a3',
  'class': 'SMG',
  'weapon': 'PW5A3',
  'rpm': 771.428,
  'velocity_mps': 432.0,
  'mag_size': 30,
  'reload_s': 2.517,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.57,
  'recoil_mean_direction_deg': -10.0,
  'recoil_direction_variation_per_side_deg': 33.2,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'pw7a2',
  'class': 'SMG',
  'weapon': 'PW7A2',
  'rpm': 947.368,
  'velocity_mps': 600.0,
  'mag_size': 30,
  'reload_s': 2.184,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 16.66666667},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 16.66666667},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 14.28571429},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.52,
  'recoil_mean_direction_deg': -10.0,
  'recoil_direction_variation_per_side_deg': 33.3,
  'recoil_decay_factor': 46.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 0.919,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.166,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'umg40',
  'class': 'SMG',
  'weapon': 'UMG-40',
  'rpm': 635.294,
  'velocity_mps': 488.0,
  'mag_size': 30,
  'reload_s': 2.517,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 21.4},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 17.83333333},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.61,
  'recoil_mean_direction_deg': -16.0,
  'recoil_direction_variation_per_side_deg': 17.4,
  'recoil_decay_factor': 57.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.045,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.228,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'usg90',
  'class': 'SMG',
  'weapon': 'USG-90',
  'rpm': 899.999,
  'velocity_mps': 570.0,
  'mag_size': 50,
  'reload_s': 3.0,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 17.83333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 15.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.56,
  'recoil_mean_direction_deg': 10.0,
  'recoil_direction_variation_per_side_deg': 42.8,
  'recoil_decay_factor': 48.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 0.905,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.179,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'kv9',
  'class': 'SMG',
  'weapon': 'KV9',
  'rpm': 1079.999,
  'velocity_mps': 348.0,
  'mag_size': 17,
  'reload_s': 2.384,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.54,
  'recoil_mean_direction_deg': 22.0,
  'recoil_direction_variation_per_side_deg': 57.6,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'scw10',
  'class': 'SMG',
  'weapon': 'SCW-10',
  'rpm': 799.999,
  'velocity_mps': 428.0,
  'mag_size': 15,
  'reload_s': 2.6,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.75,
  'recoil_mean_direction_deg': -18.0,
  'recoil_direction_variation_per_side_deg': 35.0,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'sl9',
  'class': 'SMG',
  'weapon': 'SL9',
  'rpm': 674.999,
  'velocity_mps': 510.0,
  'mag_size': 30,
  'reload_s': 2.65,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.53,
  'recoil_mean_direction_deg': 0.0,
  'recoil_direction_variation_per_side_deg': 16.2,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'cz3a1',
  'class': 'SMG',
  'weapon': 'CZ3A1',
  'rpm': 981.818,
  'velocity_mps': 360.0,
  'mag_size': 30,
  'reload_s': 2.217,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 14.28571429},
                     {'min_range': 75.0, 'max_range': None, 'damage': 12.5}],
  'recoil_amount_deg': 0.7,
  'recoil_mean_direction_deg': -15.0,
  'recoil_direction_variation_per_side_deg': 59.1,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 6.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'l110',
  'class': 'LMG',
  'weapon': 'L110',
  'rpm': 719.999,
  'velocity_mps': 780.0,
  'mag_size': 100,
  'reload_s': 6.5,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.56,
  'recoil_mean_direction_deg': 0.0,
  'recoil_direction_variation_per_side_deg': 39.4,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'drsiar',
  'class': 'LMG',
  'weapon': 'DRS-IAR',
  'rpm': 771.428,
  'velocity_mps': 720.0,
  'mag_size': 30,
  'reload_s': 2.467,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.7,
  'recoil_mean_direction_deg': -14.0,
  'recoil_direction_variation_per_side_deg': 35.2,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 9.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm60',
  'class': 'LMG',
  'weapon': 'M/60',
  'rpm': 514.285,
  'velocity_mps': 720.0,
  'mag_size': 100,
  'reload_s': 7.35,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 20.0}],
  'recoil_amount_deg': 0.73,
  'recoil_mean_direction_deg': 0.0,
  'recoil_direction_variation_per_side_deg': 38.8,
  'recoil_decay_factor': 104.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.459,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.392,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'rpkm',
  'class': 'LMG',
  'weapon': 'RPKM',
  'rpm': 553.846,
  'velocity_mps': 670.0,
  'mag_size': 40,
  'reload_s': 2.8,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 27.25},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 21.4},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.66,
  'recoil_mean_direction_deg': 5.0,
  'recoil_direction_variation_per_side_deg': 22.7,
  'recoil_decay_factor': 76.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.24,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 9.0,
  'spread_increase_per_shot_deg': 0.307,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm123k',
  'class': 'LMG',
  'weapon': 'M123K',
  'rpm': 830.769,
  'velocity_mps': 670.0,
  'mag_size': 100,
  'reload_s': 6.65,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.61,
  'recoil_mean_direction_deg': -10.0,
  'recoil_direction_variation_per_side_deg': 55.9,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm250',
  'class': 'LMG',
  'weapon': 'M250',
  'rpm': 674.999,
  'velocity_mps': 760.0,
  'mag_size': 50,
  'reload_s': 5.75,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 25.0}],
  'recoil_amount_deg': 0.73,
  'recoil_mean_direction_deg': -14.0,
  'recoil_direction_variation_per_side_deg': 39.7,
  'recoil_decay_factor': 76.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.24,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.307,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'kts100mk8',
  'class': 'LMG',
  'weapon': 'KTS100 MK8',
  'rpm': 514.285,
  'velocity_mps': 840.0,
  'mag_size': 60,
  'reload_s': 3.25,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 25.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 25.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 20.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 20.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 16.66666667}],
  'recoil_amount_deg': 0.52,
  'recoil_mean_direction_deg': 8.0,
  'recoil_direction_variation_per_side_deg': 10.9,
  'recoil_decay_factor': 72.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.2,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 9.0,
  'spread_increase_per_shot_deg': 0.27,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm240l',
  'class': 'LMG',
  'weapon': 'M240L',
  'rpm': 599.999,
  'velocity_mps': 630.0,
  'mag_size': 50,
  'reload_s': 4.25,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 20.0}],
  'recoil_amount_deg': 0.81,
  'recoil_mean_direction_deg': 5.0,
  'recoil_direction_variation_per_side_deg': 41.8,
  'recoil_decay_factor': 104.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.459,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.392,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'm121a2',
  'class': 'LMG',
  'weapon': 'M121 A2',
  'rpm': 654.545,
  'velocity_mps': 600.0,
  'mag_size': 50,
  'reload_s': 6.267,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 33.33333333},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 33.33333333},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 25.0},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 25.0},
                     {'min_range': 75.0, 'max_range': None, 'damage': 20.0}],
  'recoil_amount_deg': 0.8,
  'recoil_mean_direction_deg': -7.0,
  'recoil_direction_variation_per_side_deg': 39.5,
  'recoil_decay_factor': 104.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.459,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.392,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'},
 {'id': 'rpk74m',
  'class': 'LMG',
  'weapon': 'RPK-74M',
  'rpm': 685.0,
  'velocity_mps': 840.0,
  'mag_size': 45,
  'reload_s': 2.784,
  'damage_profile': [{'min_range': 0.0, 'max_range': 9.5, 'damage': 20.0},
                     {'min_range': 9.5, 'max_range': 21.5, 'damage': 20.0},
                     {'min_range': 21.5, 'max_range': 36.5, 'damage': 16.66666667},
                     {'min_range': 36.5, 'max_range': 75.0, 'damage': 16.66666667},
                     {'min_range': 75.0, 'max_range': None, 'damage': 14.28571429}],
  'recoil_amount_deg': 0.48,
  'recoil_mean_direction_deg': 6.0,
  'recoil_direction_variation_per_side_deg': 18.9,
  'recoil_decay_factor': 55.0,
  'recoil_decay_exponent': 1.0,
  'recoil_decay_time_exponent': 1.023,
  'recoil_decay_offset': 0.06,
  'ads_stand_min_deg': 0.05,
  'ads_stand_max_deg': 11.0,
  'spread_increase_per_shot_deg': 0.21,
  'spread_first_shot_multiplier': 1.0,
  'spread_firing_decrease_coefficient': 1.22,
  'spread_firing_decrease_exponent': 2.5,
  'spread_firing_decrease_offset': 1.84,
  'spread_not_firing_decrease_coefficient': 0.0,
  'spread_not_firing_decrease_exponent': 0.25,
  'spread_not_firing_decrease_offset': 7.2,
  'spread_radial_distribution_exponent': 0.67,
  'source_model_version': 'pre-1.3.3.0'}]
WEAPON_BY_ID = {weapon["id"]: weapon for weapon in WEAPON_DATA}


# ============================================================
# Target geometry
# ============================================================

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
    denominator = abx * abx + aby * aby
    t = ((x - ax) * abx + (y - ay) * aby) / max(denominator, 1e-12)
    t = np.clip(t, 0.0, 1.0)
    dx = x - (ax + t * abx)
    dy = y - (ay + t * aby)
    return dx * dx + dy * dy <= radius * radius


def target_hit_and_head(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return full-target hit mask and head mask for the provisional standing target."""
    head = ((x / 0.09) ** 2 + ((y - 1.635) / 0.115) ** 2) <= 1.0

    neck_chest_abdomen = (
        ((np.abs(x) <= 0.07) & (y >= 1.48) & (y < 1.52))
        | ((np.abs(x) <= 0.20) & (y >= 1.15) & (y < 1.48))
        | ((np.abs(x) <= 0.18) & (y >= 0.86) & (y < 1.15))
    )

    arms = (
        _capsule_mask(x, y, -0.20, 1.42, -0.28, 1.24, 0.050)
        | _capsule_mask(x, y, 0.20, 1.42, 0.28, 1.24, 0.050)
        | _capsule_mask(x, y, -0.28, 1.24, -0.07, 1.29, 0.045)
        | _capsule_mask(x, y, 0.28, 1.24, 0.07, 1.29, 0.045)
    )

    legs = (
        _capsule_mask(x, y, -0.095, 0.86, -0.095, 0.09, 0.075)
        | _capsule_mask(x, y, 0.095, 0.86, 0.095, 0.09, 0.075)
        | _capsule_mask(x, y, -0.095, 0.09, -0.13, 0.025, 0.070)
        | _capsule_mask(x, y, 0.095, 0.09, 0.13, 0.025, 0.070)
    )

    return head | neck_chest_abdomen | arms | legs, head


# ============================================================
# Damage and recovery helpers
# ============================================================

def _ceil_damage(value: float, decimals: int = 3) -> float:
    factor = 10**decimals
    return math.ceil(float(value) * factor - 1e-12) / factor


def _damage_at_distance(profile: list[dict[str, Any]], distance_m: float) -> float:
    distance_m = max(0.0, float(distance_m))
    for row in profile:
        upper = row["max_range"]
        if distance_m >= float(row["min_range"]) and (
            upper is None or distance_m < float(upper)
        ):
            return float(row["damage"])
    return float(profile[-1]["damage"])


def _recoil_decay_affine_coefficients(
    factor: float,
    exponent: float,
    time_exponent: float,
    duration_s: float,
    offset: float,
) -> tuple[float, float] | None:
    """
    For exponent == 1, collapse the 60 Hz decay loop into:
        new_magnitude = max(0, A * old_magnitude - B)
    This is mathematically equivalent to the frame-by-frame recurrence and is much faster.
    """
    if abs(exponent - 1.0) > 1e-12:
        return None

    a_total = 1.0
    b_total = 0.0
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(FRAME_DT, duration_s - elapsed)
        elapsed += step
        a = factor * step * (elapsed**time_exponent)
        a_total = (1.0 - a) * a_total
        b_total = (1.0 - a) * b_total + a * offset
    return a_total, b_total


def _recover_recoil_axis(
    values: np.ndarray,
    factor: float,
    exponent: float,
    time_exponent: float,
    duration_s: float,
    offset: float,
) -> np.ndarray:
    if duration_s <= 0.0:
        return values

    affine = _recoil_decay_affine_coefficients(
        factor, exponent, time_exponent, duration_s, offset
    )
    if affine is not None:
        a_total, b_total = affine
        return np.sign(values) * np.maximum(0.0, a_total * np.abs(values) - b_total)

    output = values
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(FRAME_DT, duration_s - elapsed)
        elapsed += step
        decay = (
            (np.abs(output) ** exponent + offset)
            * factor
            * step
            * (elapsed**time_exponent)
        )
        output = np.sign(output) * np.maximum(0.0, np.abs(output) - decay)
    return output


def _recover_spread(
    spread: float,
    baseline: float,
    maximum: float,
    duration_s: float,
    coefficient: float,
    exponent: float,
    offset: float,
) -> float:
    output = float(spread)
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        step = min(FRAME_DT, duration_s - elapsed)
        elapsed += step
        delta = max(output - baseline, 0.0)
        output -= step * (coefficient * delta**exponent + offset)
        output = min(maximum, max(baseline, output))
    return output


# ============================================================
# Monte Carlo engine
# ============================================================

@st.cache_data(show_spinner=False, max_entries=512)
def simulate_weapon(
    weapon_id: str,
    distance_m: int,
    armor_plates: int,
) -> dict[str, float | int | str]:
    """
    Run exactly 262,144 complete engagements for one weapon/condition.

    Cache key = weapon + distance + armor.
    Therefore a weapon is calculated only once for that condition during the app process.
    Selecting, sorting, or redisplaying the result does not rerun the Monte Carlo calculation.
    """
    weapon = WEAPON_BY_ID[weapon_id]
    n = MONTE_CARLO_TRIALS
    rng = np.random.default_rng(RANDOM_SEED)

    health = np.full(n, TARGET_HEALTH, dtype=np.float32)
    armor = np.full(n, float(armor_plates) * ARMOR_HP_PER_PLATE, dtype=np.float32)
    alive = np.ones(n, dtype=bool)

    recoil_x = np.zeros(n, dtype=np.float32)
    recoil_y = np.zeros(n, dtype=np.float32)
    kill_shot = np.zeros(n, dtype=np.int16)
    kill_time = np.full(n, np.nan, dtype=np.float32)
    hits_until_kill = np.zeros(n, dtype=np.int16)

    rpm = float(weapon["rpm"])
    normal_interval = 60.0 / rpm
    current_time = 0.0
    rounds_in_magazine = 0
    pause_count = 0

    spread_min = float(weapon["ads_stand_min_deg"])
    spread_max = float(weapon["ads_stand_max_deg"])
    spread = spread_min

    recoil_amount = np.float32(weapon["recoil_amount_deg"])
    recoil_mean = np.float32(weapon["recoil_mean_direction_deg"])
    recoil_variation = float(weapon["recoil_direction_variation_per_side_deg"])

    body_damage = _ceil_damage(
        _damage_at_distance(weapon["damage_profile"], float(distance_m))
    )
    armor_body_damage = _ceil_damage(
        _damage_at_distance(
            weapon["damage_profile"],
            float(distance_m) + ARMOR_RANGE_PENALTY_M,
        )
    )

    for shot_number in range(1, MAX_SHOTS + 1):
        # Spread is sampled around the current recoil-displaced aim direction.
        radial_u = rng.random(n, dtype=np.float32)
        azimuth = rng.random(n, dtype=np.float32) * np.float32(2.0 * math.pi)
        radius = np.float32(spread) * (
            radial_u ** np.float32(weapon["spread_radial_distribution_exponent"])
        )

        bullet_angle_x = recoil_x + radius * np.cos(azimuth)
        bullet_angle_y = recoil_y + radius * np.sin(azimuth)
        impact_x = np.float32(distance_m) * np.tan(np.deg2rad(bullet_angle_x))
        impact_y = np.float32(AIM_POINT_Y_M) + np.float32(distance_m) * np.tan(
            np.deg2rad(bullet_angle_y)
        )

        hit, head = target_hit_and_head(impact_x, impact_y)
        shot_hit_rate = float(hit.mean())

        # Only rounds fired before a trial's kill count toward practical STK and accuracy.
        active_hit = alive & hit
        hits_until_kill += active_hit

        damage = np.where(
            head,
            np.float32(body_damage * HEAD_MULTIPLIER),
            np.float32(body_damage),
        )

        if armor_plates > 0:
            armor_damage = np.where(
                head,
                np.float32(armor_body_damage * HEAD_MULTIPLIER),
                np.float32(armor_body_damage),
            )
            armor_damage = armor_damage * hit * alive
            absorbed = np.minimum(armor, armor_damage)
            armor -= absorbed
            health -= armor_damage - absorbed
        else:
            health -= damage * hit * alive

        newly_killed = alive & (health <= DAMAGE_EPS)
        kill_shot[newly_killed] = shot_number
        kill_time[newly_killed] = current_time
        alive[newly_killed] = False

        # The current shot's recoil affects the following shot.
        # Sym direction variation is the full per-side value: mean ± variation.
        recoil_direction = recoil_mean + rng.uniform(
            -recoil_variation,
            recoil_variation,
            size=n,
        ).astype(np.float32)
        direction_rad = np.deg2rad(recoil_direction)
        recoil_x += -recoil_amount * np.sin(direction_rad)
        recoil_y += recoil_amount * np.cos(direction_rad)

        # Player recoil compensation is deliberately fixed at 0%.
        spread_increase = float(weapon["spread_increase_per_shot_deg"])
        if shot_number == 1:
            spread_increase *= float(weapon["spread_first_shot_multiplier"])
        spread = min(spread_max, spread + spread_increase)

        rounds_in_magazine += 1
        pause_triggered = shot_hit_rate <= HIT_RATE_REST_THRESHOLD
        interval_to_next = max(normal_interval, REST_INTERVAL_S) if pause_triggered else normal_interval
        if pause_triggered:
            pause_count += 1

        # Reload takes precedence over the 0.2 s pause and resets recoil/spread.
        if rounds_in_magazine >= int(weapon["mag_size"]) and np.any(alive):
            interval_to_next = float(weapon["reload_s"])
            rounds_in_magazine = 0
            recoil_x.fill(0.0)
            recoil_y.fill(0.0)
            spread = spread_min
        else:
            recoil_x = _recover_recoil_axis(
                recoil_x,
                float(weapon["recoil_decay_factor"]),
                float(weapon["recoil_decay_exponent"]),
                float(weapon["recoil_decay_time_exponent"]),
                interval_to_next,
                float(weapon["recoil_decay_offset"]),
            )
            recoil_y = _recover_recoil_axis(
                recoil_y,
                float(weapon["recoil_decay_factor"]),
                float(weapon["recoil_decay_exponent"]),
                float(weapon["recoil_decay_time_exponent"]),
                interval_to_next,
                float(weapon["recoil_decay_offset"]),
            )

            firing_part = min(normal_interval, interval_to_next)
            spread = _recover_spread(
                spread,
                spread_min,
                spread_max,
                firing_part,
                float(weapon["spread_firing_decrease_coefficient"]),
                float(weapon["spread_firing_decrease_exponent"]),
                float(weapon["spread_firing_decrease_offset"]),
            )

            extra_pause = max(0.0, interval_to_next - firing_part)
            if extra_pause > 0.0:
                spread = _recover_spread(
                    spread,
                    spread_min,
                    spread_max,
                    extra_pause,
                    float(weapon["spread_not_firing_decrease_coefficient"]),
                    float(weapon["spread_not_firing_decrease_exponent"]),
                    float(weapon["spread_not_firing_decrease_offset"]),
                )

        if not np.any(alive):
            break
        current_time += interval_to_next

    killed = kill_shot > 0
    killed_count = int(killed.sum())
    kill_probability = killed_count / n

    if killed_count == 0:
        return {
            "class": weapon["class"],
            "weapon": weapon["weapon"],
            "rpm": rpm,
            "distance_m": int(distance_m),
            "armor_plates": int(armor_plates),
            "trials": n,
            "practical_stk": float("nan"),
            "mean_ttk_s": float("nan"),
            "median_ttk_s": float("nan"),
            "accuracy": float("nan"),
            "kill_probability": 0.0,
            "pause_count": pause_count,
        }

    killed_shots = kill_shot[killed].astype(np.float64)
    killed_times = kill_time[killed].astype(np.float64)
    total_shots = float(killed_shots.sum())
    total_hits = float(hits_until_kill[killed].sum())

    return {
        "class": weapon["class"],
        "weapon": weapon["weapon"],
        "rpm": rpm,
        "distance_m": int(distance_m),
        "armor_plates": int(armor_plates),
        "trials": n,
        "practical_stk": float(killed_shots.mean()),
        "median_stk": float(np.median(killed_shots)),
        "mean_ttk_s": float(killed_times.mean()),
        "median_ttk_s": float(np.median(killed_times)),
        "accuracy": total_hits / total_shots if total_shots > 0 else float("nan"),
        "kill_probability": kill_probability,
        "pause_count": pause_count,
    }


# ============================================================
# Streamlit UI — all 37 weapons are calculated together
# ============================================================

st.set_page_config(page_title="BF6 Practical STK / TTK", layout="wide")
st.title("Battlefield 6 실전 STK / TTK — MC 262,144")
st.code(f"BUILD: {BUILD_ID}", language=None)
st.caption(
    "1.3.3.0 이전 데이터 · 플레이어 반동 보정 0% · 총기당 262,144회 고정 몬테카를로 · 선택 조건당 37종 1회 계산 후 캐시"
)

control_a, control_b, control_c = st.columns([1.2, 1.0, 1.2])
with control_a:
    distance_m = st.number_input(
        "거리 (m)", min_value=1, max_value=150, value=30, step=1
    )
with control_b:
    armor_plates = st.radio("방탄 플레이트", [0, 1, 2], horizontal=True)
with control_c:
    calculate = st.button(
        "37종 전체 계산",
        type="primary",
        use_container_width=True,
    )

st.info(
    "실전 STK는 빗나간 탄을 포함해 처치까지 실제로 발사한 총탄 수입니다. "
    "각 발차의 262,144개 고정 코호트 명중률이 20% 이하이면 다음 발까지 총 간격을 0.2초로 늘립니다. "
    "같은 거리·방탄판 조건은 캐시에 저장되어 표를 다시 보거나 정렬할 때 재계산하지 않습니다."
)

condition_key = (int(distance_m), int(armor_plates))
if calculate:
    st.session_state["requested_condition"] = condition_key

if st.session_state.get("requested_condition") != condition_key:
    st.warning("거리 또는 방탄판 조건을 바꿨습니다. ‘37종 전체 계산’을 누르세요.")
    st.stop()

progress = st.progress(0.0, text="총기별 262,144회 계산 준비 중…")
status = st.empty()
rows: list[dict[str, Any]] = []

for index, weapon in enumerate(WEAPON_DATA, start=1):
    status.write(f"{index}/{len(WEAPON_DATA)} — {weapon['class']} | {weapon['weapon']}")
    rows.append(
        simulate_weapon(
            weapon_id=weapon["id"],
            distance_m=int(distance_m),
            armor_plates=int(armor_plates),
        )
    )
    progress.progress(index / len(WEAPON_DATA), text=f"{index}/{len(WEAPON_DATA)} 완료")

progress.empty()
status.empty()

results = pd.DataFrame(rows)
results = results.sort_values(
    ["mean_ttk_s", "practical_stk", "weapon"],
    ascending=[True, True, True],
).reset_index(drop=True)
results.insert(0, "rank", np.arange(1, len(results) + 1))

view = results.copy()
view["practical_stk"] = view["practical_stk"].round(3)
view["median_stk"] = view["median_stk"].round(0).astype("Int64")
view["mean_ttk_s"] = view["mean_ttk_s"].round(4)
view["median_ttk_s"] = view["median_ttk_s"].round(4)
view["accuracy"] = (view["accuracy"] * 100.0).round(2)
view["kill_probability"] = (view["kill_probability"] * 100.0).round(3)

view = view.rename(
    columns={
        "rank": "순위",
        "class": "종류",
        "weapon": "총기",
        "rpm": "RPM",
        "practical_stk": "실전 STK 평균",
        "median_stk": "실전 STK 중앙값",
        "mean_ttk_s": "TTK 평균 (초)",
        "median_ttk_s": "TTK 중앙값 (초)",
        "accuracy": "명중률 (%)",
        "kill_probability": "처치 성공률 (%)",
        "pause_count": "0.2초 휴식 발차 수",
        "trials": "시행 횟수",
    }
)

st.subheader(f"{int(distance_m)}m 결과 — 방탄판 {int(armor_plates)}장")
st.dataframe(
    view[
        [
            "순위",
            "종류",
            "총기",
            "RPM",
            "실전 STK 평균",
            "실전 STK 중앙값",
            "TTK 평균 (초)",
            "TTK 중앙값 (초)",
            "명중률 (%)",
            "처치 성공률 (%)",
            "0.2초 휴식 발차 수",
            "시행 횟수",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

csv_bytes = view.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "현재 결과 CSV 다운로드",
    data=csv_bytes,
    file_name=f"bf6_mc_{int(distance_m)}m_armor{int(armor_plates)}_262144.csv",
    mime="text/csv",
)

with st.expander("고정 계산 조건"):
    st.write(
        {
            "Monte Carlo per weapon": MONTE_CARLO_TRIALS,
            "Player recoil compensation": "0%",
            "Initial aim height": f"{AIM_POINT_Y_M} m (chest center)",
            "Rest trigger": "per-shot cohort hit rate <= 20%",
            "Rest interval": "0.2 s total shot-to-shot interval",
            "Target health": TARGET_HEALTH,
            "Head multiplier": HEAD_MULTIPLIER,
            "Damage model": "pre-1.3.3.0",
            "Bullet travel time": "not included",
        }
    )
