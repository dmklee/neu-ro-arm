import numpy as np
from scipy.spatial.transform import Rotation as R

import matplotlib
matplotlib.use('TkAgg')
import tkinter as tk

from neu_ro_arm.constants import GRIPPER_CLOSED, GRIPPER_OPENED
from neu_ro_arm.robot.motion_planner import MotionPlanner
from neu_ro_arm.robot.pybullet_simulator import PybulletSimulator
from neu_ro_arm.robot.simulator_controller import SimulatorController
from neu_ro_arm.robot.xarm_controller import XArmController

class RobotArm:
    def __init__(self,
                 controller_type='real',
                 headless=True,
                 realtime=True,
                 workspace=None,
                ):
        '''Real or simulated xArm robot interface for safe, high-level motion commands

        Parameters
        ----------
        controller_type : str, {'real','sim'}, default to 'real'
            Indicate whether motor control be sent to a simulator or the real robot

        Attrbutes
        ---------
        joint_names : :tuple: str
            names of the joints in the arm
        controller : BaseController
            Controller used to execute motion commands
        mp : MotionPlanner
            Internal simulator of robot used to perform IK and collision
            detection
        '''
        self.joint_names = ('base', 'shoulder','elbow', 'wrist','wristRotation', 'gripper')

        self._sim = PybulletSimulator(headless)
        self.mp = MotionPlanner(self._sim, workspace)
        if controller_type == 'real':
            self.controller = XArmController()
        elif controller_type == 'sim':
            self.controller = SimulatorController(self._sim, realtime)
        else:
            raise TypeError('invalid controller type')
        self.controller_type = controller_type

        self._mirror_planner()

    def home(self):
        '''Moves to home arm positions
        '''
        self.move_arm_jpos(self.controller.arm_jpos_home)

    def passive_mode(self):
        self.controller.power_off_servos()

    def passive_mode(self):
        self.controller.power_off_servos()

    def active_mode(self):
        self.controller.power_on_servos()

    def get_arm_jpos(self):
        '''Get positions of the arm joints

        Returns
        -------
        ndarray
            joint angles in radians; shape=(5,); dtype=float
        '''
        arm_jpos = self.controller.read_arm_jpos()
        return arm_jpos

    def move_arm_jpos(self, jpos, verbose=True):
        '''Moves arm joints to specific positions

        Parameters
        ----------
        jpos : ndarray
            Desired joint angles in radians for each joint in the arm;
            shape=(5,); dtype=float
        verbose : bool
            Whether to print error messages in case of an issue

        Returns
        -------
        bool
            True if joint angles returned from IK were achieved
        '''
        current_jpos = self.get_arm_jpos()
        if not self.mp.is_collision_free_trajectory(current_jpos, jpos):
            if verbose:
                print(f"[MOVE FAILED] Trajectory would result in collision"
                      f" of robot:{e.robot_link} and {e.other_body}.")
            return False

        duration = self.controller.write_arm_jpos(jpos)
        success, achieved_jpos = self.controller.monitor(self.controller.arm_joint_ids,
                                                         jpos, duration)
        if not success:
            # to avoid leaving motors under load, move to achieved jpos
            self.controller.write_arm_jpos(achieved_jpos)

        self._mirror_planner()
        return success

    def get_hand_pose(self):
        self._mirror_planner()
        return self.mp.get_hand_pose()

    def move_hand_to(self,
                     pos,
                     pitch_roll=None,
                     verbose=True,
                     **ik_kwargs
                    ):
        '''Moves end effector to desired pose in world

        Parameters
        ----------
        pos : array_like
            desired 3d position of end effector; shape=(3,); dtype=float
        pos : array_like
            desired 3d position of end effector; shape=(3,); dtype=float
        verbose : bool
            Whether to print error messages in case of an issue

        Raises
        ------
        UnsafeJointPosition
            If desired pose results in joint configuration that is in collision
            with the world
        UnsafeTrajectoryError
            If trajectory to reach desired pose will cause a collision.  See
            move_arm_jpos for details

        Returns
        -------
        bool
            True if joint angles returned from IK were achieved
        dict
            contains information about IK solution
        '''
        if pitch_roll is None:
            rot = None
        else:
            yaw = np.arctan2(pos[1], pos[0])
            pitch, roll = pitch_roll
            rot = R.from_euler('z', yaw) * R.from_euler('YZ', (pitch, roll + np.pi/2) )
            rot = rot.as_quat()

        jpos, ik_info = self.mp.calculate_ik(pos, rot, **ik_kwargs)

        return self.move_arm_jpos(jpos)

    def open_gripper(self):
        '''Opens gripper completely

        Returns
        -------
        bool
            True if desired gripper state was achieved
        '''
        return self.set_gripper_state(GRIPPER_OPENED)

    def close_gripper(self):
        '''Closes gripper completely

        Returns
        -------
        bool
            True if desired gripper state was achieved
        '''
        return self.set_gripper_state(GRIPPER_CLOSED, backoff=-0.05)

    def set_gripper_state(self, state, backoff=-0.05):
        '''Get state of gripper

        Parameters
        ----------
        state : float
            gripper state to move to; will be clipped to range [0,1]

        backoff : float
            amount of back off if move fails (as fraction of gripper range). a
            positive value of backoff means the gripper will be more open
            than the acheived position

        Returns
        -------
        bool
            gripper state that is achieved
        '''
        state = np.clip(state, 0, 1)
        duration = self.controller.write_gripper_state(state)

        gripper_jpos = self.controller._gripper_state_to_jpos(state)
        success, achieved_jpos = self.controller.monitor(self.controller.gripper_joint_ids,
                                                         gripper_jpos,
                                                         duration)
        if not success:
            # to avoid leaving motors under load, move to achieved jpos
            achieved_state = self.controller._gripper_jpos_to_state(achieved_jpos)
            achieved_state += backoff
            self.controller.write_gripper_state(achieved_state)
            self.controller.timestep()

        achieved_gripper_state = self.get_gripper_state()
        self._mirror_planner()
        return achieved_gripper_state

    def get_gripper_state(self):
        '''Get state of gripper

        Returns
        -------
        float
            value in range [0,1] describing how close to open(1) or closed(0)
            the gripper is
        '''
        return self.controller.read_gripper_state()

    def _mirror_planner(self):
        if self.controller_type == 'real':
            self.mp.mirror(arm_jpos=self.get_arm_jpos(),
                           gripper_state=self.get_gripper_state())