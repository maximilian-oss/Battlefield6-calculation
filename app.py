# app.py
# Battlefield 6 TTK 계산기 - 내장 데이터 + 개인 명중률 거리별 그래프 v27
# 실행:
#   pip install streamlit pandas plotly
#   py -m streamlit run app.py

import math
from typing import Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# =========================
# 기본 설정
# =========================

DEFAULT_HEALTH = 100
ARMOR_HP_PER_PLATE = 40
ARMOR_RANGE_PENALTY = 10.0

# DMR과 Sidearm은 방탄판이 있어도 거리 +10m 데미지 모델 후퇴를 적용하지 않는다.
# 단, 방탄판 HP 자체는 그대로 존재한다.
ARMOR_RANGE_PENALTY_EXEMPT_TYPES = {"dmr", "sidearm"}

# 배틀필드의 데미지 판정상 33.3333 * 3 = 99.9999 같은 값도 사망으로 처리되므로,
# 프로그램에서는 모든 데미지를 소수점 셋째 자리까지 올림 처리한다.
# 예: 33.33333333 -> 33.334
DAMAGE_CEIL_DECIMALS = 3

# 이 데이터는 업로드된 Battlefield 6 무기 데이터 엑셀의 Table 시트에서 추출한 값입니다.
# 포함: Type, Weapon, Rate of Fire, Firing Mode, Velocity, Mag Size, Reload, 거리별 Body Damage
# 거리 구간: 0-9.5m / 9.5-21.5m / 21.5-36.5m / 36.5-75m / 75m+
WEAPON_DATA = [
    {
        "type": "Assault",
        "weapon": "M433",
        "rpm": 830.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 670.0,
        "mag_size": 30.0,
        "reload": 2.384,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "B36A4",
        "rpm": 720.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 780.0,
        "mag_size": 30.0,
        "reload": 2.384,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "SOR-556 MK2",
        "rpm": 568.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 800.0,
        "mag_size": 30.0,
        "reload": 2.384,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "AK4D",
        "rpm": 514.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 720.0,
        "mag_size": 20.0,
        "reload": 2.467,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 33.33333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "TR-7",
        "rpm": 720.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 648.0,
        "mag_size": 20.0,
        "reload": 2.4,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 33.33333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "KORD 6P67",
        "rpm": 900.0,
        "firing_mode": "Auto",
        "burst_size": 2.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 760.0,
        "mag_size": 30.0,
        "reload": 2.45,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 20.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "NVO-228E",
        "rpm": 654.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 671.0,
        "mag_size": 30.0,
        "reload": 2.5,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 27.25
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 21.4
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "L85A3",
        "rpm": 635.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 814.0,
        "mag_size": 30.0,
        "reload": 2.767,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "VCR-2",
        "rpm": 900.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 704.0,
        "mag_size": 30.0,
        "reload": 2.434,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Assault",
        "weapon": "M16A4 *",
        "rpm": 771.0,
        "firing_mode": "Auto",
        "burst_size": 3.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 720.0,
        "mag_size": 30.0,
        "reload": 2.2,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "M4A1",
        "rpm": 900.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 630.0,
        "mag_size": 30.0,
        "reload": 2.2,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 21.4
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 17.83333333
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "M277",
        "rpm": 720.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 624.0,
        "mag_size": 20.0,
        "reload": 2.384,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "AK-205",
        "rpm": 720.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 737.0,
        "mag_size": 30.0,
        "reload": 2.484,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 20.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 17.83333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 15.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "M417 A2",
        "rpm": 654.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 600.0,
        "mag_size": 20.0,
        "reload": 2.467,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 27.25
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 21.4
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "GRT-BC",
        "rpm": 830.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 599.0,
        "mag_size": 30.0,
        "reload": 2.5,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 21.4
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 17.83333333
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "QBZ-192",
        "rpm": 771.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 644.0,
        "mag_size": 30.0,
        "reload": 2.567,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 21.4
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 17.83333333
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "SG 553R",
        "rpm": 720.0,
        "firing_mode": "Auto",
        "burst_size": 3.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 519.0,
        "mag_size": 30.0,
        "reload": 2.5,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "Carbine",
        "weapon": "SOR-300SC",
        "rpm": 600.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 563.0,
        "mag_size": 30.0,
        "reload": 2.25,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "SGX",
        "rpm": 830.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 402.0,
        "mag_size": 30.0,
        "reload": 2.517,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "PW5A3",
        "rpm": 771.0,
        "firing_mode": "Auto",
        "burst_size": 3.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 432.0,
        "mag_size": 30.0,
        "reload": 2.517,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "PW7A2",
        "rpm": 947.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 600.0,
        "mag_size": 30.0,
        "reload": 2.184,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 16.66666667
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 16.66666667
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 14.28571429
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "UMG-40",
        "rpm": 635.0,
        "firing_mode": "Auto",
        "burst_size": 2.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 488.0,
        "mag_size": 30.0,
        "reload": 2.517,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 21.4
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 17.83333333
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "USG-90",
        "rpm": 900.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 570.0,
        "mag_size": 50.0,
        "reload": 3.0,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 20.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 17.83333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 15.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "KV9",
        "rpm": 1080.0,
        "firing_mode": "Auto",
        "burst_size": 2.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 348.0,
        "mag_size": 17.0,
        "reload": 2.384,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "SCW-10",
        "rpm": 800.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 428.0,
        "mag_size": 15.0,
        "reload": 2.6,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "SL9",
        "rpm": 675.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 510.0,
        "mag_size": 30.0,
        "reload": 2.65,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "SMG",
        "weapon": "CZ3A1",
        "rpm": 981.0,
        "firing_mode": "Auto",
        "burst_size": 3.0,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 360.0,
        "mag_size": 30.0,
        "reload": 2.217,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "L110",
        "rpm": 720.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 780.0,
        "mag_size": 100.0,
        "reload": 6.5,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "DRS-IAR",
        "rpm": 771.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 720.0,
        "mag_size": 30.0,
        "reload": 2.467,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "M/60",
        "rpm": 514.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 720.0,
        "mag_size": 100.0,
        "reload": 7.35,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 33.33333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "RPKM",
        "rpm": 553.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 670.0,
        "mag_size": 40.0,
        "reload": 2.8,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 27.25
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 21.4
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "M123K",
        "rpm": 830.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 670.0,
        "mag_size": 100.0,
        "reload": 6.65,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "M250",
        "rpm": 675.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 760.0,
        "mag_size": 50.0,
        "reload": 5.75,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 25.0
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "KTS100 MK8",
        "rpm": 514.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 840.0,
        "mag_size": 60.0,
        "reload": 3.25,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 20.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 16.66666667
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "M240L",
        "rpm": 600.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 630.0,
        "mag_size": 50.0,
        "reload": 4.25,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 33.33333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "M121 A2",
        "rpm": 654.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 600.0,
        "mag_size": 50.0,
        "reload": 6.267,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 33.33333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 25.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "LMG",
        "weapon": "RPK-74M *",
        "rpm": 685.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Heavy",
        "velocity": 840.0,
        "mag_size": 45.0,
        "reload": 2.784,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 20.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "DMR",
        "weapon": "M39 EMR",
        "rpm": 257.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Extended",
        "velocity": 1000.0,
        "mag_size": 20.0,
        "reload": 2.534,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 40.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 40.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 37.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 37.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 33.33333333
            }
        ]
    },
    {
        "type": "DMR",
        "weapon": "LMR27",
        "rpm": 450.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Extended",
        "velocity": 1100.0,
        "mag_size": 10.0,
        "reload": 3.034,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 28.5
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 28.5
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 27.25
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 27.25
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 25.0
            }
        ]
    },
    {
        "type": "DMR",
        "weapon": "SVK-8.6",
        "rpm": 150.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Extended",
        "velocity": 900.0,
        "mag_size": 10.0,
        "reload": 2.967,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 66.66666667
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 60.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 50.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 50.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 50.0
            }
        ]
    },
    {
        "type": "DMR",
        "weapon": "SVDM",
        "rpm": 300.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Extended",
        "velocity": 1000.0,
        "mag_size": 10.0,
        "reload": 2.5,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 40.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 40.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 37.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 37.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 33.33333333
            }
        ]
    },
    {
        "type": "DMR",
        "weapon": "GRT-CPS",
        "rpm": 360.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Extended",
        "velocity": 1000.0,
        "mag_size": 20.0,
        "reload": 2.75,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 28.5
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 28.5
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 27.25
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 27.25
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 25.0
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "P18",
        "rpm": 400.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 350.0,
        "mag_size": 17.0,
        "reload": 1.934,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 20.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 16.66666667
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "ES 5.7",
        "rpm": 450.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 650.0,
        "mag_size": 20.0,
        "reload": 2.017,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 20.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 17.83333333
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 15.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "M45A1",
        "rpm": 327.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 336.0,
        "mag_size": 7.0,
        "reload": 1.867,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 33.33333333
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 25.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 20.0
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 14.28571429
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 12.5
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "M44",
        "rpm": 163.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 440.0,
        "mag_size": 6.0,
        "reload": 3.4,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 66.66666667
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 60.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 33.33333333
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 33.33333333
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 25.0
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "GGH-22",
        "rpm": 360.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 400.0,
        "mag_size": 15.0,
        "reload": 1.934,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 25.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 21.4
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 17.83333333
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 16.66666667
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 14.28571429
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "M357 TRAIT",
        "rpm": 225.0,
        "firing_mode": "Single",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 410.0,
        "mag_size": 8.0,
        "reload": 3.067,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 50.0
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 37.66666667
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 27.25
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 25.0
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 20.0
            }
        ]
    },
    {
        "type": "Sidearm",
        "weapon": "VZ. 61",
        "rpm": 818.0,
        "firing_mode": "Auto",
        "burst_size": None,
        "burst_delay": None,
        "barrel": "Basic",
        "velocity": 326.0,
        "mag_size": 10.0,
        "reload": 2.134,
        "damage_profile": [
            {
                "min_range": 0.0,
                "max_range": 9.5,
                "damage": 16.66666667
            },
            {
                "min_range": 9.5,
                "max_range": 21.5,
                "damage": 15.0
            },
            {
                "min_range": 21.5,
                "max_range": 36.5,
                "damage": 13.125
            },
            {
                "min_range": 36.5,
                "max_range": 75.0,
                "damage": 12.5
            },
            {
                "min_range": 75.0,
                "max_range": None,
                "damage": 11.22222222
            }
        ]
    }
]

