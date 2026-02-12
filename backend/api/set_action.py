#!/usr/bin/env python3

import argparse
from motion_control_service import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser("set motion control action")
    MotionControlService.add_arguments(parser)
    args = parser.parse_args()

    # MotionControlService(args).select_action(["JOINT_FREEZE"])
    # MotionControlService(args).ensure_action("McAction_PASSIVE_DEFAULT")
    
#  1: DEFAULT
#  2: JOINT_DEFAULT
#  3: JOINT_FREEZE
#  4: JOINT_TEST
#  5: LOCOMOTION_ARM_EXT_JOINT_SERVO
#  6: LOCOMOTION_DEFAULT
#  7: NAVIGATION_DEFAULT
#  8: PASSIVE_DAMPING
#  9: PASSIVE_DEFAULT
#  10: STAND_ARM_EXT_JOINT_SERVO
#  11: STAND_ARM_EXT_JOINT_TRAJ
#  12: STAND_ARM_FREEZE
#  13: STAND_ARM_PRESET_MOTION
#  14: STAND_DEFAULT