# 원본 시트에서 RPM 또는 숫자형 거리별 데미지가 부족해서 제외된 항목입니다.
SKIPPED_WEAPONS = [
    "PP-19 *",
    "M2010 ESR",
    "SV-98",
    "PSR",
    "MINI SCOUT",
    "L115 *"
]


# =========================
# 계산 함수
# =========================

def ceil_damage(value: float, decimals: int = DAMAGE_CEIL_DECIMALS) -> float:
    """
    데미지를 지정한 소수 자리까지 올림 처리한다.

    이유:
    - 원본 데이터의 33.33333333 같은 값은 3발 합산 시 99.99999999가 될 수 있다.
    - 실제 게임에서는 이런 값도 100 데미지 사망 판정으로 취급되므로,
      계산상 STK가 1발 더 늘어나는 문제를 막기 위해 데미지 자체를 올림한다.
    """
    factor = 10 ** decimals
    return math.ceil(float(value) * factor - 1e-12) / factor


def get_damage_at_range(profile: List[Dict], distance: float) -> float:
    """거리별 데미지 프로필에서 현재 거리의 데미지를 반환한다."""
    if not profile:
        return 0.0

    for item in profile:
        min_range = float(item["min_range"])
        max_range = item["max_range"]
        max_range_value = math.inf if max_range is None else float(max_range)

        if min_range <= distance < max_range_value:
            return ceil_damage(item["damage"])

    return ceil_damage(profile[-1]["damage"])


def armor_range_penalty_applies(weapon_type: str) -> bool:
    """
    방탄판이 남아 있을 때 거리 +10m 데미지 모델 후퇴를 적용할지 결정한다.

    현재 규칙:
    - DMR, Sidearm: 적용하지 않음
    - 그 외: 적용
    """
    return str(weapon_type).strip().lower() not in ARMOR_RANGE_PENALTY_EXEMPT_TYPES


def effective_distance_against_armor(
    weapon_type: str,
    distance: float,
    armor_range_penalty: float = ARMOR_RANGE_PENALTY,
) -> float:
    """방탄판이 남아 있을 때 해당 탄환에 적용할 거리."""
    if armor_range_penalty_applies(weapon_type):
        return distance + armor_range_penalty
    return distance


def calculate_ttk(
    profile: List[Dict],
    rpm: float,
    distance: float,
    armor_plates: int,
    weapon_type: str = "",
    base_health: float = DEFAULT_HEALTH,
    armor_hp_per_plate: float = ARMOR_HP_PER_PLATE,
    armor_range_penalty: float = ARMOR_RANGE_PENALTY,
    max_shots: int = 200,
) -> Dict:
    """
    한 발씩 순차 계산한다.

    규칙:
    - 방탄판 0장: HP 100, 실제 거리 기준 데미지
    - 방탄판 1장: Armor 40 + HP 100
    - 방탄판 2장: Armor 80 + HP 100
    - 방탄판이 1이라도 남아 있으면 해당 탄환은 거리 +10m 데미지 적용
    - 단, DMR과 Sidearm은 방탄판이 있어도 거리 +10m 후퇴를 적용하지 않음
    - 방탄판 초과 피해는 HP로 넘어간다.
    """
    health = float(base_health)
    armor_hp = float(armor_plates * armor_hp_per_plate)
    shot_count = 0

    while health > 0 and shot_count < max_shots:
        shot_count += 1

        if armor_hp > 0:
            effective_distance = effective_distance_against_armor(
                weapon_type=weapon_type,
                distance=distance,
                armor_range_penalty=armor_range_penalty,
            )
        else:
            effective_distance = distance

        damage = get_damage_at_range(profile, effective_distance)

        if armor_hp > 0:
            if damage <= armor_hp:
                armor_hp -= damage
            else:
                overflow = damage - armor_hp
                armor_hp = 0.0
                health -= overflow
        else:
            health -= damage

    ttk = None if rpm <= 0 else (shot_count - 1) * (60.0 / rpm)

    return {
        "shots_to_kill": shot_count,
        "ttk": ttk,
        "final_health": max(health, 0),
        "final_armor": max(armor_hp, 0),
    }


def calculate_accuracy_stats(
    shots_to_kill: int,
    rpm: float,
    accuracy_percent: float,
) -> Dict:
    """
    개인 명중률을 반영한 평균 처치 시간과 표준편차를 계산한다.

    모델:
    - 필요한 명중탄 수 k = 기존 STK
    - 각 탄환은 독립적으로 p 확률로 명중
    - 총 N발을 쏴서 k번째 명중이 발생하는 순간 처치
    - N은 음이항분포를 따른다.
    - 재장전 시간은 반영하지 않는다.

    공식:
    - E[N] = k / p
    - Var(N) = k(1-p) / p^2
    - Time = (N - 1) * shot_interval
    """
    k = int(shots_to_kill)
    p = float(accuracy_percent) / 100.0

    if k <= 0 or rpm <= 0 or p <= 0:
        return {
            "mean_time_sec": None,
            "sigma_time_sec": None,
            "expected_shots": None,
            "coverage": 0.0,
        }

    shot_interval = 60.0 / float(rpm)

    expected_shots = k / p
    variance_shots = k * (1.0 - p) / (p ** 2)

    mean_time = (expected_shots - 1.0) * shot_interval
    sigma_time = math.sqrt(max(0.0, variance_shots)) * shot_interval

    return {
        "mean_time_sec": mean_time,
        "sigma_time_sec": sigma_time,
        "expected_shots": expected_shots,
        "coverage": 1.0,
    }

def negative_binomial_distribution(
    shots_to_kill: int,
    rpm: float,
    accuracy_percent: float,
    cdf_cutoff: float = 0.999,
    max_shots_cap: int = 2500,
) -> pd.DataFrame:
    """
    개인 명중률 기반 처치 시간의 실제 확률분포를 만든다.

    N = k번째 명중이 발생하는 총 발사탄 수
    P(N=n) = C(n-1, k-1) * p^k * (1-p)^(n-k)

    반환값:
    - fired_shots: 총 발사탄 수 N
    - kill_time_sec: (N-1) * 발사간격
    - probability: 해당 발사탄 수에서 처치될 확률
    - cumulative_probability: 그 시간까지 처치될 누적확률
    """
    k = int(shots_to_kill)
    p = float(accuracy_percent) / 100.0

    if k <= 0 or rpm <= 0 or p <= 0:
        return pd.DataFrame()

    p = min(max(p, 1e-9), 1.0)
    q = 1.0 - p
    shot_interval = 60.0 / float(rpm)

    if p >= 1.0:
        return pd.DataFrame([{
            "fired_shots": k,
            "kill_time_sec": (k - 1) * shot_interval,
            "probability": 1.0,
            "cumulative_probability": 1.0,
        }])

    expected_shots = k / p
    variance_shots = k * q / (p ** 2)
    sigma_shots = math.sqrt(max(0.0, variance_shots))

    # 평균 + 10σ 정도까지 보되, 너무 긴 꼬리 때문에 화면/연산이 과도해지는 것은 막는다.
    dynamic_cap = int(math.ceil(expected_shots + 10.0 * sigma_shots + 20))
    max_shots = max(k, min(max(dynamic_cap, 80), max_shots_cap))

    rows = []
    n = k
    probability = p ** k
    cumulative = 0.0

    while n <= max_shots:
        cumulative += probability
        rows.append({
            "fired_shots": n,
            "kill_time_sec": (n - 1) * shot_interval,
            "probability": probability,
            "cumulative_probability": min(cumulative, 1.0),
        })

        if cumulative >= cdf_cutoff:
            break

        # P(N=n+1) = P(N=n) * n/(n+1-k) * (1-p)
        next_denominator = n + 1 - k
        if next_denominator <= 0:
            break

        probability = probability * (n / next_denominator) * q
        n += 1

        if probability <= 0 and cumulative > 0:
            break

    return pd.DataFrame(rows)


def distribution_quantile(distribution_df: pd.DataFrame, probability: float):
    """
    누적확률이 probability 이상이 되는 최초 처치 시간을 반환한다.
    """
    if distribution_df.empty:
        return None

    matched = distribution_df[distribution_df["cumulative_probability"] >= probability]
    if matched.empty:
        return None

    return float(matched.iloc[0]["kill_time_sec"])


def default_accuracy_for_weapon(weapon: Dict) -> float:
    """
    무기 타입별 기본 개인 명중률.
    - Assault, Carbine: 25%
    - SMG, LMG: 20%
    - DMR, Sidearm: 33%
    - 그 외: 25%
    """
    type_name = str(weapon.get("type", "")).strip().lower()
    if type_name in ["assault", "carbine"]:
        return 25.0
    if type_name in ["smg", "lmg"]:
        return 20.0
    if type_name in ["dmr", "sidearm"]:
        return 33.0
    return 25.0

def weapon_result_row(weapon: Dict, distance: float, armor_plates: int) -> Dict:
    profile = weapon["damage_profile"]
    rpm = float(weapon["rpm"])
    result = calculate_ttk(
        profile=profile,
        rpm=rpm,
        distance=distance,
        armor_plates=armor_plates,
        weapon_type=weapon.get("type", ""),
    )

    actual_damage = get_damage_at_range(profile, distance)
    armor_damage = get_damage_at_range(
        profile,
        effective_distance_against_armor(
            weapon_type=weapon.get("type", ""),
            distance=distance,
        ),
    )

    return {
        "type": weapon["type"],
        "weapon": weapon["weapon"],
        "rpm": rpm,
        "firing_mode": weapon.get("firing_mode", ""),
        "mag_size": weapon.get("mag_size"),
        "reload": weapon.get("reload"),
        "velocity": weapon.get("velocity"),
        "distance": distance,
        "armor_plates": armor_plates,
        "normal_damage_at_distance": actual_damage,
        "armor_damage_at_distance_plus_10m": armor_damage,
        "shots_to_kill": result["shots_to_kill"],
        "ttk_sec": result["ttk"],
    }


def sweep_weapon(weapon: Dict, armor_plates: int, max_distance: int = 100) -> pd.DataFrame:
    rows = []
    for distance in range(0, max_distance + 1):
        rows.append(
            weapon_result_row(
                weapon=weapon,
                distance=float(distance),
                armor_plates=armor_plates,
            )
        )
    return pd.DataFrame(rows)


def damage_profile_to_text(profile: List[Dict]) -> str:
    parts = []
    for item in profile:
        min_range = item["min_range"]
        max_range = item["max_range"]
        damage = item["damage"]
        if max_range is None:
            label = f"{min_range:g}m+"
        else:
            label = f"{min_range:g}-{max_range:g}m"
        parts.append(f"{label}: {damage:g}")
    return " / ".join(parts)


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Plotly 기본 색상(hex)을 투명도 있는 rgba 문자열로 변환한다."""
    color = str(hex_color).strip()
    if color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    if color.startswith("rgb("):
        return color.replace("rgb(", "rgba(").replace(")", f", {alpha})")
    return f"rgba(80, 80, 80, {alpha})"


def _hex_to_rgb_tuple(hex_color: str):
    color = str(hex_color).strip().lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _rgb_tuple_to_hex(rgb_tuple) -> str:
    r, g, b = rgb_tuple
    return f"#{int(round(r)):02x}{int(round(g)):02x}{int(round(b)):02x}"


def _interpolate_color(hex_a: str, hex_b: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb_tuple(hex_a)
    br, bg, bb = _hex_to_rgb_tuple(hex_b)
    return _rgb_tuple_to_hex((
        ar + (br - ar) * t,
        ag + (bg - ag) * t,
        ab + (bb - ab) * t,
    ))


def ranked_rainbow_colors(count: int) -> List[str]:
    """표준편차 순위에 맞춰 높은 값부터 낮은 값까지 사용할 색상표를 만든다."""
    if count <= 0:
        return []
    if count == 1:
        return ["#ff0000"]
    if count == 2:
        return ["#ff0000", "#0000ff"]
    if count == 3:
        return ["#ff0000", "#00aa00", "#0000ff"]
    if count == 4:
        return ["#ff0000", "#ffff00", "#00aa00", "#0000ff"]

    stops = [
        "#ff0000",  # red
        "#ff7f00",  # orange
        "#ffff00",  # yellow
        "#00aa00",  # green
        "#0066ff",  # blue
        "#4b0082",  # indigo
        "#8a2be2",  # violet
    ]
    if count == len(stops):
        return stops

    result = []
    max_pos = len(stops) - 1
    for idx in range(count):
        pos = idx * max_pos / (count - 1)
        left = int(math.floor(pos))
        right = int(math.ceil(pos))
        if left == right:
            result.append(stops[left])
        else:
            result.append(_interpolate_color(stops[left], stops[right], pos - left))
    return result


def color_map_by_sigma(accuracy_df: pd.DataFrame, selected_weapon_order: List[str]) -> Dict[str, str]:
    """σ가 큰 총기일수록 빨간색, 작은 총기일수록 보라색/파란색에 가깝게 배정한다."""
    if accuracy_df.empty:
        return {}

    order_index = {weapon_name: idx for idx, weapon_name in enumerate(selected_weapon_order)}
    ranking_df = accuracy_df[["weapon", "sigma_sec"]].copy()
    ranking_df["_order"] = ranking_df["weapon"].map(order_index).fillna(999999)
    ranking_df = ranking_df.sort_values(["sigma_sec", "_order"], ascending=[False, True])

    colors = ranked_rainbow_colors(len(ranking_df))
    return {weapon_name: colors[idx] for idx, weapon_name in enumerate(ranking_df["weapon"].tolist())}


def line_dash_map_for_weapons(selected_weapon_order: List[str]) -> Dict[str, str]:
    """
    음이항분포 곡선이 완전히 겹칠 때도 구분되도록 총기마다 다른 선 모양을 부여한다.
    Plotly line.dash는 기본 문자열과 CSS식 px 배열을 모두 지원한다.
    """
    if not selected_weapon_order:
        return {}

    # 1개만 볼 때는 가독성을 위해 실선.
    if len(selected_weapon_order) == 1:
        return {selected_weapon_order[0]: "solid"}

    dash_patterns = [
        "dash",                       # 긴 점선
        "dot",                        # 점선
        "longdash",                   # 더 긴 점선
        "dashdot",                    # 점-선 혼합
        "longdashdot",                # 긴 점-선 혼합
        "1px,5px",                    # 촘촘한 점선
        "3px,3px,10px,3px",           # 짧은 선 + 긴 선
        "10px,2px,2px,2px",           # 긴 선 + 짧은 점
        "2px,2px,2px,6px",            # 2중 점선
        "12px,4px,4px,4px,4px,4px",   # 긴 선 + 2중 짧은 선
        "6px,2px,1px,2px,1px,2px",    # 선 + 2중 점
        "14px,3px,2px,3px",           # 매우 긴 선 + 점
    ]

    return {
        weapon_name: dash_patterns[idx % len(dash_patterns)]
        for idx, weapon_name in enumerate(selected_weapon_order)
    }


# =========================
# 반동 기반 1:1 승률 비교 모델
# =========================

DUEL_ELIGIBLE_TYPES = {"Assault", "Carbine", "SMG", "LMG", "Sidearm"}

DUEL_BASE_ACCURACY_UNTIL_15M = 0.25
DUEL_TARGET_WIDTH_M = 0.45
DUEL_TARGET_HEIGHT_M = 0.80
DUEL_RECOIL_RECOVERY_TAU = 0.17
DUEL_BASE_AIM_SIGMA_DEG = 0.20
DUEL_VERTICAL_RECOIL_SCALE = 0.38
DUEL_HORIZONTAL_RECOIL_SCALE = 0.90

# vertical은 1발당 수직 반동 계열, direction_var는 반동 방향 변화/수평 불안정성 계열로 쓰는 값이다.
# 값이 없는 총기는 타입별 기본값을 사용한다. 추후 정확한 Sym.gg 수치를 확인하면 여기만 교체하면 된다.
DUEL_RECOIL_BY_TYPE = {
    "Assault": {"vertical": 0.78, "direction_var": 40.0},
    "Carbine": {"vertical": 0.82, "direction_var": 38.0},
    "SMG": {"vertical": 0.70, "direction_var": 45.0},
    "LMG": {"vertical": 0.90, "direction_var": 36.0},
    "Sidearm": {"vertical": 0.95, "direction_var": 34.0},
}

DUEL_RECOIL_DATA = {
    # Assault
    "M433": {"vertical": 0.78, "direction_var": 48.4},
    "B36A4": {"vertical": 0.67, "direction_var": 40.0},
    "SOR-556 MK2": {"vertical": 0.58, "direction_var": 25.0},
    "AK4D": {"vertical": 0.68, "direction_var": 28.0},
    "TR-7": {"vertical": 1.04, "direction_var": 45.2},
    "KORD 6P67": {"vertical": 0.92, "direction_var": 46.0},
    "NVO-228E": {"vertical": 0.95, "direction_var": 44.0},
    "L85A3": {"vertical": 0.63, "direction_var": 31.6},
    "VCR-2": {"vertical": 0.88, "direction_var": 45.0},
    "M16A4 *": {"vertical": 0.70, "direction_var": 30.0},

    # Carbine
    "M4A1": {"vertical": 0.88, "direction_var": 42.0},
    "M277": {"vertical": 0.96, "direction_var": 38.7},
    "AK-205": {"vertical": 0.58, "direction_var": 26.0},
    "M417 A2": {"vertical": 0.60, "direction_var": 26.0},
    "GRT-BC": {"vertical": 0.72, "direction_var": 34.0},
    "QBZ-192": {"vertical": 0.56, "direction_var": 24.0},
    "SG 553R": {"vertical": 0.95, "direction_var": 43.0},
    "SOR-300SC": {"vertical": 0.90, "direction_var": 40.0},

    # SMG
    "SGX": {"vertical": 0.68, "direction_var": 44.0},
    "PW5A3": {"vertical": 0.62, "direction_var": 40.0},
    "PW7A2": {"vertical": 0.70, "direction_var": 46.0},
    "UMG-40": {"vertical": 0.58, "direction_var": 36.0},
    "USG-90": {"vertical": 0.64, "direction_var": 39.0},
    "KV9": {"vertical": 0.76, "direction_var": 48.0},
    "SCW-10": {"vertical": 0.72, "direction_var": 45.0},
    "SL9": {"vertical": 0.55, "direction_var": 34.0},
    "CZ3A1": {"vertical": 0.82, "direction_var": 50.0},

    # LMG
    "L110": {"vertical": 0.82, "direction_var": 35.0},
    "DRS-IAR": {"vertical": 0.76, "direction_var": 34.0},
    "M/60": {"vertical": 0.95, "direction_var": 34.0},
    "RPKM": {"vertical": 0.85, "direction_var": 32.0},
    "M123K": {"vertical": 0.88, "direction_var": 36.0},
    "M250": {"vertical": 0.90, "direction_var": 38.0},
    "KTS100 MK8": {"vertical": 0.84, "direction_var": 33.0},
    "M240L": {"vertical": 1.02, "direction_var": 37.0},
    "M121 A2": {"vertical": 0.86, "direction_var": 35.0},
    "RPK-74M *": {"vertical": 0.74, "direction_var": 30.0},

    # Sidearm
    "P18": {"vertical": 0.82, "direction_var": 32.0},
    "ES 5.7": {"vertical": 0.58, "direction_var": 24.0},
    "M45A1": {"vertical": 0.72, "direction_var": 28.0},
    "M44": {"vertical": 1.15, "direction_var": 28.0},
    "GGH-22": {"vertical": 0.64, "direction_var": 24.0},
    "M357 TRAIT": {"vertical": 1.05, "direction_var": 30.0},
    "VZ. 61": {"vertical": 0.78, "direction_var": 42.0},
}


def duel_recoil_for_weapon(weapon: Dict) -> Dict[str, float]:
    """1:1 비교용 반동 데이터를 반환한다. 없으면 타입별 기본값을 쓴다."""
    weapon_name = str(weapon.get("weapon", ""))
    weapon_type = str(weapon.get("type", ""))
    if weapon_name in DUEL_RECOIL_DATA:
        return DUEL_RECOIL_DATA[weapon_name]
    return DUEL_RECOIL_BY_TYPE.get(weapon_type, {"vertical": 0.80, "direction_var": 40.0})


def duel_burst_len_for_distance(distance: float) -> int:
    """거리별 반동 리셋 단위. 15m 이하는 명중률 고정이라 실질적으로 영향이 없다."""
    if distance <= 15:
        return 999999
    if distance <= 40:
        return 10
    return 8


def duel_target_half_angles(distance: float) -> tuple[float, float]:
    """표적이 차지하는 좌우/상하 반각을 라디안으로 반환한다."""
    d = max(float(distance), 0.1)
    theta_x = math.atan((DUEL_TARGET_WIDTH_M / 2.0) / d)
    theta_y = math.atan((DUEL_TARGET_HEIGHT_M / 2.0) / d)
    return theta_x, theta_y


def duel_recoil_sigma_radians(weapon: Dict, shot_in_pattern: int) -> tuple[float, float]:
    """해당 탄 번호에서 좌우/상하 조준 오차 표준편차를 라디안으로 추정한다."""
    recoil = duel_recoil_for_weapon(weapon)
    rpm = max(float(weapon.get("rpm", 600.0)), 1.0)
    shot_interval = 60.0 / rpm
    rho = math.exp(-shot_interval / DUEL_RECOIL_RECOVERY_TAU)

    n = max(int(shot_in_pattern), 1)
    if n <= 1:
        accumulated = 0.0
    else:
        denominator = max(1e-9, 1.0 - rho ** 2)
        accumulated = (1.0 - rho ** (2 * (n - 1))) / denominator

    vertical = float(recoil.get("vertical", 0.8))
    direction_var = float(recoil.get("direction_var", 40.0))
    horizontal_component = vertical * math.sin(math.radians(max(direction_var, 0.0) / 2.0))

    base_sigma = math.radians(DUEL_BASE_AIM_SIGMA_DEG)
    sigma_x = math.sqrt(
        base_sigma ** 2
        + (math.radians(horizontal_component * DUEL_HORIZONTAL_RECOIL_SCALE) ** 2) * accumulated
    )
    sigma_y = math.sqrt(
        base_sigma ** 2
        + (math.radians(vertical * DUEL_VERTICAL_RECOIL_SCALE) ** 2) * accumulated
    )

    return max(sigma_x, 1e-9), max(sigma_y, 1e-9)


def duel_geometry_hit_probability_raw(weapon: Dict, distance: float, shot_in_pattern: int) -> float:
    """
    표적 허용각과 n번째 탄의 반동 오차를 비교해 원시 명중 확률 G(n,d)를 계산한다.
    이 값 자체는 실제 개인 명중률이 아니라, 15m 대비 감쇠율을 만들기 위한 기하학 값이다.
    """
    theta_x, theta_y = duel_target_half_angles(distance)
    sigma_x, sigma_y = duel_recoil_sigma_radians(weapon, shot_in_pattern)

    px = math.erf(theta_x / (math.sqrt(2.0) * sigma_x))
    py = math.erf(theta_y / (math.sqrt(2.0) * sigma_y))
    return max(1e-9, min(1.0, px * py))


def duel_hit_probability_for_shot(weapon: Dict, distance: float, fired_shot_number: int) -> float:
    """
    15m까지는 모든 총기 25% 명중률로 고정한다.
    15m 이후에는 G(n,d) / G(n,15m) 비율만큼 명중률을 감쇠시킨다.
    """
    if distance <= 15:
        return DUEL_BASE_ACCURACY_UNTIL_15M

    burst_len = duel_burst_len_for_distance(distance)
    shot_in_pattern = ((int(fired_shot_number) - 1) % burst_len) + 1

    g_distance = duel_geometry_hit_probability_raw(weapon, distance, shot_in_pattern)
    g_15m = duel_geometry_hit_probability_raw(weapon, 15.0, shot_in_pattern)
    decay = min(1.0, max(0.0, g_distance / max(g_15m, 1e-9)))

    return max(0.001, min(DUEL_BASE_ACCURACY_UNTIL_15M, DUEL_BASE_ACCURACY_UNTIL_15M * decay))


def duel_variable_accuracy_distribution(
    weapon: Dict,
    distance: float,
    armor_plates: int,
    cdf_cutoff: float = 0.999,
    max_shots: int = 500,
) -> pd.DataFrame:
    """
    탄마다 명중률이 달라지는 경우의 킬 시간 분포.
    상태 DP:
    - 아직 처치 전인 상태에서 현재까지 h발 명중했을 확률
    - 다음 탄 p_n으로 명중/빗나감 분기
    """
    base_row = weapon_result_row(
        weapon=weapon,
        distance=float(distance),
        armor_plates=int(armor_plates),
    )
    stk = int(base_row["shots_to_kill"])
    rpm = max(float(base_row["rpm"]), 1.0)
    interval = 60.0 / rpm

    state = [0.0] * stk
    state[0] = 1.0
    rows = []
    cumulative = 0.0

    for shot in range(1, max_shots + 1):
        p = duel_hit_probability_for_shot(weapon, distance, shot)
        next_state = [0.0] * stk
        kill_probability = 0.0

        for hits, probability in enumerate(state):
            if probability <= 0:
                continue

            # miss
            next_state[hits] += probability * (1.0 - p)

            # hit
            if hits + 1 >= stk:
                kill_probability += probability * p
            else:
                next_state[hits + 1] += probability * p

        if kill_probability > 0:
            cumulative += kill_probability
            rows.append({
                "weapon": weapon.get("weapon", ""),
                "fired_shots": shot,
                "kill_time_sec": (shot - 1) * interval,
                "probability": kill_probability,
                "cumulative_probability": min(cumulative, 1.0),
                "shot_hit_probability": p,
                "stk": stk,
                "rpm": rpm,
            })

        state = next_state

        if cumulative >= cdf_cutoff:
            break

        if sum(state) < 1e-9:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    total = float(df["probability"].sum())
    if total > 0:
        df["probability"] = df["probability"] / total
        df["cumulative_probability"] = df["probability"].cumsum().clip(upper=1.0)
        df["probability_percent"] = df["probability"] * 100.0
        df["cumulative_percent"] = df["cumulative_probability"] * 100.0

    return df


def duel_distribution_mean_sigma(df: pd.DataFrame) -> tuple[float | None, float | None]:
    if df.empty:
        return None, None
    times = df["kill_time_sec"].astype(float)
    probs = df["probability"].astype(float)
    mean = float((times * probs).sum())
    variance = float(((times - mean) ** 2 * probs).sum())
    return mean, math.sqrt(max(0.0, variance))


def duel_distribution_quantile(df: pd.DataFrame, q: float) -> float | None:
    if df.empty:
        return None
    hit = df[df["cumulative_probability"] >= q]
    if hit.empty:
        return None
    return float(hit.iloc[0]["kill_time_sec"])


def duel_win_probability(df_a: pd.DataFrame, df_b: pd.DataFrame) -> tuple[float, float, float]:
    """
    A/B 킬 시간 분포로 A 승률, B 승률, 동시킬 확률을 계산한다.
    같은 시간은 0.5승으로 처리할 수 있도록 tie를 별도 반환한다.
    """
    if df_a.empty or df_b.empty:
        return 0.0, 0.0, 0.0

    a_times = df_a["kill_time_sec"].to_numpy(dtype=float)
    a_probs = df_a["probability"].to_numpy(dtype=float)
    b_times = df_b["kill_time_sec"].to_numpy(dtype=float)
    b_probs = df_b["probability"].to_numpy(dtype=float)

    eps = 1e-9
    a_win_raw = 0.0
    tie = 0.0

    for t, p_a in zip(a_times, a_probs):
        b_after = b_probs[b_times > t + eps].sum()
        b_equal = b_probs[abs(b_times - t) <= eps].sum()
        a_win_raw += p_a * b_after
        tie += p_a * b_equal

    b_win_raw = max(0.0, 1.0 - a_win_raw - tie)
    a_score = a_win_raw + 0.5 * tie
    b_score = b_win_raw + 0.5 * tie

    return float(a_score), float(b_score), float(tie)


def duel_distance_sweep_win_probability(
    weapon_a: Dict,
    weapon_b: Dict,
    armor_plates: int,
    min_distance: int = 15,
    max_distance: int = 100,
    step: int = 1,
) -> pd.DataFrame:
    """
    15m부터 최대 거리까지 모든 거리에서 A/B 승률을 계산한다.
    슬라이더 값과 무관하게 같은 두 총기/방탄판 조건에서는 동일한 곡선이 나오고,
    화면에서는 현재 선택 거리만 수직선으로 표시한다.
    """
    rows = []

    for distance_value in range(int(min_distance), int(max_distance) + 1, int(step)):
        df_a = duel_variable_accuracy_distribution(
            weapon_a,
            distance=float(distance_value),
            armor_plates=int(armor_plates),
        )
        df_b = duel_variable_accuracy_distribution(
            weapon_b,
            distance=float(distance_value),
            armor_plates=int(armor_plates),
        )

        a_win, b_win, tie_probability = duel_win_probability(df_a, df_b)

        rows.append({
            "distance": distance_value,
            "a_weapon": weapon_a.get("weapon", ""),
            "b_weapon": weapon_b.get("weapon", ""),
            "a_win_percent": a_win * 100.0,
            "b_win_percent": b_win * 100.0,
            "tie_percent": tie_probability * 100.0,
            "winner": weapon_a.get("weapon", "") if a_win >= b_win else weapon_b.get("weapon", ""),
        })

    return pd.DataFrame(rows)


# =========================
# Streamlit UI
# =========================

st.set_page_config(
    page_title="Battlefield 6 TTK Calculator",
    layout="wide",
)

st.title("Battlefield 6 총기 TTK 계산기")
st.caption("엑셀 업로드 없이 내장된 총기 데이터로 TTK와 개인 명중률 기반 평균 처치 시간을 비교합니다.")

# 타입 순서는 원본 데이터 등장 순서를 유지한다.
type_order = []
for weapon in WEAPON_DATA:
    if weapon["type"] not in type_order:
        type_order.append(weapon["type"])

# 검색창은 타입 필터와 무관하게 전체 무기를 대상으로 한다.
all_weapons_sorted = []
for type_name in type_order:
    weapons_in_type = [w for w in WEAPON_DATA if w["type"] == type_name]
    weapons_in_type = sorted(weapons_in_type, key=lambda w: w["weapon"], reverse=True)
    all_weapons_sorted.extend(weapons_in_type)

all_weapon_options = [f'{w["type"]} | {w["weapon"]}' for w in all_weapons_sorted]
all_weapon_option_map = {f'{w["type"]} | {w["weapon"]}': w for w in all_weapons_sorted}

searched_weapon_options = st.sidebar.multiselect(
    "총기명 검색 추가",
    all_weapon_options,
    default=[],
    placeholder="총기 이름을 입력하세요",
    help="키보드로 총기명을 입력하면 자동완성 목록에서 바로 추가할 수 있습니다. 타입 필터와 무관하게 전체 무기에서 검색합니다.",
)

st.sidebar.subheader("필터")
selected_types = st.sidebar.multiselect(
    "무기 타입 필터",
    type_order,
    default=[],
    placeholder="선택하지 않으면 전체 표시",
)

# 비교할 총기 목록은 타입별로 묶고, 각 타입 안에서는 무기명을 내림차순으로 정렬한다.
# 무기 타입을 아무것도 선택하지 않은 초기 상태에서는 "필터 없음"으로 보고 전체 무기를 보여준다.
active_types = selected_types if selected_types else type_order

filtered_weapons = []
for type_name in type_order:
    if type_name not in active_types:
        continue
    weapons_in_type = [w for w in WEAPON_DATA if w["type"] == type_name]
    weapons_in_type = sorted(weapons_in_type, key=lambda w: w["weapon"], reverse=True)
    filtered_weapons.extend(weapons_in_type)

weapon_options = [f'{w["type"]} | {w["weapon"]}' for w in filtered_weapons]
weapon_option_map = {f'{w["type"]} | {w["weapon"]}': w for w in filtered_weapons}

def unique_labels_preserve_order(labels: List[str]) -> List[str]:
    seen = set()
    result = []
    for label in labels:
        if label in seen:
            continue
        seen.add(label)
        result.append(label)
    return result


st.sidebar.subheader("계산 옵션")
armor_plates = st.sidebar.radio(
    "방탄 플레이트",
    [0, 1, 2],
    index=0,
    horizontal=True,
)

# 슬라이더와 +/- number_input을 동기화한다.
if "distance_value" not in st.session_state:
    st.session_state.distance_value = 15
if "distance_slider" not in st.session_state:
    st.session_state.distance_slider = st.session_state.distance_value
if "distance_number" not in st.session_state:
    st.session_state.distance_number = st.session_state.distance_value

if "max_graph_distance_value" not in st.session_state:
    st.session_state.max_graph_distance_value = 80
if "max_graph_distance_slider" not in st.session_state:
    st.session_state.max_graph_distance_slider = st.session_state.max_graph_distance_value
if "max_graph_distance_number" not in st.session_state:
    st.session_state.max_graph_distance_number = st.session_state.max_graph_distance_value


def sync_distance_from_slider():
    st.session_state.distance_value = st.session_state.distance_slider
    st.session_state.distance_number = st.session_state.distance_slider


def sync_distance_from_number():
    st.session_state.distance_value = st.session_state.distance_number
    st.session_state.distance_slider = st.session_state.distance_number


def sync_max_graph_distance_from_slider():
    st.session_state.max_graph_distance_value = st.session_state.max_graph_distance_slider
    st.session_state.max_graph_distance_number = st.session_state.max_graph_distance_slider


def sync_max_graph_distance_from_number():
    st.session_state.max_graph_distance_value = st.session_state.max_graph_distance_number
    st.session_state.max_graph_distance_slider = st.session_state.max_graph_distance_number


st.sidebar.slider(
    "비교 거리",
    min_value=0,
    max_value=150,
    step=1,
    key="distance_slider",
    on_change=sync_distance_from_slider,
)

st.sidebar.number_input(
    "비교 거리 +/-",
    min_value=0,
    max_value=150,
    step=1,
    key="distance_number",
    on_change=sync_distance_from_number,
)

distance = int(st.session_state.distance_value)

st.sidebar.slider(
    "그래프 최대 거리",
    min_value=30,
    max_value=200,
    step=1,
    key="max_graph_distance_slider",
    on_change=sync_max_graph_distance_from_slider,
)

st.sidebar.number_input(
    "그래프 최대 거리 +/-",
    min_value=30,
    max_value=200,
    step=1,
    key="max_graph_distance_number",
    on_change=sync_max_graph_distance_from_number,
)

max_graph_distance = int(st.session_state.max_graph_distance_value)

selected_weapon_options = st.sidebar.multiselect(
    "비교할 총기",
    weapon_options,
    default=[],
    placeholder="타입 필터에서 고를 총기를 선택하세요",
)

selected_weapon_labels = unique_labels_preserve_order(
    selected_weapon_options + searched_weapon_options
)

# =========================
# 반동 기반 1:1 승률 비교
# =========================

st.subheader("반동 기반 1:1 승률 비교")
st.caption(
    "15m까지는 두 총기 모두 기본 명중률 25%로 고정하고, 15m 이후부터는 반동과 거리로 계산한 "
    "기하학적 감쇠율을 적용합니다. 방탄판 설정은 왼쪽 사이드바의 값을 사용합니다."
)

duel_weapon_options = [
    label
    for label, weapon in all_weapon_option_map.items()
    if weapon.get("type") in DUEL_ELIGIBLE_TYPES
]

if "duel_distance_value" not in st.session_state:
    st.session_state.duel_distance_value = 15

# 기존 세션 또는 이전 버전에서 15m 미만 값이 남아 있어도,
# 위젯을 만들기 전에 먼저 보정해야 Streamlit 세션 오류가 나지 않는다.
st.session_state.duel_distance_value = max(15, int(st.session_state.duel_distance_value))

if "duel_distance_slider" not in st.session_state:
    st.session_state.duel_distance_slider = st.session_state.duel_distance_value
else:
    st.session_state.duel_distance_slider = max(15, int(st.session_state.duel_distance_slider))

if "duel_distance_number" not in st.session_state:
    st.session_state.duel_distance_number = st.session_state.duel_distance_value
else:
    st.session_state.duel_distance_number = max(15, int(st.session_state.duel_distance_number))

# 세 값이 서로 어긋나 있으면 위젯 생성 전에 같은 값으로 맞춘다.
st.session_state.duel_distance_value = max(
    15,
    int(st.session_state.duel_distance_value),
)
st.session_state.duel_distance_slider = st.session_state.duel_distance_value
st.session_state.duel_distance_number = st.session_state.duel_distance_value


def sync_duel_distance_from_slider():
    st.session_state.duel_distance_value = st.session_state.duel_distance_slider
    st.session_state.duel_distance_number = st.session_state.duel_distance_slider


def sync_duel_distance_from_number():
    st.session_state.duel_distance_value = st.session_state.duel_distance_number
    st.session_state.duel_distance_slider = st.session_state.duel_distance_number


duel_cols = st.columns([2.0, 2.0, 2.2, 1.25])
with duel_cols[0]:
    duel_a_label = st.selectbox(
        "A 총기",
        ["선택 안 함"] + duel_weapon_options,
        index=0,
        key="duel_weapon_a",
    )
with duel_cols[1]:
    duel_b_label = st.selectbox(
        "B 총기",
        ["선택 안 함"] + duel_weapon_options,
        index=0,
        key="duel_weapon_b",
    )
with duel_cols[2]:
    st.slider(
        "교전 거리",
        min_value=15,
        max_value=100,
        step=1,
        key="duel_distance_slider",
        on_change=sync_duel_distance_from_slider,
    )
with duel_cols[3]:
    st.number_input(
        "거리 +/-",
        min_value=15,
        max_value=100,
        step=1,
        key="duel_distance_number",
        on_change=sync_duel_distance_from_number,
    )

duel_distance = int(st.session_state.duel_distance_value)

if duel_a_label != "선택 안 함" and duel_b_label != "선택 안 함":
    if duel_a_label == duel_b_label:
        st.warning("서로 다른 두 총기를 선택하세요.")
    else:
        duel_weapon_a = all_weapon_option_map[duel_a_label]
        duel_weapon_b = all_weapon_option_map[duel_b_label]

        duel_df_a = duel_variable_accuracy_distribution(
            duel_weapon_a,
            distance=float(duel_distance),
            armor_plates=int(armor_plates),
        )
        duel_df_b = duel_variable_accuracy_distribution(
            duel_weapon_b,
            distance=float(duel_distance),
            armor_plates=int(armor_plates),
        )

        a_win, b_win, tie_probability = duel_win_probability(duel_df_a, duel_df_b)

        mean_a, sigma_a = duel_distribution_mean_sigma(duel_df_a)
        mean_b, sigma_b = duel_distribution_mean_sigma(duel_df_b)

        p80_a = duel_distribution_quantile(duel_df_a, 0.80)
        p80_b = duel_distribution_quantile(duel_df_b, 0.80)
        p95_a = duel_distribution_quantile(duel_df_a, 0.95)
        p95_b = duel_distribution_quantile(duel_df_b, 0.95)

        base_a = weapon_result_row(duel_weapon_a, float(duel_distance), int(armor_plates))
        base_b = weapon_result_row(duel_weapon_b, float(duel_distance), int(armor_plates))

        p_a_first = duel_hit_probability_for_shot(duel_weapon_a, float(duel_distance), 1) * 100.0
        p_b_first = duel_hit_probability_for_shot(duel_weapon_b, float(duel_distance), 1) * 100.0
        burst_a = duel_burst_len_for_distance(float(duel_distance))
        burst_b = duel_burst_len_for_distance(float(duel_distance))
        p_a_late = duel_hit_probability_for_shot(duel_weapon_a, float(duel_distance), min(8, burst_a)) * 100.0
        p_b_late = duel_hit_probability_for_shot(duel_weapon_b, float(duel_distance), min(8, burst_b)) * 100.0

        winner = duel_weapon_a["weapon"] if a_win >= b_win else duel_weapon_b["weapon"]
        winner_prob = max(a_win, b_win) * 100.0

        metric_cols = st.columns(3)
        metric_cols[0].metric("예상 우세 총기", winner)
        metric_cols[1].metric(f"{duel_weapon_a['weapon']} 승률", f"{a_win * 100:.1f}%")
        metric_cols[2].metric(f"{duel_weapon_b['weapon']} 승률", f"{b_win * 100:.1f}%")

        result_df = pd.DataFrame([
            {
                "총기": duel_weapon_a["weapon"],
                "타입": duel_weapon_a["type"],
                "승률": a_win * 100,
                "STK": base_a["shots_to_kill"],
                "완전명중 TTK sec": base_a["ttk_sec"],
                "평균 처치 시간 sec": mean_a,
                "표준편차 σ sec": sigma_a,
                "P80 sec": p80_a,
                "P95 sec": p95_a,
                "1발째 명중률 %": p_a_first,
                "8발째/패턴 명중률 %": p_a_late,
            },
            {
                "총기": duel_weapon_b["weapon"],
                "타입": duel_weapon_b["type"],
                "승률": b_win * 100,
                "STK": base_b["shots_to_kill"],
                "완전명중 TTK sec": base_b["ttk_sec"],
                "평균 처치 시간 sec": mean_b,
                "표준편차 σ sec": sigma_b,
                "P80 sec": p80_b,
                "P95 sec": p95_b,
                "1발째 명중률 %": p_b_first,
                "8발째/패턴 명중률 %": p_b_late,
            },
        ])

        for col in [
            "승률",
            "완전명중 TTK sec",
            "평균 처치 시간 sec",
            "표준편차 σ sec",
            "P80 sec",
            "P95 sec",
            "1발째 명중률 %",
            "8발째/패턴 명중률 %",
        ]:
            result_df[col] = result_df[col].round(3)

        st.dataframe(result_df, use_container_width=True, hide_index=True)

        duel_sweep_df = duel_distance_sweep_win_probability(
            duel_weapon_a,
            duel_weapon_b,
            armor_plates=int(armor_plates),
            min_distance=15,
            max_distance=100,
            step=1,
        )

        if not duel_sweep_df.empty:
            win_fig = go.Figure()

            win_fig.add_trace(
                go.Scatter(
                    x=duel_sweep_df["distance"],
                    y=duel_sweep_df["a_win_percent"],
                    mode="lines",
                    name=f"{duel_weapon_a['weapon']} 승률",
                    line=dict(width=3),
                    hovertemplate=
                    "거리: %{x}m<br>"
                    f"{duel_weapon_a['weapon']} 승률: " + "%{y:.1f}%"
                    "<extra></extra>",
                )
            )

            win_fig.add_trace(
                go.Scatter(
                    x=duel_sweep_df["distance"],
                    y=duel_sweep_df["b_win_percent"],
                    mode="lines",
                    name=f"{duel_weapon_b['weapon']} 승률",
                    line=dict(width=3),
                    hovertemplate=
                    "거리: %{x}m<br>"
                    f"{duel_weapon_b['weapon']} 승률: " + "%{y:.1f}%"
                    "<extra></extra>",
                )
            )

            win_fig.add_hline(
                y=50,
                line_width=1,
                line_dash="dash",
                annotation_text="50%",
                annotation_position="top left",
            )

            win_fig.add_vline(
                x=duel_distance,
                line_width=1,
                line_dash="dot",
                annotation_text=f"현재 {duel_distance}m",
                annotation_position="top",
            )

            win_fig.update_layout(
                title="거리별 승률 그래프",
                xaxis_title="거리 m",
                yaxis_title="승률 %",
                yaxis=dict(range=[0, 100]),
                xaxis=dict(range=[15, 100]),
                legend_title="총기",
            )

            st.plotly_chart(win_fig, use_container_width=True)

        with st.expander("1:1 비교 모델 설명"):
            st.write(
                """
                - 15m 이하는 두 총기의 기본 명중률을 모두 25%로 고정합니다.
                - 15m를 넘으면 `G(n,d) / G(n,15m)` 감쇠율을 곱합니다.
                - `G(n,d)`는 표적 너비/높이가 거리에서 차지하는 허용각과, n번째 탄의 반동 오차를 비교한 기하학 값입니다.
                - 15~40m는 10발 단위, 40m 초과는 8발 단위로 반동 패턴이 리셋된다고 가정합니다.
                - 승률은 두 총기의 킬 시간 분포를 직접 비교해 계산합니다. 같은 시간에 처치하는 경우는 0.5승으로 처리합니다.
                - 거리별 승률 그래프는 15~100m 전체를 고정 계산하며, 슬라이더는 현재 확인 중인 거리의 수직선만 움직입니다.
                """
            )
else:
    st.info("A 총기와 B 총기를 선택하면 해당 거리에서의 승률 비교가 표시됩니다.")

st.divider()

if not selected_weapon_labels:
    st.info("왼쪽 사이드바에서 비교할 총기를 직접 선택하거나, 총기명 검색으로 추가하세요.")
    st.stop()

selected_weapon_data = [
    all_weapon_option_map[label]
    for label in selected_weapon_labels
    if label in all_weapon_option_map
]
weapon_by_name = {weapon["weapon"]: weapon for weapon in WEAPON_DATA}

if not selected_weapon_data:
    st.warning("비교할 총기가 선택되지 않았습니다.")
    st.stop()

if searched_weapon_options:
    st.sidebar.caption("검색으로 추가한 총기는 무기 타입 필터와 관계없이 비교 대상에 포함됩니다.")

summary_rows = [
    weapon_result_row(weapon=w, distance=float(distance), armor_plates=armor_plates)
    for w in selected_weapon_data
]
summary_df = pd.DataFrame(summary_rows)
summary_df["ttk_ms"] = summary_df["ttk_sec"] * 1000
summary_df = summary_df.sort_values(["ttk_sec", "shots_to_kill", "weapon"]).reset_index(drop=True)

# =========================
# 화면 출력
# =========================

left, right = st.columns([1.35, 1])

with left:
    st.subheader(f"{distance}m 기준 비교")

    display_df = summary_df.copy()
    for col in ["ttk_sec", "normal_damage_at_distance", "armor_damage_at_distance_plus_10m", "reload"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].round(3)

    display_df = display_df[
        [
            "type",
            "weapon",
            "rpm",
            "firing_mode",
            "reload",
            "normal_damage_at_distance",
            "armor_damage_at_distance_plus_10m",
            "armor_plates",
            "shots_to_kill",
            "ttk_sec",
        ]
    ].rename(columns={
        "type": "타입",
        "weapon": "총기",
        "rpm": "RPM",
        "firing_mode": "발사모드",
        "reload": "재장전",
        "normal_damage_at_distance": "기준 데미지",
        "armor_damage_at_distance_plus_10m": "방탄판 데미지",
        "armor_plates": "방탄판",
        "shots_to_kill": "STK",
        "ttk_sec": "TTK",
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

with right:
    st.subheader("계산 규칙")

    if armor_plates == 0:
        st.write(
            """
            **방탄판 0장**
            - HP: 100
            - 플레이트 없음
            - 실제 거리 기준 데미지 적용
            """
        )
    else:
        st.write(
            f"""
            **방탄판 {armor_plates}장**
            - HP: 100
            - 플레이트 HP: {armor_plates * ARMOR_HP_PER_PLATE}
            - 플레이트가 남아 있으면 해당 탄환은 **거리 +{ARMOR_RANGE_PENALTY:.0f}m 데미지** 적용
            - 단, **DMR / Sidearm은 거리 +{ARMOR_RANGE_PENALTY:.0f}m 후퇴 미적용**
            - 플레이트 초과 피해는 HP로 넘어감
            """
        )

    st.write(
        f"""
        **내장 데이터**
        - 사용 가능 총기: {len(WEAPON_DATA)}개
        - 제외된 항목: {len(SKIPPED_WEAPONS)}개
        """
    )

# =========================
# 거리별 TTK 그래프
# =========================

st.subheader("거리별 TTK 그래프")

sweep_df = pd.concat(
    [sweep_weapon(w, armor_plates=armor_plates, max_distance=max_graph_distance) for w in selected_weapon_data],
    ignore_index=True,
)
sweep_df["ttk_ms"] = sweep_df["ttk_sec"] * 1000

fig_ttk = px.line(
    sweep_df,
    x="distance",
    y="ttk_ms",
    color="weapon",
    markers=False,
    title="Distance / TTK",
    labels={
        "distance": "거리 m",
        "ttk_ms": "TTK ms",
        "weapon": "총기",
        "shots_to_kill": "STK",
        "type": "타입",
    },
    custom_data=["type", "shots_to_kill"],
)

fig_ttk.update_traces(
    hovertemplate=
    "타입: %{customdata[0]}<br>"
    "총기: %{fullData.name}<br>"
    "거리: %{x}m<br>"
    "TTK: %{y:.1f} ms<br>"
    "STK: %{customdata[1]}발"
    "<extra></extra>"
)

st.plotly_chart(fig_ttk, use_container_width=True)

# =========================
# 개인 명중률 기반 평균 처치 시간
# =========================

st.subheader("개인 명중률 기반 평균 처치 시간")
st.caption(
    "기준: 현재 선택한 거리/방탄판 조건의 STK를 필요한 명중탄 수로 보고, "
    "각 탄환이 입력한 명중률로 독립적으로 명중한다고 가정합니다. "
    "재장전 시간은 반영하지 않습니다."
)

accuracy_cols = st.columns(min(3, len(selected_weapon_data)))
accuracy_inputs = {}

for idx, weapon in enumerate(selected_weapon_data):
    weapon_name = weapon["weapon"]
    with accuracy_cols[idx % len(accuracy_cols)]:
        default_accuracy = default_accuracy_for_weapon(weapon)

        accuracy_inputs[weapon_name] = st.number_input(
            f"{weapon_name} 명중률 (%)",
            min_value=0.1,
            max_value=100.0,
            value=round(float(default_accuracy), 2),
            step=1.0,
            format="%.2f",
            key=f"accuracy_{weapon_name}",
        )


accuracy_rows = []
for _, row in summary_df.iterrows():
    weapon_name = row["weapon"]
    weapon_obj = weapon_by_name.get(weapon_name)
    accuracy = accuracy_inputs.get(weapon_name, 100.0)

    stats = calculate_accuracy_stats(
        shots_to_kill=int(row["shots_to_kill"]),
        rpm=float(row["rpm"]),
        accuracy_percent=float(accuracy),
    )

    mean_time_sec = stats["mean_time_sec"]
    sigma_time_sec = stats["sigma_time_sec"]

    accuracy_rows.append({
        "type": row["type"],
        "weapon": weapon_name,
        "accuracy_percent": accuracy,
        "stk_needed_hits": int(row["shots_to_kill"]),
        "perfect_ttk_sec": row["ttk_sec"],
        "mean_time_M_sec": mean_time_sec,
        "sigma_sec": sigma_time_sec,
        "expected_shots_fired": stats["expected_shots"],
        "coverage": stats["coverage"],
    })

accuracy_df = pd.DataFrame(accuracy_rows)
accuracy_df = accuracy_df.sort_values(["mean_time_M_sec", "weapon"]).reset_index(drop=True)

accuracy_display = accuracy_df.copy()
for col in [
    "accuracy_percent",
    "perfect_ttk_sec",
    "mean_time_M_sec",
    "sigma_sec",
    "expected_shots_fired",
    "coverage",
]:
    if col in accuracy_display.columns:
        accuracy_display[col] = accuracy_display[col].round(3)

accuracy_display = accuracy_display.rename(columns={
    "type": "타입",
    "weapon": "총기",
    "accuracy_percent": "명중률 %",
    "stk_needed_hits": "필요 명중탄 STK",
    "perfect_ttk_sec": "완전명중 TTK s",
    "mean_time_M_sec": "평균 처치 시간 sec",
    "sigma_sec": "표준편차 σ sec",
    "expected_shots_fired": "평균 발사탄 수",
})

accuracy_table_col, _accuracy_table_blank = st.columns([0.78, 0.22])
with accuracy_table_col:
    st.dataframe(
        accuracy_display[
            [
                "타입",
                "총기",
                "명중률 %",
                "필요 명중탄 STK",
                "완전명중 TTK s",
                "평균 처치 시간 sec",
                "표준편차 σ sec",
                "평균 발사탄 수",
            ]
        ],
        use_container_width=False,
        width=980,
        hide_index=True,
    )

# 평균 처치 시간 막대그래프는 제거했습니다.
# 아래의 음이항분포/누적확률 그래프에서 시간 분포를 직접 확인합니다.

# =========================
# 현재 거리 기준 개인 명중률 확률분포
# =========================

st.subheader("현재 거리 기준 개인 명중률 처치 시간 분포")
st.caption(
    "필요한 명중탄 수 STK와 개인 명중률을 바탕으로 한 음이항분포를 그립니다. "
    "즉, '몇 발째에 킬이 나는가'를 확률로 보여줍니다. "
    "곡선이 완전히 겹치는 총기도 구분되도록 총기마다 선 모양을 다르게 표시합니다."
)

weapon_order_for_accuracy_graph = [weapon["weapon"] for weapon in selected_weapon_data]
sigma_color_map = color_map_by_sigma(accuracy_df, weapon_order_for_accuracy_graph)
distribution_dash_map = line_dash_map_for_weapons(weapon_order_for_accuracy_graph)

distribution_frames = []
distribution_summary_rows = []

for _, distribution_row in accuracy_df.iterrows():
    distribution_weapon_name = distribution_row["weapon"]
    distribution_df = negative_binomial_distribution(
        shots_to_kill=int(distribution_row["stk_needed_hits"]),
        rpm=float(weapon_by_name[distribution_weapon_name]["rpm"]),
        accuracy_percent=float(distribution_row["accuracy_percent"]),
    )

    if distribution_df.empty:
        continue

    distribution_df = distribution_df.copy()
    distribution_df["weapon"] = distribution_weapon_name
    distribution_df["type"] = distribution_row["type"]
    distribution_df["accuracy_percent"] = float(distribution_row["accuracy_percent"])
    distribution_df["stk_needed_hits"] = int(distribution_row["stk_needed_hits"])
    distribution_df["mean_time_M_sec"] = float(distribution_row["mean_time_M_sec"])
    distribution_df["sigma_sec"] = float(distribution_row["sigma_sec"])
    distribution_df["probability_percent"] = distribution_df["probability"] * 100.0
    distribution_df["cumulative_percent"] = distribution_df["cumulative_probability"] * 100.0

    q50 = distribution_quantile(distribution_df, 0.50)
    q80 = distribution_quantile(distribution_df, 0.80)
    q95 = distribution_quantile(distribution_df, 0.95)
    coverage_percent = float(distribution_df["cumulative_probability"].iloc[-1]) * 100.0

    distribution_summary_rows.append({
        "타입": distribution_row["type"],
        "총기": distribution_weapon_name,
        "명중률 %": round(float(distribution_row["accuracy_percent"]), 2),
        "필요 명중탄 STK": int(distribution_row["stk_needed_hits"]),
        "평균 M sec": round(float(distribution_row["mean_time_M_sec"]), 3),
        "표준편차 σ sec": round(float(distribution_row["sigma_sec"]), 3),
        "50% 처치 시간 sec": round(q50, 3) if q50 is not None else None,
        "80% 처치 시간 sec": round(q80, 3) if q80 is not None else None,
        "95% 처치 시간 sec": round(q95, 3) if q95 is not None else None,
        "표시 누적확률 %": round(coverage_percent, 2),
        "색상 기준": "σ 높음 → 빨강" if distribution_weapon_name == max(sigma_color_map, key=lambda w: accuracy_df.loc[accuracy_df["weapon"] == w, "sigma_sec"].iloc[0]) else "",
    })

    distribution_frames.append(distribution_df)

if not distribution_frames:
    st.warning("선택한 총기의 개인 명중률 분포를 만들 수 없습니다.")
else:
    all_distribution_df = pd.concat(distribution_frames, ignore_index=True)

    dist_summary_col, _dist_summary_blank = st.columns([0.86, 0.14])
    with dist_summary_col:
        st.dataframe(
            pd.DataFrame(distribution_summary_rows).drop(columns=["색상 기준"], errors="ignore"),
            use_container_width=False,
            width=1080,
            hide_index=True,
        )

    pmf_tab, cdf_tab = st.tabs(["확률분포", "누적확률"])

    with pmf_tab:
        fig_pmf = go.Figure()
        for weapon_name in weapon_order_for_accuracy_graph:
            weapon_df = all_distribution_df[all_distribution_df["weapon"] == weapon_name].sort_values("kill_time_sec")
            if weapon_df.empty:
                continue

            color = sigma_color_map.get(weapon_name, "#666666")
            dash_style = distribution_dash_map.get(weapon_name, "solid")
            custom_data = weapon_df[[
                "fired_shots",
                "cumulative_percent",
                "accuracy_percent",
                "stk_needed_hits",
                "mean_time_M_sec",
                "sigma_sec",
            ]].to_numpy()

            fig_pmf.add_trace(
                go.Scatter(
                    x=weapon_df["kill_time_sec"],
                    y=weapon_df["probability_percent"],
                    mode="lines",
                    line=dict(color=color, width=4, dash=dash_style),
                    opacity=0.88,
                    name=weapon_name,
                    customdata=custom_data,
                    hovertemplate=
                        "총기: %{fullData.name}<br>"
                        "처치 시간: %{x:.3f} sec<br>"
                        "총 발사탄 수: %{customdata[0]}발<br>"
                        "명중률: %{customdata[2]:.2f}%<br>"
                        "필요 명중탄 STK: %{customdata[3]}발<br>"
                        "해당 시점 처치 확률: %{y:.2f}%<br>"
                        "누적 처치 확률: %{customdata[1]:.2f}%<br>"
                        "평균 M: %{customdata[4]:.3f} sec<br>"
                        "표준편차 σ: %{customdata[5]:.3f} sec"
                        "<extra></extra>",
                )
            )

        fig_pmf.update_layout(
            title=f"처치 시간 확률분포 / 현재 거리 {distance}m",
            xaxis_title="처치 시간 sec",
            yaxis_title="해당 시점 처치 확률 %",
            legend_title="총기 — σ 높을수록 빨강 / 선 모양은 겹침 구분",
        )
        st.plotly_chart(fig_pmf, use_container_width=True)

    with cdf_tab:
        fig_cdf = go.Figure()
        for weapon_name in weapon_order_for_accuracy_graph:
            weapon_df = all_distribution_df[all_distribution_df["weapon"] == weapon_name].sort_values("kill_time_sec")
            if weapon_df.empty:
                continue

            color = sigma_color_map.get(weapon_name, "#666666")
            dash_style = distribution_dash_map.get(weapon_name, "solid")
            custom_data = weapon_df[[
                "fired_shots",
                "probability_percent",
                "accuracy_percent",
                "stk_needed_hits",
                "mean_time_M_sec",
                "sigma_sec",
            ]].to_numpy()

            fig_cdf.add_trace(
                go.Scatter(
                    x=weapon_df["kill_time_sec"],
                    y=weapon_df["cumulative_percent"],
                    mode="lines",
                    line=dict(color=color, width=4, dash=dash_style),
                    opacity=0.88,
                    name=weapon_name,
                    customdata=custom_data,
                    hovertemplate=
                        "총기: %{fullData.name}<br>"
                        "시간: %{x:.3f} sec<br>"
                        "총 발사탄 수: %{customdata[0]}발<br>"
                        "명중률: %{customdata[2]:.2f}%<br>"
                        "필요 명중탄 STK: %{customdata[3]}발<br>"
                        "그 시점 단일 확률: %{customdata[1]:.2f}%<br>"
                        "누적 처치 확률: %{y:.2f}%<br>"
                        "평균 M: %{customdata[4]:.3f} sec<br>"
                        "표준편차 σ: %{customdata[5]:.3f} sec"
                        "<extra></extra>",
                )
            )

        for target_percent in [50, 80, 95]:
            fig_cdf.add_hline(
                y=target_percent,
                line_width=1,
                line_dash="dot",
                annotation_text=f"{target_percent}%",
                annotation_position="right",
            )

        fig_cdf.update_layout(
            title=f"누적 처치 확률 / 현재 거리 {distance}m",
            xaxis_title="처치 시간 sec",
            yaxis_title="누적 처치 확률 %",
            yaxis=dict(range=[0, 100]),
            legend_title="총기 — σ 높을수록 빨강 / 선 모양은 겹침 구분",
        )
        st.plotly_chart(fig_cdf, use_container_width=True)

    with st.expander("처치 시간 분포 데이터 보기"):
        dist_table = all_distribution_df.copy()
        dist_table["kill_time_sec"] = dist_table["kill_time_sec"].round(3)
        dist_table["probability_percent"] = dist_table["probability_percent"].round(3)
        dist_table["cumulative_percent"] = dist_table["cumulative_percent"].round(3)
        dist_table["accuracy_percent"] = dist_table["accuracy_percent"].round(2)
        dist_table["mean_time_M_sec"] = dist_table["mean_time_M_sec"].round(3)
        dist_table["sigma_sec"] = dist_table["sigma_sec"].round(3)
        st.dataframe(
            dist_table[[
                "type",
                "weapon",
                "fired_shots",
                "kill_time_sec",
                "probability_percent",
                "cumulative_percent",
                "accuracy_percent",
                "stk_needed_hits",
                "mean_time_M_sec",
                "sigma_sec",
            ]].rename(columns={
                "type": "타입",
                "weapon": "총기",
                "fired_shots": "총 발사탄 수",
                "kill_time_sec": "처치 시간 sec",
                "probability_percent": "해당 시점 처치 확률 %",
                "cumulative_percent": "누적 처치 확률 %",
                "accuracy_percent": "명중률 %",
                "stk_needed_hits": "필요 명중탄 STK",
                "mean_time_M_sec": "평균 M sec",
                "sigma_sec": "표준편차 σ sec",
            }),
            use_container_width=True,
            hide_index=True,
        )

st.subheader("거리별 개인 명중률 평균 처치 시간 그래프")
st.caption(
    "각 거리에서의 STK를 다시 계산한 뒤, 입력한 개인 명중률을 적용해 평균 처치 시간 M을 그립니다. "
    "표준편차 옵션을 켜면 M ± σ 구간이 반투명 밴드로 표시됩니다."
)

show_accuracy_sigma_band = st.checkbox(
    "표준편차 범위 표시 (M ± σ)",
    value=True,
    key="show_accuracy_sigma_band_distance_graph",
)

accuracy_sweep_rows = []

for weapon in selected_weapon_data:
    weapon_name = weapon["weapon"]
    accuracy = float(accuracy_inputs.get(weapon_name, default_accuracy_for_weapon(weapon)))

    for sweep_distance in range(0, max_graph_distance + 1):
        base_row = weapon_result_row(
            weapon=weapon,
            distance=float(sweep_distance),
            armor_plates=armor_plates,
        )
        stats = calculate_accuracy_stats(
            shots_to_kill=int(base_row["shots_to_kill"]),
            rpm=float(base_row["rpm"]),
            accuracy_percent=accuracy,
        )

        mean_sec = stats["mean_time_sec"]
        sigma_sec = stats["sigma_time_sec"]
        if mean_sec is None or sigma_sec is None:
            continue

        accuracy_sweep_rows.append({
            "type": weapon["type"],
            "weapon": weapon_name,
            "distance": float(sweep_distance),
            "accuracy_percent": accuracy,
            "shots_to_kill": int(base_row["shots_to_kill"]),
            "perfect_ttk_sec": base_row["ttk_sec"],
            "mean_time_M_sec": mean_sec,
            "sigma_sec": sigma_sec,
            "mean_minus_sigma_sec": max(0.0, mean_sec - sigma_sec),
            "mean_plus_sigma_sec": mean_sec + sigma_sec,
            "expected_shots_fired": stats["expected_shots"],
        })

accuracy_sweep_df = pd.DataFrame(accuracy_sweep_rows)

if accuracy_sweep_df.empty:
    st.warning("거리별 개인 명중률 그래프를 만들 수 있는 데이터가 없습니다.")
else:
    fig_accuracy_distance = go.Figure()
    weapon_order_for_graph = [weapon["weapon"] for weapon in selected_weapon_data]
    color_map = sigma_color_map if "sigma_color_map" in globals() or "sigma_color_map" in locals() else color_map_by_sigma(accuracy_df, weapon_order_for_graph)

    if show_accuracy_sigma_band:
        for weapon_name in weapon_order_for_graph:
            weapon_df = accuracy_sweep_df[accuracy_sweep_df["weapon"] == weapon_name].sort_values("distance")
            if weapon_df.empty:
                continue

            color = color_map[weapon_name]
            fill_color = hex_to_rgba(color, 0.18)

            fig_accuracy_distance.add_trace(
                go.Scatter(
                    x=weapon_df["distance"],
                    y=weapon_df["mean_plus_sigma_sec"],
                    mode="lines",
                    line=dict(width=0, color=fill_color),
                    hoverinfo="skip",
                    showlegend=False,
                    name=f"{weapon_name} +σ",
                )
            )
            fig_accuracy_distance.add_trace(
                go.Scatter(
                    x=weapon_df["distance"],
                    y=weapon_df["mean_minus_sigma_sec"],
                    mode="lines",
                    line=dict(width=0, color=fill_color),
                    fill="tonexty",
                    fillcolor=fill_color,
                    hoverinfo="skip",
                    showlegend=False,
                    name=f"{weapon_name} M ± σ",
                )
            )

    for weapon_name in weapon_order_for_graph:
        weapon_df = accuracy_sweep_df[accuracy_sweep_df["weapon"] == weapon_name].sort_values("distance")
        if weapon_df.empty:
            continue

        color = color_map[weapon_name]
        custom_data = weapon_df[[
            "sigma_sec",
            "accuracy_percent",
            "shots_to_kill",
            "expected_shots_fired",
            "perfect_ttk_sec",
        ]].to_numpy()

        fig_accuracy_distance.add_trace(
            go.Scatter(
                x=weapon_df["distance"],
                y=weapon_df["mean_time_M_sec"],
                mode="lines",
                line=dict(color=color, width=3),
                name=weapon_name,
                customdata=custom_data,
                hovertemplate=
                    "총기: %{fullData.name}<br>"
                    "거리: %{x}m<br>"
                    "명중률: %{customdata[1]:.1f}%<br>"
                    "필요 명중탄 STK: %{customdata[2]}발<br>"
                    "완전명중 TTK: %{customdata[4]:.3f} sec<br>"
                    "평균 발사탄 수: %{customdata[3]:.2f}발<br>"
                    "평균 처치 시간: %{y:.3f} sec<br>"
                    "표준편차 σ: %{customdata[0]:.3f} sec"
                    "<extra></extra>",
            )
        )

    fig_accuracy_distance.update_layout(
        title="Personal Accuracy / Distance / Mean Time To Kill",
        xaxis_title="거리 m",
        yaxis_title="평균 처치 시간 sec",
        legend_title="총기",
    )

    st.plotly_chart(fig_accuracy_distance, use_container_width=True)

with st.expander("개인 명중률 계산식 설명"):
    st.write(
        """
        - 기존 TTK는 모든 탄이 명중한다고 가정한 값입니다.
        - 개인 명중률 계산은 현재 거리/방탄판 조건에서 필요한 명중탄 수, 즉 STK를 먼저 구합니다.
        - 그 다음 각 발이 입력한 명중률 p로 명중한다고 보고, k번째 명중이 나올 때까지 필요한 총 발사탄 수 N을 계산합니다.
        - N은 음이항분포를 따릅니다.
        - 재장전 시간은 반영하지 않습니다.
        - 평균 처치 시간은 초(sec) 단위이며, σ는 처치 시간의 표준편차입니다.
        - 확률분포/누적확률 그래프는 음이항분포를 직접 계산해 표시합니다.
        """
    )

# =========================
# 내장 데이터 확인
# =========================

with st.expander("내장 총기 데이터 확인"):
    data_preview = []
    for weapon in WEAPON_DATA:
        data_preview.append({
            "type": weapon["type"],
            "weapon": weapon["weapon"],
            "rpm": weapon["rpm"],
            "firing_mode": weapon.get("firing_mode"),
            "velocity": weapon.get("velocity"),
            "mag_size": weapon.get("mag_size"),
            "reload": weapon.get("reload"),
            "damage_profile": damage_profile_to_text(weapon["damage_profile"]),
        })
    st.dataframe(pd.DataFrame(data_preview), use_container_width=True, hide_index=True)

if SKIPPED_WEAPONS:
    with st.expander("제외된 항목"):
        st.write("원본 시트에서 RPM 또는 숫자형 거리별 Body Damage가 없어 내장 계산 데이터에서 제외했습니다.")
        st.write(SKIPPED_WEAPONS)
